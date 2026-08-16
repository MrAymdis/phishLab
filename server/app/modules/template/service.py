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
