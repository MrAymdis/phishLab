"""演练邮件渲染：模板变量替换、落地页链接、追踪像素、二维码、附件载荷变体。

Worker 批量投递与演练「测试发送」共用，保证测试邮件与真实演练邮件内容一致。
"""
import hashlib
import io
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.qr import render_qr_png
from app.modules.channel.models import PhishDomain, SendChannel, SenderProfile
from app.modules.org.models import EmpDept
from app.modules.template.models import EmailTemplate, LandingPage


_MISSING = object()

# 附件变体占位符与邮件正文同一变量表（Word 内需以无格式断点输入的整串文本）
_ATTACH_VARS = ("{{.FirstName}}", "{{.LastName}}", "{{.Department}}",
                "{{.Email}}", "{{.Date}}")


def _add_beacon_relationship(rels_xml: str, pixel_url: str) -> tuple[str, str]:
    """docx 关系文件追加外链图片关系（beacon）；返回 (rels_xml, 关系 Id)。"""
    rid = "rIdPhishLabBeacon"
    while f'Id="{rid}"' in rels_xml:
        rid += "X"  # 理论不会冲突，防御性加后缀
    rel = (
        f'<Relationship Id="{rid}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="{pixel_url}" TargetMode="External"/>'
    )
    return rels_xml.replace("</Relationships>", rel + "</Relationships>"), rid


