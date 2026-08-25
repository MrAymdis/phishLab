"""素材模板服务：邮件模板、落地页、附件载荷、二维码。"""
import ast
import hashlib
import re
import secrets
import uuid
from datetime import datetime
from html import escape as _html_escape
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.config import settings
from app.core.deps import apply_data_scope, get_scoped_or_404
from app.core.errors import BizError, ErrorCode
from app.modules.campaign.models import Campaign, CampaignAttachment, CampaignTarget

from .models import (
    AttachmentDownloadLog,
    AttachmentPayload,
    EmailTemplate,
    LandingFormField,
    LandingPage,
    QrAsset,
)

# 场景 → 中文标签（卡片列表直接消费，未知场景回退原文）
_SCENE_LABELS = {
    "upgrade": "系统升级",
    "system": "系统升级",
    "finance": "财务报销",
    "lottery": "中奖通知",
    "prize": "中奖",
    "hr": "HR通知",
    "alert": "安全告警",
    "security": "安全告警",
    "holiday": "节假日",
}

_PAGE_TYPE_LABELS = {
    "mail_login": "邮箱登录",
    "oa_login": "OA登录",
    "pan_auth": "网盘认证",
    "pay": "支付页面",
    "custom": "自定义",
    "cloned": "克隆页面",
}

_ATTACH_TYPE_LABELS = {
    "benign_doc": "文档附件",
    "macro_doc": "宏文档",
    "exe": "可执行文件",
    "qr": "二维码",
    "other": "其他",
}

# 一期良性文档白名单；宏/EXE 载荷默认关闭（License 门控，红线 6）
_ALLOWED_PAYLOAD_EXTS = {".docx", ".xlsx", ".pdf", ".zip"}
# 宏/EXE 载荷扩展名：红线 6 仅旗舰版授权后开放（payload_enabled 门控）
_EXEC_PAYLOAD_EXTS = {".exe", ".msi", ".bat", ".scr", ".cmd"}
_MACRO_PAYLOAD_EXTS = {".docm", ".xlsm", ".pptm", ".xlsb", ".dotm"}
_MAX_PAYLOAD_MB = 20


def payload_enabled(db) -> bool:
    """宏/EXE 载荷功能开关（红线 6 默认关闭）：仅旗舰版授权且未过期开放。

    与其他功能不同，不享受"无 license 放行"的开发便利——高危载荷必须显式授权。
    与 license 模块 EDITION_FEATURES["flagship"]["payload"] 保持一致。
    """
    from app.modules.license.models import LicenseInfo

    lic = db.scalar(select(LicenseInfo).order_by(LicenseInfo.id.desc()))
    if lic is None or lic.status != "active":
        return False
    if lic.expire_at and lic.expire_at < datetime.now():
        return False
    return lic.edition == "flagship"

_VAR_RE = re.compile(r"\{\{\.\w+\}\}")


def list_email_templates(db, account, scene=None) -> list[dict]:
    """模板卡片列表（无分页），按使用次数倒序。

    使用次数/点击率为实时聚合（引用该模板的演练增删后自动正确）：
    - used  = 引用该模板的演练场次（campaign.template_id 计数）
    - click = 点击人次（campaign_target.click_count>0 去重）/ 目标人次 × 100
    """
    stmt = select(EmailTemplate)
    stmt = apply_data_scope(db, stmt, account, self_owner_col=EmailTemplate.created_by,
                            allow_null_owner=True)  # 平台内置模板 created_by IS NULL 全员可见
    if scene:
        stmt = stmt.where(EmailTemplate.scene == scene)
    rows = db.scalars(stmt).all()
    tpl_ids = [t.id for t in rows]

    used_map: dict[int, int] = {}
    target_map: dict[int, int] = {}
    click_map: dict[int, int] = {}
    if tpl_ids:
        used_map = dict(db.execute(
            select(Campaign.template_id, func.count(Campaign.id))
            .where(Campaign.template_id.in_(tpl_ids))
            .group_by(Campaign.template_id)
        ).all())
        agg = db.execute(
            select(
                Campaign.template_id,
                func.count(CampaignTarget.id),
                func.count(func.if_(CampaignTarget.click_count > 0, 1, None)),
            )
            .join(CampaignTarget, CampaignTarget.campaign_id == Campaign.id)
            .where(Campaign.template_id.in_(tpl_ids))
            .group_by(Campaign.template_id)
        ).all()
        target_map = {t: (trg or 0) for t, trg, _ in agg}
        click_map = {t: (clk or 0) for t, _, clk in agg}

    items = []
    for t in rows:
        targets = target_map.get(t.id, 0)
        clicks = click_map.get(t.id, 0)
        click_rate = round(clicks / targets * 100, 2) if targets else 0.0
        items.append({
            "id": t.id,
            "name": t.name,
            "cat": t.scene,
            "catText": _SCENE_LABELS.get(t.scene, t.scene),
            "subject": t.subject,
            "sender": t.sender,
            "stars": t.stars,
            "used": used_map.get(t.id, 0),
            "click": click_rate,
            "preview": f"{t.subject[:24]}…" if len(t.subject) > 24 else t.subject,
            "created_at": t.created_at.strftime("%Y-%m-%d") if t.created_at else "",
            "track_pixel": bool(t.track_pixel),
            "track_link": bool(t.track_link),
            "track_attach": bool(t.track_attach),
        })
    return sorted(items, key=lambda i: i["used"], reverse=True)


