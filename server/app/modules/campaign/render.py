"""演练邮件渲染：模板变量替换、落地页链接、追踪像素、二维码。

Worker 批量投递与演练「测试发送」共用，保证测试邮件与真实演练邮件内容一致。
"""
from datetime import datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.qr import render_qr_png
from app.modules.channel.models import PhishDomain, SendChannel, SenderProfile
from app.modules.org.models import EmpDept
from app.modules.template.models import EmailTemplate, LandingPage


_MISSING = object()


def render_campaign_email(db, campaign, user, token: str, to: str | None = None,
                          assets: dict | None = None) -> dict:
    """渲染单封演练邮件，返回 {to, subject, html, sender_name, attachments}。

    user 传 None 表示测试发送（收件人非演练目标员工），姓名/部门用演示值。
    assets：批次投递预加载的共享实体 {tpl, lp, domain, ch, sp, users, depts}——
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
    if campaign.sender_profile_id:
        sp = a.get("sp", _MISSING)
        if sp is _MISSING:
            sp = db.get(SenderProfile, campaign.sender_profile_id)
        if sp:
            sender_name = sp.display_name or sp.name
    return {
        "to": to or (user.email if user else ""),
        "subject": subject,
        "html": html,
        "sender_name": sender_name,
        "attachments": attachments,
    }