def _add_beacon_drawing(doc_xml: str, rid: str) -> str:
    """docx 正文尾部插入 beacon 外链图（120×30 降级横幅，EMU=像素×9525）。

    纯渲染期资源加载，无宏无代码执行（与红线 6 的宏/EXE 载荷完全独立）。
    """
    if "</w:body>" not in doc_xml:
        return doc_xml
    # 缺命名空间声明时补在根元素（Word 生成文件通常已声明）
    for prefix, uri in (
        ("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"),
        ("a", "http://schemas.openxmlformats.org/drawingml/2006/main"),
        ("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture"),
    ):
        if f"xmlns:{prefix}=" not in doc_xml:
            doc_xml = doc_xml.replace("<w:document ", f'<w:document xmlns:{prefix}="{uri}" ', 1)
    cx, cy = 1143000, 285750  # 120×30 像素（与追踪像素降级横幅同规格）
    drawing = (
        '<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        '<wp:docPr id="99001" name="图片 1"/><wp:cNvGraphicFramePr>'
        '<a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic><pic:nvPicPr><pic:cNvPr id="99002" name="beacon"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    )
    # w:sectPr 必须是 w:body 最后一个子元素（CT_Body 序列约束），beacon 段落须插在其前；
    # Word 对顺序违规宽容但严格校验器会报损坏，统一按规范插入
    sect_start = doc_xml.rfind("<w:sectPr")
    if sect_start != -1:
        return doc_xml[:sect_start] + drawing + doc_xml[sect_start:]
    return doc_xml.replace("</w:body>", drawing + "</w:body>")


def _render_docx_variant(raw: bytes, var_map: dict, pixel_url: str | None) -> bytes:
    """docx 变体：占位符替换 + beacon 注入（zip 内 XML 原位处理）。

    失败兜底原样透传，不阻断投递（个性化与溯源属尽力而为，投递是主链路）。
    """
    if not raw.startswith(b"PK"):
        return raw
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        names = z.namelist()
        if "word/document.xml" not in names:
            return raw
        doc_xml = z.read("word/document.xml").decode("utf-8")
        rels_xml = (z.read("word/_rels/document.xml.rels").decode("utf-8")
                    if "word/_rels/document.xml.rels" in names else None)
        for k, v in var_map.items():
            doc_xml = doc_xml.replace(k, v)
        if pixel_url and rels_xml is not None:
            rels_xml, rid = _add_beacon_relationship(rels_xml, pixel_url)
            doc_xml = _add_beacon_drawing(doc_xml, rid)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
            for name in names:
                data = z.read(name)
                if name == "word/document.xml":
                    data = doc_xml.encode("utf-8")
                elif name == "word/_rels/document.xml.rels" and rels_xml is not None:
                    data = rels_xml.encode("utf-8")
                zo.writestr(name, data)
        return out.getvalue()
    except Exception:
        return raw


def _render_xlsx_variant(raw: bytes, var_map: dict, pixel_url: str | None) -> bytes:
    """xlsx 变体：占位符替换 + beacon 注入（zip 内 XML 原位处理，同 docx）。

    xlsx 图片必须走 drawing part 链：sheet →(rels)→ drawing →(rels)→ image。
    新建 xl/drawings/drawing1.xml + 两级 rels，sheet1.xml 的 </sheetData> 后挂
    <drawing r:id>，并在 [Content_Types].xml 注册 drawing Override；仅注入
    第一个 sheet（打开文件默认激活表，加载即请求 beacon）。
    失败兜底原样透传，不阻断投递（个性化与溯源属尽力而为，投递是主链路）。
    """
    if not raw.startswith(b"PK"):
        return raw
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        names = set(z.namelist())
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in names:
            return raw
        sheet_xml = z.read(sheet_name).decode("utf-8")
        # 单元格文本通常在 sharedStrings.xml（真实 Excel 保存默认），sheet 内联字符串走 sheet_xml
        shared_name = "xl/sharedStrings.xml"
        shared_xml = z.read(shared_name).decode("utf-8") if shared_name in names else None
        for k, v in var_map.items():
            sheet_xml = sheet_xml.replace(k, v)
            if shared_xml is not None:
                shared_xml = shared_xml.replace(k, v)
        if "</sheetData>" not in sheet_xml:
            return raw
        # 注入段（track_attach=0 时 pixel_url=None → 零外链，仅占位符替换，红线语义）
        sheet_rels = drawing_xml = drawing_rels = None
        if pixel_url is not None:
            # r 命名空间（drawing r:id 前缀）缺失时补在根元素
            if "xmlns:r=" not in sheet_xml:
                sheet_xml = sheet_xml.replace("<worksheet ",
                                              '<worksheet xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ',
                                              1)
            # drawing 必须挂在工作表序列末尾（CT_Worksheet：...pageMargins/pageSetup/
            # headerFooter/.../drawing/.../extLst），真实 Excel 文件 sheetData 后还有
            # pageMargins 等元素，插在 </sheetData> 后会违反顺序 → Office 报"文件损坏"
            # （WPS 容错能开）。extLst 必须最后，drawing 插在 extLst 之前。
            idx = sheet_xml.rfind("</extLst>")
            if idx == -1:
                idx = sheet_xml.rfind("</worksheet>")
            sheet_xml = sheet_xml[:idx] + '<drawing r:id="rIdPhishLabDraw"/>' + sheet_xml[idx:]

            # sheet → drawing 关系（已存在如超链接 rels 时追加）。
            # OPC 规范：part xl/worksheets/sheet1.xml 的关系 part 必须位于
            # xl/worksheets/_rels/sheet1.xml.rels（part 同目录的 _rels 子目录）——
            # 写错路径 Excel/LibreOffice 按规范路径找不到 rels → 无法解析 drawing
            # 引用 → 修复器删除绘图形状；WPS 扫描全包所以能开。
            sheet_rels_name = "xl/worksheets/_rels/sheet1.xml.rels"
            if sheet_rels_name in names:
                sheet_rels = z.read(sheet_rels_name).decode("utf-8")
            else:
                sheet_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                              '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                              "</Relationships>")
            if 'Id="rIdPhishLabDraw"' not in sheet_rels:
                sheet_rels = sheet_rels.replace(
                    "</Relationships>",
                    '<Relationship Id="rIdPhishLabDraw" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
                    'Target="../drawings/drawing1.xml"/></Relationships>')

            # drawing part + 图片外链关系（1×1 像素锚 A1，几乎不可见、打开即加载）。
            # 结构与 openpyxl/Excel 原生生成逐字节一致（oneCellAnchor + from/ext、blip r:link、
            # 内联命名空间、spPr 无 xfrm）——实测 twoCellAnchor 锚定 / spPr 带 xfrm 会被
            # Excel 判为损坏删除形状，oneCellAnchor 结构 + External 外链则完全接受。
            drawing_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<wsDr xmlns="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">'
                '<oneCellAnchor><from><col>0</col><colOff>0</colOff><row>0</row><rowOff>0</rowOff></from>'
                '<ext cx="9525" cy="9525"/>'
                '<pic><nvPicPr><cNvPr id="1" name="beacon" descr="Picture"/><cNvPicPr/></nvPicPr>'
                '<blipFill><a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                'cstate="print" r:link="rId1"/>'
                '<a:stretch xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:fillRect/></a:stretch></blipFill>'
                '<spPr><a:prstGeom xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'prst="rect"/></spPr>'
                '</pic><clientData/></oneCellAnchor></wsDr>'
            )
            drawing_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="{pixel_url}" TargetMode="External"/></Relationships>'
            )

            # [Content_Types].xml 注册 drawing part（缺则跳过，Excel 侧视为文件损坏兜底）
            ct_name = "[Content_Types].xml"
            if ct_name in names:
                ct_xml = z.read(ct_name).decode("utf-8")
                if "/xl/drawings/drawing1.xml" not in ct_xml:
                    ct_xml = ct_xml.replace(
                        "</Types>",
                        '<Override PartName="/xl/drawings/drawing1.xml" '
                        'ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/></Types>')

        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
            for name in names:
                data = z.read(name)
                if name == sheet_name:
                    data = sheet_xml.encode("utf-8")
                elif name == shared_name and shared_xml is not None:
                    data = shared_xml.encode("utf-8")
                elif name == "[Content_Types].xml" and pixel_url is not None and ct_xml is not None:
                    data = ct_xml.encode("utf-8")
                zo.writestr(name, data)
            if pixel_url is not None:
                # 新增 part 统一在循环外写（sheet rels 可能原文件不存在，不能依赖原 names 遍历）
                zo.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet_rels)
                zo.writestr("xl/drawings/drawing1.xml", drawing_xml)
                zo.writestr("xl/drawings/_rels/drawing1.xml.rels", drawing_rels)
        return out.getvalue()
    except Exception:
        return raw


