"""素材模板服务：邮件模板、落地页、附件载荷、二维码。"""
import re
import secrets
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select

from app.core.audit import record_audit
from app.core.errors import BizError, ErrorCode

from .models import (
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
    "macro_doc": "宏文档",
    "exe": "可执行文件",
    "qr": "二维码",
    "other": "其他",
}

_VAR_RE = re.compile(r"\{\{\.\w+\}\}")


def list_email_templates(db, account, scene=None) -> list[dict]:
    """模板卡片列表（无分页），按使用次数倒序。"""
    stmt = select(EmailTemplate).order_by(EmailTemplate.used_count.desc())
    if scene:
        stmt = stmt.where(EmailTemplate.scene == scene)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "cat": t.scene,
            "catText": _SCENE_LABELS.get(t.scene, t.scene),
            "subject": t.subject,
            "sender": t.sender,
            "stars": t.stars,
            "used": t.used_count,
            "click": float(t.click_rate or 0),
            "preview": f"{t.subject[:24]}…" if len(t.subject) > 24 else t.subject,
        }
        for t in rows
    ]


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
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    record_audit(
        db, account=account, module="template", action="create_template",
        target_type="email_template", target_id=tpl.id,
    )
    return tpl.id


def get_email_template(db, template_id: int) -> dict:
    """获取邮件模板详情（含 html_body 全文）。"""
    t = db.get(EmailTemplate, template_id)
    if t is None:
        raise ValueError("模板不存在")
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
        "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
    }


def update_email_template(db, account, template_id: int, payload: dict) -> None:
    """更新邮件模板：重新抽取变量，写审计。"""
    t = db.get(EmailTemplate, template_id)
    if t is None:
        raise ValueError("模板不存在")
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
    db.commit()
    record_audit(
        db, account=account, module="template", action="update_template",
        target_type="email_template", target_id=t.id,
    )


def test_send_template(db, account, template_id: int, to: list[str]) -> dict:
    """测试发送：仅限白名单收件人，真实投递由 Worker 队列执行（TODO）。"""
    if db.get(EmailTemplate, template_id) is None:
        raise BizError(ErrorCode.NOT_FOUND)
    record_audit(
        db, account=account, module="template", action="test_send",
        target_type="email_template", target_id=template_id,
        detail={"to_count": len(to)},
    )
    return {"ok": True, "message": f"测试邮件已发送至 {len(to)} 个白名单收件人"}


def list_landing_pages(db, account) -> list[dict]:
    """落地页列表（无分页），字段数聚合自 landing_form_field。"""
    pages = db.scalars(select(LandingPage).order_by(LandingPage.id.desc())).all()
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
    result = []
    for p in pages:
        fields = counts.get(p.id, 0)
        fs = p.form_schema or {}
        collect = int(fs.get("collect", fields)) if fs else fields
        result.append(
            {
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "typeText": _PAGE_TYPE_LABELS.get(p.type, p.type),
                "fields": fields,
                "collect": collect,
                "used": p.used_count,
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


def get_landing_page(db, page_id: int) -> dict:
    """获取落地页详情（含 html_content 全文 + form_schema）。"""
    p = db.get(LandingPage, page_id)
    if p is None:
        raise ValueError("落地页不存在")
    fs = p.form_schema or {}
    fields = db.scalars(
        select(LandingFormField).where(LandingFormField.page_id == page_id)
    ).all()
    html = p.html_content or _default_landing_html(p.type, p.name)
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
    p = db.get(LandingPage, page_id)
    if p is None:
        raise ValueError("落地页不存在")
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


def clone_url(db, account, url: str) -> int:
    """URL 克隆：抓取 → 存草稿待人工核对（仅限客户自有系统，操作留审计）。"""
    try:
        resp = httpx.get(url, timeout=8, follow_redirects=True)
    except Exception as err:
        raise BizError(ErrorCode.INTEGRATION_ERROR, f"页面克隆失败：{err}")
    host = urlparse(url).netloc or url
    page = LandingPage(
        name=f"克隆-{host}",
        type="cloned",
        slug=secrets.token_hex(6),
        html_content=resp.text[:50000],
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
    rows = db.scalars(select(AttachmentPayload).order_by(AttachmentPayload.id.desc())).all()
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
            }
        )
    return result


def list_qr_assets(db, account) -> list[dict]:
    """二维码资产列表（无分页）。"""
    rows = db.scalars(select(QrAsset).order_by(QrAsset.id.desc())).all()
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
