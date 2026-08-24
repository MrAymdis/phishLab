"""附件载荷渲染测试：docx 个性化 + beacon 注入 + 变体落盘留痕 + 测试发送降级。"""
import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.campaign.models import Campaign, CampaignAttachment, CampaignStat, CampaignTarget
from app.modules.campaign.render import render_campaign_email
from app.modules.org.models import EmpDept, EmpRiskProfile, EmpUser
from app.modules.template.models import AttachmentDownloadLog, AttachmentPayload, EmailTemplate
from app.modules.tracking.models import TrackEvent

TOKEN = "a" * 32

DOCX_BODY = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    "<w:body><w:p><w:r><w:t>尊敬的 {{.FirstName}}（{{.Department}}）：</w:t></w:r></w:p></w:body>"
    "</w:document>"
)


def _make_xlsx() -> bytes:
    """最小 xlsx（Content_Types/workbook/sheet1/sharedStrings），供 beacon 注入测试。

    单元格文本放 sharedStrings（真实 Excel 保存默认），占位符替换须作用到该 part。
    sheetData 后带 pageMargins/pageSetup/headerFooter——真实 Office 保存文件的序列，
    drawing 注入必须插在它们之后（CT_Worksheet 顺序约束），否则 Excel 报文件损坏。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                   "</Types>")
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                   'Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
                   'Target="sharedStrings.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">'
                   "<si><t>姓名 {{.FirstName}}（{{.Department}}）</t></si></sst>")
        z.writestr("xl/worksheets/sheet1.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData>'
                   '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" '
                   'header="0.3" footer="0.3"/><pageSetup paperSize="9" orientation="portrait"/>'
                   '<headerFooter/>'
                   "</worksheet>")
    return buf.getvalue()


def _make_docx(body: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # w:sectPr 必须位于 w:body 末尾（真实 Office 文件必有），beacon 段落须插在其前
        z.writestr("word/document.xml", body.replace(
            "</w:body>",
            "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/></w:sectPr></w:body>"))
        z.writestr(
            "word/_rels/document.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>',
        )
        z.writestr("word/style.xml", "<xml/>")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _static_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "static_dir", str(tmp_path))
    yield tmp_path


@pytest.fixture(autouse=True)
def _cleanup():
    """每个用例后清空测试数据：固定邮箱/token 在同库内二次执行会撞唯一约束。"""
    yield
    db = SessionLocal()
    try:
        for m in (TrackEvent, EmpRiskProfile, CampaignTarget, CampaignAttachment,
                  CampaignStat, Campaign, EmpUser, EmpDept, EmailTemplate,
                  AttachmentPayload, AttachmentDownloadLog):
            db.execute(delete(m))
        db.commit()
    finally:
        db.close()


def _setup(db, track_attach: int = 1, file_name: str = "工资条.docx", ext: str = ".docx"):
    tpl = EmailTemplate(name="附件模板", scene="finance", subject="工资条 {{.FirstName}}",
                        html_body="<p>见附件</p>", track_pixel=1, track_link=1,
                        track_attach=track_attach)
    db.add(tpl)
    db.flush()
    dept = EmpDept(name="财务部", parent_id=0, path="/1/")
    db.add(dept)
    db.flush()
    user = EmpUser(name="张三", email="zhangsan@corp.com", dept_id=dept.id)
    db.add(user)
    db.flush()
    c = Campaign(name="附件演练", type="mail", creator_id=1, template_id=tpl.id,
                 target_mode="dept", target_snapshot={})
    db.add(c)
    db.flush()
    payload = AttachmentPayload(name=file_name, file_type="benign_doc",
                                file_path=f"uploads/payloads/_t{ext}", file_hash="x",
                                file_size=10, created_by=1, status="enabled")
    db.add(payload)
    db.flush()
    db.add(CampaignAttachment(campaign_id=c.id, payload_id=payload.id, deliver_mode="inline", sort=0))
    target = CampaignTarget(campaign_id=c.id, user_id=user.id, token=TOKEN)
    db.add(target)
    db.add(CampaignStat(campaign_id=c.id))
    db.commit()
    return c, user, target, payload


def test_docx_variant_personalized_and_beacon(_static_tmp):
    raw = _make_docx(DOCX_BODY)
    db = SessionLocal()
    c, user, target, payload = _setup(db)
    payload_path = Path(_static_tmp) / payload.file_path
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(raw)

    rendered = render_campaign_email(db, c, user, TOKEN, target=target)
    atts = rendered["attachments"]
    assert [a["filename"] for a in atts] == ["工资条.docx"]

    z = zipfile.ZipFile(io.BytesIO(atts[0]["content"]))
    doc = z.read("word/document.xml").decode()
    rels = z.read("word/_rels/document.xml.rels").decode()
    # 个性化：占位符替换
    assert "{{.FirstName}}" not in doc and "{{.Department}}" not in doc
    assert "尊敬的 张三（" in doc
    # beacon：外链关系 + 正文 drawing 引用同一 rid
    assert "rIdPhishLabBeacon" in rels
    assert 'TargetMode="External"' in rels and "/pa/aaa" in rels
    assert "rIdPhishLabBeacon" in doc
    # CT_Body 序列约束：beacon 段落必须在 w:sectPr 之前（sectPr 是 body 最后子元素）
    assert doc.find("<w:drawing>") < doc.find("</w:sectPr>")

    # 变体落盘留痕：路径 + hash + 文件真实存在
    assert target.attach_variant_path == f"uploads/variants/{c.id}/{target.id}/工资条.docx"
    assert target.attach_variant_hash == hashlib.sha256(atts[0]["content"]).hexdigest()
    assert (Path(_static_tmp) / target.attach_variant_path).read_bytes() == atts[0]["content"]
    db.close()


def test_xlsx_variant_beacon(_static_tmp):
    """xlsx 变体：占位符替换 + drawing part 链注入 /pa/ 外链图。"""
    raw = _make_xlsx()
    db = SessionLocal()
    c, user, target, payload = _setup(db, file_name="工资表.xlsx", ext=".xlsx")
    payload_path = Path(_static_tmp) / payload.file_path
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(raw)

    rendered = render_campaign_email(db, c, user, TOKEN, target=target)
    atts = rendered["attachments"]
    assert [a["filename"] for a in atts] == ["工资表.xlsx"]

    z = zipfile.ZipFile(io.BytesIO(atts[0]["content"]))
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    # 个性化：占位符替换（单元格文本在 sharedStrings，替换须作用到该 part）
    ss = z.read("xl/sharedStrings.xml").decode()
    assert "{{.FirstName}}" not in ss and "{{.Department}}" not in ss
    assert "姓名 张三（" in ss
    assert "{{.FirstName}}" not in sheet
    # sheet 挂 drawing 引用
    assert 'rIdPhishLabDraw' in sheet
    # CT_Worksheet 序列约束：drawing 必须在 pageMargins 等打印类元素之后（Excel 严格校验，
    # 插错位置 Office 报"文件损坏"）
    assert sheet.find("<drawing") > sheet.find("<pageMargins")
    # drawing part：外链 beacon（/pa/ 专用端点）
    drawing = z.read("xl/drawings/drawing1.xml").decode()
    assert "rId1" in drawing and "beacon" in drawing
    # 外链图必须 r:link（r:embed 语义是包内媒体，Excel 对 embed+External 会删形状报修复）
    assert 'r:link="rId1"' in drawing
    drawing_rels = z.read("xl/drawings/_rels/drawing1.xml.rels").decode()
    assert 'TargetMode="External"' in drawing_rels and "/pa/aaa" in drawing_rels
    # sheet → drawing 关系（OPC 规范路径：part 同目录 _rels 子目录，写错 Excel 删绘图形状）
    sheet_rels = z.read("xl/worksheets/_rels/sheet1.xml.rels").decode()
    assert "rIdPhishLabDraw" in sheet_rels and "drawing1.xml" in sheet_rels
    # Content_Types 注册 drawing part
    assert "drawing1.xml" in z.read("[Content_Types].xml").decode()

    # 变体落盘留痕
    assert target.attach_variant_path == f"uploads/variants/{c.id}/{target.id}/工资表.xlsx"
    assert target.attach_variant_hash == hashlib.sha256(atts[0]["content"]).hexdigest()
    assert (Path(_static_tmp) / target.attach_variant_path).read_bytes() == atts[0]["content"]
    db.close()


def test_xlsx_no_beacon_when_track_attach_off(_static_tmp):
    """track_attach=0：xlsx 透传零外链（红线语义），仍做占位符替换。"""
    raw = _make_xlsx()
    db = SessionLocal()
    c, user, target, payload = _setup(db, track_attach=0, file_name="工资表.xlsx", ext=".xlsx")
    payload_path = Path(_static_tmp) / payload.file_path
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(raw)

    rendered = render_campaign_email(db, c, user, TOKEN, target=target)
    z = zipfile.ZipFile(io.BytesIO(rendered["attachments"][0]["content"]))
    names = z.namelist()
    assert "xl/drawings/drawing1.xml" not in names  # 无 beacon part
    ss = z.read("xl/sharedStrings.xml").decode()
    assert "姓名 张三（" in ss  # 占位符替换仍生效（零外链，仅个性化）
    assert "{{.FirstName}}" not in ss
    db.close()


def test_no_beacon_when_track_attach_off(_static_tmp):
    raw = _make_docx(DOCX_BODY)
    db = SessionLocal()
    c, user, target, payload = _setup(db, track_attach=0)
    payload_path = Path(_static_tmp) / payload.file_path
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(raw)

    rendered = render_campaign_email(db, c, user, TOKEN, target=target)
    z = zipfile.ZipFile(io.BytesIO(rendered["attachments"][0]["content"]))
    rels = z.read("word/_rels/document.xml.rels").decode()
    assert "rIdPhishLabBeacon" not in rels  # 追踪关闭：零外链零溯源
    assert "张三" in z.read("word/document.xml").decode()  # 个性化仍生效
    db.close()


def test_test_send_no_beacon_no_persist(_static_tmp):
    """测试发送（user=None）：附件透传演示个性化，不注入 beacon、不落变体。"""
    raw = _make_docx(DOCX_BODY)
    db = SessionLocal()
    c, _user, _target, payload = _setup(db)
    payload_path = Path(_static_tmp) / payload.file_path
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(raw)

    rendered = render_campaign_email(db, c, None, "f" * 32, target=None)
    assert [a["filename"] for a in rendered["attachments"]] == ["工资条.docx"]
    z = zipfile.ZipFile(io.BytesIO(rendered["attachments"][0]["content"]))
    rels = z.read("word/_rels/document.xml.rels").decode()
    assert "rIdPhishLabBeacon" not in rels
    assert not (Path(_static_tmp) / "uploads/variants").exists()  # 不落盘
    db.close()


def test_non_docx_passthrough(_static_tmp):
    """pdf 透传：内容一致、无 beacon（一期仅 docx 支持注入）。"""
    raw = b"%PDF-1.4 fake pdf bytes"
    db = SessionLocal()
    c, user, target, payload = _setup(db, file_name="说明.pdf", ext=".pdf")
    payload_path = Path(_static_tmp) / payload.file_path
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(raw)

    rendered = render_campaign_email(db, c, user, TOKEN, target=target)
    assert rendered["attachments"][0]["content"] == raw  # 原样透传
    assert target.attach_variant_hash == hashlib.sha256(raw).hexdigest()
    db.close()