def _load_payload_bytes(payload) -> bytes | None:
    """读取载荷文件字节；缺失返回 None（跳过该附件，不阻断投递）。"""
    try:
        abs_path = Path(settings.static_dir) / (payload.file_path or "")
        return abs_path.read_bytes()
    except OSError:
        return None


def _render_payload_attachments(db, campaign, user, target, token: str,
                                var_map: dict, domain_name: str, track_attach: bool,
                                payload_rows: list | None) -> list[dict]:
    """演练附件载荷 → 每目标变体（docx 个性化 + beacon；其他类型透传）。

    target 非 None（真实目标）：变体落盘 + hash 留痕（溯源/合规证据）。
    target 为 None（测试发送）：不注入 beacon、不落盘，仅透传演示个性化。
    """
    from app.modules.campaign.models import CampaignAttachment
    from app.modules.template.models import AttachmentPayload

    if payload_rows is None:
        payload_rows = db.execute(
            select(CampaignAttachment, AttachmentPayload)
            .join(AttachmentPayload, AttachmentPayload.id == CampaignAttachment.payload_id)
            .where(CampaignAttachment.campaign_id == campaign.id)
            .order_by(CampaignAttachment.sort, CampaignAttachment.id)
        ).all()
    if not payload_rows:
        return []

    # beacon 外链指向独立追踪域（红线 3）；track_attach=0 或测试发送时不注入。
    # 用 /pa/ 专用端点（记 attach_run），与邮件打开像素 /px/（记 open）区分——
    # 同一 URL 无法区分"打开邮件"与"运行附件"，消费端事件维度会错位。
    pixel_url = None
    if user is not None and track_attach:
        pixel_url = f"http://{domain_name}:{settings.landing_port}/pa/{token}.png"

    attachments: list[dict] = []
    for _ca, payload in payload_rows:
        raw = _load_payload_bytes(payload)
        if raw is None:
            continue
        name = payload.name or Path(payload.file_path or "附件").name
        if payload.file_type == "benign_doc" and name.lower().endswith(".docx"):
            raw = _render_docx_variant(raw, var_map, pixel_url)
        elif payload.file_type == "benign_doc" and name.lower().endswith(".xlsx"):
            raw = _render_xlsx_variant(raw, var_map, pixel_url)
        attachments.append({"filename": name, "content": raw, "content_id": None})
        if target is not None:
            variant_rel = Path("uploads/variants") / str(campaign.id) / str(target.id) / name
            abs_variant = Path(settings.static_dir) / variant_rel
            abs_variant.parent.mkdir(parents=True, exist_ok=True)
            abs_variant.write_bytes(raw)
            target.attach_variant_path = str(variant_rel)
            target.attach_variant_hash = hashlib.sha256(raw).hexdigest()
    return attachments