def create_email_template(db, account, payload: dict) -> int:
    """富文本模板：正则抽取 {{.变量}} 清单；AI 来源须走 ai_draft 审核流。"""
    variables = list(dict.fromkeys(_VAR_RE.findall(payload.get("html_body") or "")))
    tpl = EmailTemplate(
        name=payload["name"],
        scene=payload.get("scene") or "",
        subject=payload["subject"],
        html_body=payload.get("html_body") or "",
        variables=variables,
        source=payload.get("source") or "custom",
        status="approved",
        created_by=account.id,
        sender=None,
        stars=2,
        track_pixel=int(payload.get("track_pixel", True)),
        track_link=int(payload.get("track_link", True)),
        track_attach=int(payload.get("track_attach", False)),
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    record_audit(
        db, account=account, module="template", action="create_template",
        target_type="email_template", target_id=tpl.id,
    )
    return tpl.id


def duplicate_email_template(db, account, template_id: int) -> int:
    """复制模板：生成同名（副本）的新模板，使用计数归零。"""
    t = get_scoped_or_404(db, account, EmailTemplate, template_id,
                          self_owner_col=EmailTemplate.created_by, allow_null_owner=True,
                          msg="模板不存在")
    new = EmailTemplate(
        name=f"{t.name}（副本）",
        scene=t.scene,
        subject=t.subject,
        html_body=t.html_body,
        variables=t.variables or [],
        source="custom",
        status="approved",
        created_by=account.id,
        sender=t.sender,
        stars=t.stars,
        track_pixel=t.track_pixel,
        track_link=t.track_link,
        track_attach=t.track_attach,
        used_count=0,
        click_rate=0,
    )
    db.add(new)
    db.commit()
    record_audit(
        db, account=account, module="template", action="duplicate_template",
        target_type="email_template", target_id=str(new.id), detail={"source_id": template_id},
    )
    return new.id


def duplicate_landing_page(db, account, page_id: int) -> int:
    """复制落地页：复制页面与表单字段，生成新 slug。"""
    p = get_scoped_or_404(db, account, LandingPage, page_id,
                          self_owner_col=LandingPage.created_by, allow_null_owner=True,
                          msg="落地页不存在")
    new = LandingPage(
        name=f"{p.name}（副本）",
        type=p.type,
        slug=secrets.token_hex(6),
        html_content=p.html_content,
        page_schema=p.page_schema,
        form_schema=p.form_schema,
        source="custom",
        clone_from_url=p.clone_from_url,
        status=p.status,
        created_by=account.id,
        used_count=0,
    )
    db.add(new)
    db.flush()
    for f in db.scalars(
        select(LandingFormField).where(LandingFormField.page_id == page_id).order_by(LandingFormField.sort)
    ).all():
        db.add(LandingFormField(
            page_id=new.id, field_key=f.field_key, label=f.label,
            input_type=f.input_type, sensitive_flag=f.sensitive_flag, sort=f.sort,
        ))
    db.commit()
    record_audit(
        db, account=account, module="template", action="duplicate_landing_page",
        target_type="landing_page", target_id=str(new.id), detail={"source_id": page_id},
    )
    return new.id


def get_email_template(db, account, template_id: int) -> dict:
    """获取邮件模板详情（含 html_body 全文）。"""
    t = get_scoped_or_404(db, account, EmailTemplate, template_id,
                          self_owner_col=EmailTemplate.created_by, allow_null_owner=True,
                          msg="模板不存在")
    return {
        "id": t.id,
        "name": t.name,
        "scene": t.scene,
        "cat": t.scene,
        "catText": _SCENE_LABELS.get(t.scene, t.scene),
        "subject": t.subject,
        "html_body": t.html_body or "",
        "body": t.html_body or "",
        "sender": t.sender or "",
        "stars": t.stars,
        "used_count": t.used_count,
        "variables": t.variables or [],
        "source": t.source,
        "status": t.status,
        "track_pixel": bool(t.track_pixel),
        "track_link": bool(t.track_link),
        "track_attach": bool(t.track_attach),
        "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
    }


def update_email_template(db, account, template_id: int, payload: dict) -> None:
    """更新邮件模板：重新抽取变量，写审计。"""
    t = get_scoped_or_404(db, account, EmailTemplate, template_id,
                          self_owner_col=EmailTemplate.created_by, allow_null_owner=True,
                          msg="模板不存在")
    if "name" in payload:
        t.name = payload["name"]
    if "scene" in payload:
        t.scene = payload["scene"]
    if "subject" in payload:
        t.subject = payload["subject"]
    if "html_body" in payload:
        t.html_body = payload["html_body"]
        t.variables = list(dict.fromkeys(_VAR_RE.findall(payload["html_body"] or "")))
    if "sender" in payload:
        t.sender = payload["sender"]
    if "stars" in payload:
        t.stars = payload["stars"]
    for key in ("track_pixel", "track_link", "track_attach"):
        if key in payload:
            setattr(t, key, int(payload[key]))
    db.commit()
    record_audit(
        db, account=account, module="template", action="update_template",
        target_type="email_template", target_id=t.id,
    )


def delete_email_template(db, account, template_id: int) -> None:
    """删除邮件模板；被演练引用时阻止（防演练历史悬空）。"""
    t = get_scoped_or_404(db, account, EmailTemplate, template_id,
                          self_owner_col=EmailTemplate.created_by, allow_null_owner=True,
                          msg="模板不存在")
    if db.scalar(select(Campaign.id).where(Campaign.template_id == template_id).limit(1)):
        raise BizError(ErrorCode.BIZ_CONFLICT, "模板已被演练引用，无法删除")
    db.delete(t)
    db.commit()
    record_audit(
        db, account=account, module="template", action="delete_template",
        target_type="email_template", target_id=template_id, detail={"name": t.name},
    )


def test_send_template(db, account, template_id: int, to: list[str]) -> dict:
    """模板测试发送：渲染模板（演示变量）→ 默认 SMTP 通道逐收件人真实投递。

    收件人白名单由前端弹窗约束（管理员手输）；未配置可用 SMTP 通道时明确报错，不再假成功。
    """
    from app.core.config import settings
    from app.modules.channel import service as channel_service
    from app.modules.channel.models import SendChannel

    tpl = get_scoped_or_404(db, account, EmailTemplate, template_id,
                            self_owner_col=EmailTemplate.created_by, allow_null_owner=True,
                            msg="模板不存在")
    if not to:
        raise BizError(ErrorCode.PARAM_INVALID, "请提供测试收件人")

    channel = db.scalar(
        select(SendChannel)
        .where(SendChannel.type == "smtp", SendChannel.status != "disabled")
        .order_by(SendChannel.is_default.desc(), SendChannel.id)
    )
    if channel is None:
        raise BizError(ErrorCode.BIZ_CONFLICT, "未配置可用 SMTP 通道，请先在「发送配置」添加并测试通过")

    # 变量替换（演示值；真实演练按目标员工档案逐人渲染）
    base_map = {
        "{{.FirstName}}": "测试收件人",
        "{{.LastName}}": "演示",
        "{{.Department}}": "安全演练测试",
        "{{.Date}}": datetime.now().strftime("%Y-%m-%d"),
        "{{.ResetURL}}": f"{settings.landing_base_url.rstrip('/')}/p/demo",
        "{{.QRCode}}": f"{settings.landing_base_url.rstrip('/')}/p/demo",
    }
    results = []
    for addr in to:
        var_map = {**base_map, "{{.Email}}": addr}
        subject = tpl.subject or ""
        html = tpl.html_body or ""
        for k, v in var_map.items():
            subject = subject.replace(k, v)
            html = html.replace(k, v)
        try:
            r = channel_service.send_html_email(db, account, channel.id, addr, subject, html)
        except BizError as e:
            r = {"ok": False, "message": str(e)}
        results.append({"to": addr, **r})
    ok_n = sum(1 for r in results if r["ok"])
    record_audit(
        db, account=account, module="template", action="test_send",
        target_type="email_template", target_id=template_id,
        detail={"to": to, "ok": ok_n, "channel_id": channel.id},
    )
    if ok_n == len(results):
        message = f"测试邮件已发送至 {len(to)} 个收件人"
    else:
        message = f"成功 {ok_n}/{len(to)}，失败原因：{next(r['message'] for r in results if not r['ok'])}"
    return {"ok": ok_n == len(results), "message": message, "results": results}


def list_landing_pages(db, account) -> list[dict]:
    """落地页列表（无分页），字段数聚合自 landing_form_field。

    used 为实时聚合：引用该落地页的演练场次（campaign.landing_page_id 计数）。
    """
    stmt = select(LandingPage).order_by(LandingPage.id.desc())
    stmt = apply_data_scope(db, stmt, account, self_owner_col=LandingPage.created_by,
                            allow_null_owner=True)
    pages = db.scalars(stmt).all()
    if not pages:
        return []
    ids = [p.id for p in pages]
    counts = dict(
        db.execute(
            select(LandingFormField.page_id, func.count(LandingFormField.id))
            .where(LandingFormField.page_id.in_(ids))
            .group_by(LandingFormField.page_id)
        ).all()
    )
    used_map = dict(db.execute(
        select(Campaign.landing_page_id, func.count(Campaign.id))
        .where(Campaign.landing_page_id.in_(ids))
        .group_by(Campaign.landing_page_id)
    ).all())
    result = []
    for p in pages:
        fields = counts.get(p.id, 0)
        fs = p.form_schema or {}
        # 收集项 = 表单 schema 定义的字段数（与落库行数互为印证，无定义回退行数）
        schema_fields = (fs.get("fields") or []) if fs else []
        collect = len(schema_fields) if schema_fields else fields
        result.append(
            {
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "source": p.source,
                "typeText": _PAGE_TYPE_LABELS.get(p.type, p.type),
                "fields": fields,
                "collect": collect,
                "used": used_map.get(p.id, 0),
                "created_at": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
            }
        )
    return result


_LANDING_TYPE_HTML: dict[str, str] = {
    "mail_login": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{PAGE_NAME}}</title>
<style>body{font-family:'Segoe UI',Arial,sans-serif;background:#f3f6fb;margin:0;padding:40px 20px}
.login-box{max-width:380px;margin:80px auto;background:#fff;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,0.08);padding:40px 32px}
.logo{text-align:center;font-size:20px;font-weight:600;color:#0078d4;margin-bottom:8px}
.sub{text-align:center;color:#666;font-size:13px;margin-bottom:28px}
label{display:block;font-size:13px;color:#333;margin-bottom:6px}
input[type=text],input[type=password]{width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:4px;font-size:14px;box-sizing:border-box;margin-bottom:16px}
input:focus{border-color:#0078d4;outline:none}
button{width:100%;background:#0078d4;color:#fff;border:none;padding:11px;border-radius:4px;font-size:15px;cursor:pointer;margin-top:8px}
button:hover{background:#106ebe}
.footer{text-align:center;margin-top:24px;font-size:11px;color:#999}
</style></head><body>
<div class="login-box">
<div class="logo">🔒 {{PAGE_NAME}}</div>
<div class="sub">请登录以继续</div>
<form>
<label>用户名 / 邮箱</label>
<input type="text" placeholder="请输入用户名">
<label>密码</label>
<input type="password" placeholder="请输入密码">
<button type="submit">登 录</button>
</form>
<div class="footer">© 2026 {{PAGE_NAME}} · 安全登录</div>
</div></body></html>""",
    "oa_login": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{PAGE_NAME}}</title>
<style>body{font-family:'Microsoft YaHei',Arial,sans-serif;background:#f0f2f5;margin:0;padding:0}
.top-bar{background:#1a73e8;color:#fff;padding:14px 32px;font-size:15px;font-weight:500}
.login-box{max-width:400px;margin:60px auto;background:#fff;border-radius:6px;box-shadow:0 2px 12px rgba(0,0,0,0.1);padding:48px 40px}
.logo{text-align:center;font-size:22px;font-weight:600;color:#1a73e8;margin-bottom:6px}
.sub{text-align:center;color:#888;font-size:13px;margin-bottom:32px}
label{display:block;font-size:13px;color:#555;margin-bottom:6px}
input[type=text],input[type=password]{width:100%;padding:11px 14px;border:1px solid #e0e0e0;border-radius:4px;font-size:14px;box-sizing:border-box;margin-bottom:18px}
input:focus{border-color:#1a73e8;outline:none}
.captcha{display:flex;gap:12px;margin-bottom:8px}
.captcha input{flex:1}
.captcha-img{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:8px 16px;border-radius:4px;font-size:18px;font-weight:700;letter-spacing:2px;user-select:none}
button{width:100%;background:#1a73e8;color:#fff;border:none;padding:12px;border-radius:4px;font-size:15px;cursor:pointer;margin-top:12px}
button:hover{background:#1557b0}
.footer{text-align:center;margin-top:20px;font-size:11px;color:#aaa}
</style></head><body>
<div class="top-bar">企业统一认证系统</div>
<div class="login-box">
<div class="logo">{{PAGE_NAME}}</div>
<div class="sub">账号登录</div>
<form>
<label>账号</label>
<input type="text" placeholder="请输入工号或邮箱">
<label>密码</label>
<input type="password" placeholder="请输入密码">
<div class="captcha"><input type="text" placeholder="验证码"><div class="captcha-img">A3Kx</div></div>
<button type="submit">登 录</button>
</form>
<div class="footer">© 2026 {{PAGE_NAME}}</div>
</div></body></html>""",
    "pan_auth": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{PAGE_NAME}}</title>
<style>body{font-family:'Helvetica Neue',Arial,sans-serif;background:#fafafa;margin:0;padding:60px 20px}
.card{max-width:360px;margin:40px auto;background:#fff;border:1px solid #e8e8e8;border-radius:4px;padding:40px 32px}
.logo{text-align:center;font-size:18px;font-weight:600;color:#333;margin-bottom:4px}
.sub{text-align:center;color:#999;font-size:12px;margin-bottom:24px}
label{display:block;font-size:13px;color:#555;margin-bottom:6px}
input[type=text],input[type=password]{width:100%;padding:9px 12px;border:1px solid #d9d9d9;border-radius:3px;font-size:14px;box-sizing:border-box;margin-bottom:16px}
input:focus{border-color:#1890ff;outline:none;box-shadow:0 0 0 2px rgba(24,144,255,0.2)}
button{width:100%;background:#1890ff;color:#fff;border:none;padding:10px;border-radius:3px;font-size:14px;cursor:pointer}
button:hover{background:#40a9ff}
.tip{text-align:center;margin-top:16px;font-size:12px;color:#faad14}
.footer{text-align:center;margin-top:20px;font-size:11px;color:#bbb}
</style></head><body>
<div class="card">
<div class="logo">☁️ {{PAGE_NAME}}</div>
<div class="sub">身份验证中心</div>
<form>
<label>账号</label>
<input type="text" placeholder="请输入账号">
<label>密码</label>
<input type="password" placeholder="请输入密码">
<button type="submit">登录验证</button>
</form>
<div class="tip">⚠ 您的账号将在3分钟后过期，请及时完成身份验证</div>
</div>
<div class="footer">© 2026 {{PAGE_NAME}}</div>
</body></html>""",
    "custom": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{PAGE_NAME}}</title>
<style>body{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:40px 20px}
.box{max-width:420px;margin:60px auto;background:#fff;border-radius:8px;padding:40px 36px;box-shadow:0 2px 16px rgba(0,0,0,0.06)}
.title{text-align:center;font-size:20px;font-weight:600;color:#333;margin-bottom:8px}
.desc{text-align:center;color:#888;font-size:13px;margin-bottom:28px}
label{display:block;font-size:13px;color:#444;margin-bottom:6px}
input,select{width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:4px;font-size:14px;box-sizing:border-box;margin-bottom:16px}
button{width:100%;background:#378ADD;color:#fff;border:none;padding:11px;border-radius:4px;font-size:15px;cursor:pointer}
button:hover{opacity:0.9}
.footer{text-align:center;margin-top:16px;font-size:11px;color:#bbb}
</style></head><body>
<div class="box">
<div class="title">{{PAGE_NAME}}</div>
<div class="desc">请完成以下信息提交</div>
<form>
<label>姓名</label><input type="text" placeholder="请输入您的姓名">
<label>工号</label><input type="text" placeholder="请输入工号">
<label>部门</label><input type="text" placeholder="请输入所属部门">
<button type="submit">提交信息</button>
</form>
<div class="footer">© 2026 {{PAGE_NAME}}</div>
</div></body></html>""",
}


def _default_landing_html(page_type: str, page_name: str) -> str:
    """根据落地页类型生成默认 HTML 模板。"""
    template = _LANDING_TYPE_HTML.get(page_type, _LANDING_TYPE_HTML["custom"])
    return template.replace("{{PAGE_NAME}}", page_name)


def normalize_cloned_html(html: str) -> str:
    """克隆页面 HTML 规范化：目标站服务端模板标签 → 相对路径/移除。

    Coremail 等邮件系统的登录页含服务端渲染标签，如
    `<img src="{{customLpImg facade_custom.logo 'assets/.../logo.png'}}">`，
    裸抓取后无法渲染（坏图）。带单引号路径的标签替换为裸路径
    （配合页面已有 <base> 解析）；无路径的标签连同所在 <img> 元素一并移除。
    """
    html = re.sub(r"\{\{\s*[A-Za-z]+[^}]*?'([^']+)'[^}]*\}\}", r"\1", html)
    html = re.sub(
        r"<img\b[^>]*src\s*=\s*[\"'][^\"']*\{\{[^}]*\}\}[^\"']*[\"'][^>]*(?:/>|>\s*</img>)",
        "",
        html,
        flags=re.I,
    )
    return html


# ==================== 克隆页静态渲染与消毒（落地页服务 / 预览接口共用） ====================

FP_SCRIPT = """<script>
(function () {
  function h(s) {
    var x = 2166136261;
    for (var i = 0; i < s.length; i++) { x ^= s.charCodeAt(i); x = Math.imul(x, 16777619); }
    return (x >>> 0).toString(16);
  }
  var n = navigator || {};
  var s = window.screen || {};
  var fp = {
    ua: n.userAgent || '',
    lang: n.language || '',
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    screen: (s.width || 0) + 'x' + (s.height || 0) + 'x' + (s.colorDepth || 0),
    cores: (n.hardwareConcurrency || 0),
    touch: ('ontouchstart' in window) ? 1 : 0,
    mem: (n.deviceMemory || 0)
  };
  try {
    var c = document.createElement('canvas');
    var ctx = c.getContext('2d');
    if (ctx) {
      var txt = 'PhishLab👤✉️🎣 Cwm fjordbank glyphs vext quiz';
      ctx.textBaseline = 'top'; ctx.font = '14px Arial';
      ctx.fillStyle = '#f60'; ctx.fillRect(120, 1, 80, 20);
      ctx.fillStyle = '#069'; ctx.fillText(txt, 2, 15);
      fp.canvas = h(c.toDataURL());
      var gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (gl) {
        try {
          var dbg = gl.getExtension('WEBGL_debug_renderer_info');
          fp.webgl = dbg ? (gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || '') : (gl.getParameter(gl.RENDERER) || '');
        } catch (e) { fp.webgl = ''; }
      }
      var fonts = ['Arial', 'Verdana', 'Tahoma', 'Georgia', 'Times New Roman', 'Courier New',
        'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'SimSun', 'SimHei', 'WenQuanYi Zen Hei'];
      ctx.font = '72px monospace';
      var base = ctx.measureText(txt).width;
      var found = [];
      for (var i = 0; i < fonts.length; i++) {
        ctx.font = '72px ' + fonts[i] + ', monospace';
        if (Math.abs(ctx.measureText(txt).width - base) > 0.5) found.push(fonts[i]);
      }
      fp.fonts = h(found.join(','));
    }
  } catch (e) {}
  var el = document.getElementById('fp-input');
  if (el) el.value = JSON.stringify(fp);
})();
</script>"""

# {{{expr}}} 原样插值 | {{expr}} 转义插值 | {{#if}}...{{^}}...{{/if}} 等块标签
_HBS_TOKEN_RE = re.compile(r"\{\{\{(.*?)\}\}\}|\{\{(.*?)\}\}", re.S)


def _extract_js_object(html: str, name: str):
    """提取 `NAME = { ... };` 纯数据 JS 对象字面量 → Python dict；失败返回 None。"""
    m = re.search(rf"\b{re.escape(name)}\s*=\s*", html)
    if m is None:
        return None
    i = html.find("{", m.end())
    if i < 0:
        return None
    depth, j, quote = 0, i, None
    while j < len(html):
        c = html[j]
        if quote:
            if c == "\\":
                j += 2
                continue
            if c == quote:
                quote = None
        elif c in ("'", '"'):
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return _js_literal_to_py(html[i : j + 1])
        j += 1
    return None


def _js_literal_to_py(text: str):
    """JS 字面量 → Python 字面量：仅替换引号外的 true/false/null，不动字符串值。"""
    buf, i, quote = [], 0, None
    while i < len(text):
        c = text[i]
        if quote:
            buf.append(c)
            if c == "\\" and i + 1 < len(text):
                buf.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in ("'", '"'):
            quote = c
            buf.append(c)
        else:
            m = re.match(r"\b(true|false|null)\b", text[i:])
            if m:
                buf.append({"true": "True", "false": "False", "null": "None"}[m.group(1)])
                i += len(m.group(1))
                continue
            buf.append(c)
        i += 1
    try:
        return ast.literal_eval("".join(buf))
    except (SyntaxError, ValueError):
        return None


def _unescape_js_string(s: str) -> str:
    """反转义 JS 字符串（\\n \\t \\r \\' \\\" \\\\ \\/ \\uXXXX）。"""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "n":
                out.append("\n")
            elif n == "t":
                out.append("\t")
            elif n == "r":
                out.append("\r")
            elif n == "u" and i + 6 <= len(s):
                try:
                    out.append(chr(int(s[i + 2 : i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    out.append(n)
            else:
                out.append(n)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _extract_hbs_templates(html: str) -> dict:
    """提取 SYS_CONST.templates 的 Handlebars 模板（logoTpl/contentTpl/asideTpl）。"""
    m = re.search(r"\bSYS_CONST\s*=\s*\{", html)
    if m is None:
        return {}
    i = html.find("templates:", m.end())
    j = html.find("{", i) if i >= 0 else -1
    if j < 0:
        return {}
    depth, k, quote = 0, j, None
    while k < len(html):
        c = html[k]
        if quote:
            if c == "\\":
                k += 2
                continue
            if c == quote:
                quote = None
        elif c in ("'", '"'):
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    block = html[j : k + 1]
    result = {}
    for key in ("logoTpl", "contentTpl", "asideTpl"):
        m2 = re.search(rf"'{key}':\s*'((?:[^'\\]|\\.)*)'", block, re.S)
        if m2:
            result[key] = _unescape_js_string(m2.group(1))
    return result


def _extract_x_root(html: str) -> str:
    """提取 X 配置的上下文根 r（Coremail 资源前缀，默认 /coremail）。"""
    m = re.search(r"\bX\s*=\s*\{", html)
    if m is None:
        return "/coremail"
    m2 = re.search(r"\br\s*:\s*'(/[^']*)'", html[m.end() : m.end() + 900])
    return m2.group(1) if m2 else "/coremail"


def _resolve_path(path: str, stack: list):
    """Handlebars 路径解析：a.b.c、../a、.、..；缺失时向父级上下文逐层回退。"""
    p = path.strip()
    ctxs = list(stack)
    while p.startswith("../"):
        p = p[3:]
        if len(ctxs) > 1:
            ctxs.pop()
    if p in ("", ".", "this"):
        return ctxs[-1] if ctxs else None
    if p.startswith(".."):
        p = p[2:].lstrip(".")
        if len(ctxs) > 1:
            ctxs.pop()
        if p in ("", "this"):
            return ctxs[-1] if ctxs else None
    segs = [s for s in p.split(".") if s not in ("", "this")]
    if not segs:
        return None
    for ctx in reversed(ctxs):
        cur = ctx
        for seg in segs:
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                cur = None
                break
        if cur is not None:
            return cur
    return None


def _eval_arg(token: str, stack: list):
    """求值 {{expr}} 实参：路径 / 字符串 / true/false/null / 数字。"""
    t = token.strip()
    if t in ("true", "True"):
        return True
    if t in ("false", "False"):
        return False
    if t in ("null", "None"):
        return None
    if len(t) >= 2 and ((t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"'))):
        try:
            return ast.literal_eval(t)
        except (SyntaxError, ValueError):
            return t[1:-1]
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t) if "." in t else int(t)
    return _resolve_path(t, stack)


def _split_args(body: str) -> list[str]:
    """按空白拆分 helper 实参，尊重引号。"""
    args, cur, quote = [], [], None
    i = 0
    while i < len(body):
        c = body[i]
        if quote:
            cur.append(c)
            if c == "\\" and i + 1 < len(body):
                cur.append(body[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in ("'", '"'):
            quote = c
            cur.append(c)
        elif c.isspace():
            if cur:
                args.append("".join(cur))
                cur = []
        else:
            cur.append(c)
        i += 1
    if cur:
        args.append("".join(cur))
    return args


def _hbs_falsy(value) -> bool:
    """Handlebars isEmpty 语义：None/False/空串/空数组为假（0 与 {} 为真）。"""
    return value is None or value is False or value == "" or (isinstance(value, list) and not value)


def _hbs_split_block(template: str, start: int, close_name: str) -> tuple[str, str, int]:
    """在 start 之后查找配对的 {{/close_name}}，支持 {{^}}/{{else}} 分支与块嵌套。"""
    depth = 0
    else_pos = None
    for m in _HBS_TOKEN_RE.finditer(template, start):
        body = (m.group(1) or m.group(2) or "").strip()
        if body.startswith("#"):
            depth += 1
        elif body.startswith("/"):
            if depth == 0:
                if else_pos:
                    return template[start : else_pos[0]], template[else_pos[1] : m.start()], m.end()
                return template[start : m.start()], "", m.end()
            depth -= 1
        elif body in ("^", "else") and depth == 0:
            if else_pos is None:
                else_pos = (m.start(), m.end())
    return template[start:], "", len(template)


def _hbs_render(template: str, stack: list, partials: dict, helpers: dict) -> str:
    """迷你 Handlebars 渲染器：#if/#unless/#each/#with、^ 分支、> 局部模板、helper 与插值。"""
    out, pos = [], 0
    while True:
        m = _HBS_TOKEN_RE.search(template, pos)
        if m is None:
            out.append(template[pos:])
            break
        out.append(template[pos : m.start()])
        raw = m.group(1) is not None  # {{{expr}}} 原样插值
        body = (m.group(1) or m.group(2) or "").strip()
        pos = m.end()
        if body.startswith("!") or body in ("^", "else"):
            continue
        if body.startswith("#if "):
            branch_t, branch_f, end = _hbs_split_block(template, m.end(), "/if")
            if not _hbs_falsy(_eval_arg(body[4:], stack)):
                out.append(_hbs_render(branch_t, stack, partials, helpers))
            else:
                out.append(_hbs_render(branch_f, stack, partials, helpers))
            pos = end
        elif body.startswith("#unless "):
            branch_t, branch_f, end = _hbs_split_block(template, m.end(), "/unless")
            if _hbs_falsy(_eval_arg(body[8:], stack)):
                out.append(_hbs_render(branch_t, stack, partials, helpers))
            else:
                out.append(_hbs_render(branch_f, stack, partials, helpers))
            pos = end
        elif body.startswith("#each "):
            branch_t, branch_f, end = _hbs_split_block(template, m.end(), "/each")
            value = _eval_arg(body[6:], stack)
            items = value.values() if isinstance(value, dict) else (value if isinstance(value, list) else [])
            if items:
                for item in items:
                    out.append(_hbs_render(branch_t, stack + [item], partials, helpers))
            else:
                out.append(_hbs_render(branch_f, stack, partials, helpers))
            pos = end
        elif body.startswith("#with "):
            branch_t, branch_f, end = _hbs_split_block(template, m.end(), "/with")
            value = _eval_arg(body[6:], stack)
            if not _hbs_falsy(value):
                out.append(_hbs_render(branch_t, stack + [value], partials, helpers))
            else:
                out.append(_hbs_render(branch_f, stack, partials, helpers))
            pos = end
        elif body.startswith(">"):
            name = body[1:].strip()
            tpl = partials.get(name)
            if tpl:
                out.append(_hbs_render(tpl, stack, partials, helpers))
        else:
            parts = _split_args(body)
            if parts and parts[0] in helpers:
                rendered = helpers[parts[0]](*[_eval_arg(a, stack) for a in parts[1:]])
                out.append("" if rendered is None else str(rendered))
            else:
                value = _eval_arg(body, stack)
                text = "" if value is None else str(value)
                out.append(text if raw else _html_escape(text))
    return "".join(out)


def _render_coremail_shell(html: str) -> str:
    """Coremail 等 JS 渲染登录页静态化（原站 login 入口 chunk 的等价渲染）。

    这类登录页的 HTML 只有空壳 div（.content/.aside/.main-middle/.main-bottom），
    内容由 JS 用 Handlebars 模板（SYS_CONST.templates）+ 数据（CUSTOME_DATA）
    渲染。剥离脚本后只剩空壳，与原文视觉差异巨大。此处把模板渲染进
    .content/.aside，自定义背景/按钮/标语落到 .main-bottom/.u-btn/.slogan
    内联样式；logo/背景图仍热链原站（配合页面 <base> 解析）。
    无 CUSTOME_DATA/SYS_CONST 标记的页面原样返回。
    """
    data = _extract_js_object(html, "CUSTOME_DATA")
    templates = _extract_hbs_templates(html)
    if not data or "indexPageData2" not in data or not templates:
        return html
    ipd = data.get("indexPageData2") or {}
    res = ipd.get("real_resource") or {}
    x_root = _extract_x_root(html)

    def lp_img(name):
        if isinstance(name, list):
            if not name:
                return None
            nm = name[0]
        else:
            nm = name
        if not nm:
            return None
        q = "site=1" if ipd.get("site") else f"org_id={ipd.get('org') or ''}"
        return f"{x_root}/s?func=lp:getImg&{q}&img_id={nm}"

    helpers = {"customLpImg": lambda name, fallback="": lp_img(name) or fallback}
    stack = [res]
    content_html = _hbs_render(templates.get("contentTpl", ""), stack, templates, helpers)
    aside_html = _hbs_render(templates.get("asideTpl", ""), stack, templates, helpers)

    html = re.sub(
        r'<div\b[^>]*class\s*=\s*["\']content["\'][^>]*>\s*</div>',
        f'<div class="content">{content_html}</div>',
        html,
        count=1,
        flags=re.I | re.S,
    )
    html = re.sub(
        r'<div\b[^>]*class\s*=\s*["\']aside["\'][^>]*>\s*</div>',
        f'<div class="aside">{aside_html}</div>',
        html,
        count=1,
        flags=re.I | re.S,
    )

    fc = res.get("facade_custom") or {}
    bg = lp_img(fc.get("background"))
    if bg or fc.get("background_color"):
        styles = []
        if fc.get("background_color"):
            styles.append(f"background-color:{fc['background_color']}")
        if bg:
            styles.append(f"background-image:url('{bg}')")
        html = re.sub(
            r'<div\b[^>]*class\s*=\s*["\']main-bottom["\'][^>]*>',
            f'<div class="main-bottom" style="{";".join(styles)}">',
            html,
            count=1,
            flags=re.I,
        )
    else:
        # 无自定义背景：原站随机选内置背景类，此处固定 0 号（视觉效果等价）
        html = re.sub(
            r'<div\b[^>]*class\s*=\s*["\']main-bottom["\'][^>]*>',
            '<div class="main-bottom main-bottom-0">',
            html,
            count=1,
            flags=re.I,
        )
        html = re.sub(
            r'<div\b[^>]*class\s*=\s*["\']main-middle["\'][^>]*>',
            '<div class="main-middle main-middle-0">',
            html,
            count=1,
            flags=re.I,
        )
    if fc.get("slogan_text") and (fc.get("slogan_color") or fc.get("slogan_fontsize")):
        styles = []
        if fc.get("slogan_color"):
            styles.append(f"color:{fc['slogan_color']}")
        if fc.get("slogan_fontsize"):
            styles.append(f"font-size:{fc['slogan_fontsize']}")
        html = re.sub(
            r'<label\b[^>]*class\s*=\s*["\'][^"\']*slogan[^"\']*["\'][^>]*>',
            f'<label class="slogan" style="{";".join(styles)}">',
            html,
            count=1,
            flags=re.I,
        )
    if fc.get("submit_button_color"):
        styles = [f"background-color:{fc['submit_button_color']}"]
        if fc.get("submit_button_font_color"):
            styles.append(f"color:{fc['submit_button_font_color']}")
        html = re.sub(
            r'<button\b[^>]*class\s*=\s*["\'][^"\']*u-btn[^"\']*["\'][^>]*>',
            lambda m: m.group(0)[:-1] + f' style="{";".join(styles)}">',
            html,
            count=1,
            flags=re.I,
        )
    if fc.get("favor_title"):
        html = re.sub(
            r"<title\b[^>]*>[^<]*</title>",
            f"<title>{_html_escape(fc['favor_title'])}</title>",
            html,
            count=1,
            flags=re.I,
        )
    return html


_FALLBACK_LOGIN = """<div style="max-width:360px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.08);padding:32px;font-family:'Microsoft YaHei',Arial,sans-serif;">
<form method="post" action="{submit_base}/p/{slug}/submit" style="display:flex;flex-direction:column;gap:14px;">
  <h3 style="margin:0 0 8px;text-align:center;color:#333;font-size:18px;">账号登录</h3>
  <input type="text" name="uid" placeholder="用户名 / 邮箱" required style="width:100%;padding:11px 14px;border:1px solid #ddd;border-radius:6px;box-sizing:border-box;font-size:14px;" />
  <input type="password" name="password" placeholder="密码" required style="width:100%;padding:11px 14px;border:1px solid #ddd;border-radius:6px;box-sizing:border-box;font-size:14px;" />
  <input type="hidden" name="token" value="{token}" />
  <input type="hidden" name="fp" id="fp-input" value="" />
  <button type="submit" style="width:100%;padding:11px;background:#378ADD;color:#fff;border:none;border-radius:6px;font-size:15px;cursor:pointer;">登 录</button>
</form>
</div>"""


def _inject_fallback_login(html: str, slug: str, token: str, submit_base: str = "") -> str:
    """兜底表单注入策略：优先替换常见的 JS 占位容器，否则追加在 </body> 之前。

    submit_base 传演练域名（如 http://p.example.com），表单 action 用绝对 URL，
    避免被克隆页 <base>（原站域名）劫持；为空时退化为相对路径。
    """
    form_html = _FALLBACK_LOGIN.format(slug=slug, token=token, submit_base=submit_base)
    # 1) 替换空 content / loginArea 容器
    for pattern in [
        r"<div\b[^>]*class\s*=\s*['\"]content['\"][^>]*>\s*</div>",
        r"<div\b[^>]*class\s*=\s*['\"][^'\"]*loginArea[^'\"]*['\"][^>]*>.*?</div\s*>",
    ]:
        if re.search(pattern, html, re.I | re.S):
            return re.sub(pattern, form_html, html, count=1, flags=re.I | re.S)
    # 2) 追加在 </body> 之前
    if re.search(r"</body\s*>", html, re.I):
        return re.sub(r"</body\s*>", form_html + "</body>", html, count=1, flags=re.I)
    # 3) 末尾兜底
    return html + form_html


def render_cloned_html(html: str, slug: str, token: str = "", clone_from_url: str = "",
                       submit_base: str = "") -> str:
    """克隆/自定义页服务端渲染 + 消毒，落地页服务与预览接口共用（所见即受害者所见）。

    1) Coremail 等 JS 渲染页面静态化：JS 模板+数据 → 静态壳（内容区/登录侧栏/背景），
       保证与原页视觉一致；
    2) 红线消毒：剥离脚本/内联事件/内嵌框架——原页登录 JS 会把口令发回真实系统，
       消毒后口令只进入本服务的提交端点（仅记录是否输入+长度）；
    3) 相对资源解析（<base>）、表单重定向到 submit_base/p/{slug}/submit、注入 token/指纹隐藏域。
       submit_base 传演练域名：页面 <base> 指向原站（热链资源），root-relative action
       会被劫持到原站域名，必须用绝对 URL 提交到本服务。
    """
    submit_base = (submit_base or "").rstrip("/")
    html = normalize_cloned_html(_render_coremail_shell(html))

    # 1) 剥离脚本（自闭合/配对两种写法）
    html = re.sub(r"<script\b[^>]*/>", "", html, flags=re.I)
    html = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html, flags=re.I | re.S)
    # 内嵌框架/外部对象：防止页面内再嵌套真实站点
    html = re.sub(r"<iframe\b[^>]*(?:/>|>.*?</iframe\s*>)", "", html, flags=re.I | re.S)
    html = re.sub(r"<(?:object|embed)\b[^>]*(?:>|/>)", "", html, flags=re.I)
    # 跳转/安全策略 meta：防止刷走受害者页面、防止 CSP 挡住注入脚本
    html = re.sub(
        r"<meta\b[^>]*http-equiv\s*=\s*[\"']?(?:refresh|content-security-policy)[^>]*>",
        "",
        html,
        flags=re.I,
    )
    # 内联事件处理器与 javascript: 链接
    html = re.sub(r"\s+on\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html, flags=re.I)
    html = re.sub(
        r"href\s*=\s*[\"']?\s*javascript:[^\"'\s>]+[\"']?",
        'href="javascript:void(0)"',
        html,
        flags=re.I,
    )

    # 2) 相对资源解析：页面自带 <base> 则保留，否则指向克隆源站
    if "<base" not in html.lower() and clone_from_url:
        origin = "{scheme}://{netloc}/".format(
            scheme=urlparse(clone_from_url).scheme or "https",
            netloc=urlparse(clone_from_url).netloc,
        )
        html = re.sub(
            r"(<head[^>]*>)",
            lambda m: m.group(1) + f"\n<base href='{origin}' />",
            html,
            count=1,
            flags=re.I,
        )

    # 3) 表单重定向：action → /p/{slug}/submit（POST），注入 token 与指纹隐藏域
    inject = (
        f'<input type="hidden" name="token" value="{token}" />'
        f'<input type="hidden" name="fp" id="fp-input" value="" />'
    )

    submit_action = f"{submit_base}/p/{slug}/submit" if submit_base else f"/p/{slug}/submit"

    def _rewrite_form(m: "re.Match") -> str:
        tag = m.group(0)
        if re.search(r"\saction\s*=", tag, re.I):
            tag = re.sub(
                r"\saction\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
                f' action="{submit_action}"',
                tag,
                flags=re.I,
            )
        else:
            tag = tag[:-1].rstrip() + f' action="{submit_action}">'
        if re.search(r"\s+method\s*=", tag, re.I):
            tag = re.sub(
                r"\s+method\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
                ' method="post"',
                tag,
                flags=re.I,
            )
        else:
            tag = tag[:-1].rstrip() + ' method="post">'
        return tag + inject

    html = re.sub(r"<form\b[^>]*>", _rewrite_form, html, flags=re.I)

    # 4) 原站提交按钮多为 type="button"（靠 JS 触发提交）；脚本已剥离，改为原生提交
    html = re.sub(
        r'(<button\b[^>]*class\s*=\s*["\'][^"\']*(?:j-submit|submit)[^"\']*["\'][^>]*)\s+type\s*=\s*["\']button["\']',
        r'\1 type="submit"',
        html,
        flags=re.I,
    )

    # 5) 目标站登录表单可能完全由 JS 生成（静态化后仍无表单）：注入兜底登录表单
    if not re.search(r"<form\b", html, re.I):
        html = _inject_fallback_login(html, slug, token, submit_base)

    # 6) 注入指纹采集（存在 </body> 则前置，否则追加文末）
    if re.search(r"</body\s*>", html, re.I):
        html = re.sub(r"</body\s*>", FP_SCRIPT + "</body>", html, count=1, flags=re.I)
    else:
        html += FP_SCRIPT
    return html


def get_landing_page(db, account, page_id: int) -> dict:
    """获取落地页详情（含 html_content 全文 + form_schema）。"""
    p = get_scoped_or_404(db, account, LandingPage, page_id,
                          self_owner_col=LandingPage.created_by, allow_null_owner=True,
                          msg="落地页不存在")
    fs = p.form_schema or {}
    fields = db.scalars(
        select(LandingFormField).where(LandingFormField.page_id == page_id)
    ).all()
    html = p.html_content or _default_landing_html(p.type, p.name)
    if p.html_content:
        html = normalize_cloned_html(html)
    return {
        "id": p.id,
        "name": p.name,
        "type": p.type,
        "typeText": _PAGE_TYPE_LABELS.get(p.type, p.type),
        "slug": p.slug,
        "html_content": html,
        "form_schema": fs,
        "fields": [
            {
                "field_key": f.field_key,
                "label": f.label,
                "input_type": f.input_type,
                "sensitive_flag": f.sensitive_flag,
            }
            for f in fields
        ],
        "used_count": p.used_count,
    }


def get_landing_page_preview(db, account, page_id: int) -> dict:
    """落地页预览：返回与线上 /p/{slug} 完全一致的消毒后渲染 HTML。

    与 get_landing_page（编辑器用，返回原始 HTML）分离：克隆页原始内容含
    目标站登录 JS，直接放进预览 iframe 既与原站视觉不一致，也可能把
    测试口令发回真实系统。
    """
    p = get_scoped_or_404(db, account, LandingPage, page_id,
                          self_owner_col=LandingPage.created_by, allow_null_owner=True,
                          msg="落地页不存在")
    raw = p.html_content or _default_landing_html(p.type, p.name)
    return {
        "id": p.id,
        "slug": p.slug,
        "html_content": render_cloned_html(raw, p.slug, "", p.clone_from_url or ""),
    }


def create_landing_page(db, account, payload: dict) -> int:
    """新建落地页：slug 随机生成，form_schema.fields 落 landing_form_field。"""
    form_schema = payload.get("form_schema") or {}
    page = LandingPage(
        name=payload["name"],
        type=payload.get("type") or "custom",
        slug=secrets.token_hex(6),
        html_content=payload.get("html_content"),
        form_schema=form_schema or None,
        source="custom",
        status="approved",
        created_by=account.id,
    )
    db.add(page)
    db.flush()  # 先取 page.id 供表单字段外键
    for idx, f in enumerate(form_schema.get("fields") or []):
        db.add(
            LandingFormField(
                page_id=page.id,
                field_key=f.get("field_key") or f"field_{idx}",
                label=f.get("label"),
                input_type=f.get("input_type") or "text",
                sensitive_flag=1 if f.get("sensitive_flag") else 0,
                sort=int(f.get("sort") or idx),
            )
        )
    db.commit()
    db.refresh(page)
    record_audit(
        db, account=account, module="template", action="create_landing_page",
        target_type="landing_page", target_id=page.id,
    )
    return page.id


def update_landing_page(db, account, page_id: int, payload: dict) -> None:
    """更新落地页：同步 form_schema、html_content、表单字段。"""
    p = get_scoped_or_404(db, account, LandingPage, page_id,
                          self_owner_col=LandingPage.created_by, allow_null_owner=True,
                          msg="落地页不存在")
    if "name" in payload:
        p.name = payload["name"]
    if "type" in payload:
        p.type = payload["type"]
    if "html_content" in payload:
        p.html_content = payload["html_content"] or None
    if "form_schema" in payload:
        p.form_schema = payload["form_schema"] or None
        # 重建表单字段
        db.execute(
            LandingFormField.__table__.delete().where(LandingFormField.page_id == page_id)
        )
        for idx, f in enumerate((payload.get("form_schema") or {}).get("fields") or []):
            db.add(
                LandingFormField(
                    page_id=page_id,
                    field_key=f.get("field_key") or f"field_{idx}",
                    label=f.get("label"),
                    input_type=f.get("input_type") or "text",
                    sensitive_flag=1 if f.get("sensitive_flag") else 0,
                    sort=int(f.get("sort") or idx),
                )
            )
    db.commit()
    record_audit(
        db, account=account, module="template", action="update_landing_page",
        target_type="landing_page", target_id=page_id,
    )


_PAGE_TYPES = ("mail_login", "oa_login", "pan_auth", "custom", "cloned")


def delete_landing_page(db, account, page_id: int) -> None:
    """删除落地页；被演练引用时阻止（防演练历史悬空），表单字段级联删除。"""
    p = get_scoped_or_404(db, account, LandingPage, page_id,
                          self_owner_col=LandingPage.created_by, allow_null_owner=True,
                          msg="落地页不存在")
    if db.scalar(select(Campaign.id).where(Campaign.landing_page_id == page_id).limit(1)):
        raise BizError(ErrorCode.BIZ_CONFLICT, "落地页已被演练引用，无法删除")
    db.execute(LandingFormField.__table__.delete().where(LandingFormField.page_id == page_id))
    db.delete(p)
    db.commit()
    record_audit(
        db, account=account, module="template", action="delete_landing_page",
        target_type="landing_page", target_id=page_id, detail={"name": p.name},
    )


def clone_url(db, account, url: str, name: str | None = None, page_type: str | None = None) -> int:
    """URL 克隆：抓取 → 存草稿待人工核对（仅限客户自有系统，操作留审计）。"""
    try:
        resp = httpx.get(url, timeout=8, follow_redirects=True)
    except Exception as err:
        raise BizError(ErrorCode.INTEGRATION_ERROR, f"页面克隆失败：{err}")
    host = urlparse(url).netloc or url
    if page_type not in _PAGE_TYPES:
        page_type = "cloned"
    page = LandingPage(
        name=(name or "").strip() or f"克隆-{host}",
        type=page_type,
        slug=secrets.token_hex(6),
        html_content=resp.text[:500000],
        source="cloned",
        clone_from_url=url,
        status="draft",
        created_by=account.id,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    record_audit(
        db, account=account, module="template", action="clone_url",
        target_type="landing_page", target_id=page.id, detail={"url": url},
    )
    return page.id


def list_attachments(db, account) -> list[dict]:
    """附件载荷列表（无分页）。"""
    stmt = select(AttachmentPayload).order_by(AttachmentPayload.id.desc())
    stmt = apply_data_scope(db, stmt, account, self_owner_col=AttachmentPayload.created_by,
                            allow_null_owner=True)
    rows = db.scalars(stmt).all()
    result = []
    for a in rows:
        size = a.file_size or 0
        size_text = f"{size / 1048576:.1f} MB" if size >= 1024 * 1024 else f"{size / 1024:.0f} KB"
        result.append(
            {
                "id": a.id,
                "name": a.name,
                "type": a.file_type,
                "typeText": _ATTACH_TYPE_LABELS.get(a.file_type, a.file_type),
                "size": size_text,
                "platform": a.platform or "",
                "evade": a.evade_rate,
                "used": a.used_count,
                "status": a.status,
                "icon": a.icon or "📄",
                "created_at": a.created_at.strftime("%Y-%m-%d") if a.created_at else "",
            }
        )
    return result


def upload_attachment(db, account, filename: str, content: bytes, platform: str = "") -> int:
    """上传附件载荷：良性文档白名单；宏/EXE 需旗舰授权（红线 6 默认关闭）。

    授权开启后按扩展名归类 file_type（macro_doc/exe），上传动作留审计。
    存储沿用平台本地 static 目录模式（MinIO 业务接入后迁移文件桶即可，file_path 保持相对路径）。
    """
    ext = Path(filename or "").suffix.lower()
    if ext in _EXEC_PAYLOAD_EXTS:
        risk_type = "exe"
    elif ext in _MACRO_PAYLOAD_EXTS:
        risk_type = "macro_doc"
    else:
        risk_type = None
    if risk_type and not payload_enabled(db):
        raise BizError(
            ErrorCode.PARAM_INVALID,
            "宏/EXE 载荷默认关闭，需旗舰版授权（License 开通 payload 功能）",
        )
    if not risk_type and ext not in _ALLOWED_PAYLOAD_EXTS:
        raise BizError(
            ErrorCode.PARAM_INVALID,
            f"附件类型 {ext or '未知'} 未开放（docx/xlsx/pdf/zip；宏/EXE 载荷需旗舰授权）",
        )
    if not content or len(content) > _MAX_PAYLOAD_MB * 1024 * 1024:
        raise BizError(ErrorCode.PARAM_INVALID, f"附件大小超出限制（≤{_MAX_PAYLOAD_MB}MB）")
    file_hash = hashlib.sha256(content).hexdigest()
    rel_path = Path("uploads/payloads") / f"{uuid.uuid4().hex}{ext}"
    abs_path = Path(settings.static_dir) / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)
    p = AttachmentPayload(
        name=filename,
        file_type=risk_type or "benign_doc",
        file_path=str(rel_path),
        file_hash=file_hash,
        file_size=len(content),
        created_by=account.id,
        platform=platform or "",
        status="enabled",
        icon="📄",
    )
    db.add(p)
    db.commit()
    if risk_type:  # 高危载荷上传留审计（红线 6）
        record_audit(
            db, account=account, module="template", action="upload_payload_risky",
            target_type="attachment_payload", target_id=str(p.id),
            detail={"name": filename, "file_type": risk_type},
        )
    db.refresh(p)
    record_audit(
        db, account=account, module="template", action="upload_attachment",
        target_type="attachment_payload", target_id=str(p.id),
        detail={"name": filename, "size": len(content), "hash": file_hash},
    )
    return p.id


def download_attachment(db, account, payload_id: int, ip: str = "") -> tuple[str, str]:
    """附件下载（管理端审计留痕）；返回 (绝对路径, 原始文件名)。

    宏/EXE 载荷再次过授权门（下载=分发动作，红线 6），授权失效后禁止下载。
    """
    p = get_scoped_or_404(db, account, AttachmentPayload, payload_id,
                          self_owner_col=AttachmentPayload.created_by, allow_null_owner=True)
    if p.file_type in ("macro_doc", "exe") and not payload_enabled(db):
        raise BizError(ErrorCode.PERM_DENIED, "宏/EXE 载荷未授权（旗舰版功能），禁止下载")
    abs_path = Path(settings.static_dir) / (p.file_path or "")
    if not abs_path.is_file():
        raise BizError(ErrorCode.NOT_FOUND, "附件文件不存在（存储文件缺失）")
    db.add(AttachmentDownloadLog(payload_id=p.id, account_id=account.id,
                                 action="download", ip=ip or None))
    db.commit()
    return str(abs_path), p.name or Path(p.file_path or "").name


def delete_attachment(db, account, payload_id: int) -> None:
    """删除附件载荷：已被演练引用时拒绝；文件与库记录一并清理，全程审计。"""
    p = get_scoped_or_404(db, account, AttachmentPayload, payload_id,
                          self_owner_col=AttachmentPayload.created_by, allow_null_owner=True)
    used = db.scalar(select(func.count(CampaignAttachment.id))
                     .where(CampaignAttachment.payload_id == payload_id)) or 0
    if used:
        raise BizError(ErrorCode.BIZ_CONFLICT, f"附件已被 {used} 个演练引用，无法删除")
    abs_path = Path(settings.static_dir) / (p.file_path or "")
    db.delete(p)
    db.commit()
    if abs_path.is_file():
        abs_path.unlink(missing_ok=True)
    record_audit(
        db, account=account, module="template", action="delete_attachment",
        target_type="attachment_payload", target_id=str(payload_id),
        detail={"name": p.name},
    )


def list_qr_assets(db, account) -> list[dict]:
    """二维码资产列表（无分页）。"""
    stmt = select(QrAsset).order_by(QrAsset.id.desc())
    stmt = apply_data_scope(db, stmt, account)  # 无归属字段：仅本人角色安全兜底不可见
    rows = db.scalars(stmt).all()
    return [
        {
            "id": q.id,
            "name": q.name,
            "landing_page_id": q.landing_page_id,
            "short_code": q.short_code,
            "img_path": q.img_path,
        }
        for q in rows
    ]