def render_campaign_email(db, campaign, user, token: str, to: str | None = None,
                          assets: dict | None = None, target=None) -> dict:
    """渲染单封演练邮件，返回 {to, subject, html, sender_name, attachments}。

    user 传 None 表示测试发送（收件人非演练目标员工），姓名/部门用演示值。
    target 传 CampaignTarget（真实投递）时附件变体落盘留痕；测试发送不传。
    assets：批次投递预加载的共享实体 {tpl, lp, domain, ch, sp, users, depts, payloads}——
    千人规模批次避免每封重复查询；单封路径不传（走 db 查询）。
    """
    a = assets or {}
    if "tpl" in a:
        tpl = a["tpl"]
    else:
        tpl = db.get(EmailTemplate, campaign.template_id) if campaign.template_id else None
    if "lp" in a:
        lp = a["lp"]
    else:
        lp = db.get(LandingPage, campaign.landing_page_id) if campaign.landing_page_id else None
    if "domain" in a:
        domain = a["domain"]
    else:
        domain = db.get(PhishDomain, campaign.domain_id) if campaign.domain_id else None
    domain_name = domain.domain if domain else "drill-domain.com"
    slug = lp.slug if lp else "demo"
    # 链接追踪开关：开启时走 /t/{token} 短链跳转（记 click → 302 落地页，链接形态更真实，
    # 落地页 slug 不直接暴露在邮件里）；关闭时直连落地页（无 token，点击不计入追踪）
    track_link = tpl.track_link if tpl else 1
    if track_link:
        landing_url = f"http://{domain_name}:{settings.landing_port}/t/{token}"
    else:
        landing_url = f"http://{domain_name}:{settings.landing_port}/p/{slug}"

    dept = None
    if user is not None and user.dept_id:
        depts = a.get("depts") or {}
        if user.dept_id in depts:
            dept = depts[user.dept_id]
        else:
            dept = db.get(EmpDept, user.dept_id)
    var_map = {
        "{{.FirstName}}": user.name if user else "测试收件人",
        "{{.LastName}}": "",
        "{{.Department}}": dept.name if dept else "",
        "{{.Email}}": to or (user.email if user else ""),
        "{{.Date}}": datetime.now().strftime("%Y-%m-%d"),
        "{{.ResetURL}}": landing_url,
    }
    subject = tpl.subject if tpl else f"【通知】{campaign.name}"
    html = tpl.html_body if tpl else f"<p>{campaign.name}</p><p><a href='{landing_url}'>点击处理 →</a></p>"
    for k, v in var_map.items():
        subject = subject.replace(k, v)
        html = html.replace(k, v)

    # 二维码变量：{{.QRCode}} → 落地页链接二维码（附件 + 正文内嵌）
    attachments: list[dict] = []
    if "{{.QRCode}}" in html:
        qr_png = render_qr_png(landing_url)
        attachments.append({
            "filename": "操作指引二维码.png",
            "content": qr_png,
            "content_id": "qr_code",
        })
        html = html.replace(
            "{{.QRCode}}",
            '<div style="margin:16px 0;text-align:center">'
            '<img src="cid:qr_code" width="160" height="160" alt="二维码" '
            'style="border:1px solid #e8e8e8;border-radius:8px" />'
            '<div style="font-size:12px;color:#888;margin-top:6px">'
            '请使用手机扫描上方二维码（或下载附件）完成操作</div></div>',
        )

    # 打开追踪像素（track_pixel=1 时注入）：邮件被查看（客户端加载图片）时记录 open 事件。
    # pixel_degrade=1（像素降级）：以 120×30 正常图片替代 1×1 隐藏像素，防收件人/客户端识别
    track_pixel = tpl.track_pixel if tpl else 1
    if track_pixel:
        if campaign.pixel_degrade:
            pixel_url = f"http://{domain_name}:{settings.landing_port}/px/{token}.png"
            html += (
                f'<img src="{pixel_url}" width="120" height="30" '
                f'style="border:0;display:block;margin-top:8px" alt="" />'
            )
        else:
            pixel_url = f"http://{domain_name}:{settings.landing_port}/px/{token}.gif"
            html += (
                f'<img src="{pixel_url}" width="1" height="1" '
                f'style="border:0;width:1px;height:1px;opacity:0" alt="" />'
            )

    # 附件载荷（一期直发）：campaign_attachment 关联载荷 → 每目标变体 → 追加附件
    track_attach = bool(tpl and tpl.track_attach)  # tpl 为 None（无模板）时视为关闭
    payload_rows = a.get("payloads", _MISSING)
    if payload_rows is _MISSING:
        payload_rows = None  # 单封路径（测试发送）：render 内查询
    attachments += _render_payload_attachments(
        db, campaign, user, target, token, var_map, domain_name, track_attach, payload_rows)

    # 发件人显示名：模板 sender → 通道名 → 演练伪装发件人（display_name/name）
    if "ch" in a:
        ch = a["ch"]
    else:
        ch = db.get(SendChannel, campaign.channel_id) if campaign.channel_id else None
        if ch is None or ch.type != "smtp":
            ch = db.scalar(
                select(SendChannel).where(SendChannel.type == "smtp").order_by(SendChannel.id)
            )
    sender_name = tpl.sender if tpl and tpl.sender else (ch.name if ch else "PhishLab")
    from_addr = None
    reply_to = None
    if campaign.sender_profile_id:
        sp = a.get("sp", _MISSING)
        if sp is _MISSING:
            sp = db.get(SenderProfile, campaign.sender_profile_id)
        if sp:
            sender_name = sp.display_name or sp.name
            from_addr = sp.from_addr or None  # 伪装发件邮箱（收件端 From 头展示）
            reply_to = sp.reply_to or None
    return {
        "to": to or (user.email if user else ""),
        "subject": subject,
        "html": html,
        "sender_name": sender_name,
        "from_addr": from_addr,
        "reply_to": reply_to,
        "attachments": attachments,
    }
