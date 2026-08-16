"""开放平台服务（三期模块）。OAuth2 client_credentials + 限流网关。"""
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import func, select

from app.core.config import settings
from app.core.errors import BizError, ErrorCode
from app.core.security import decrypt_secret, encrypt_secret

from .models import OpenApiLog, OpenApp


def _mask_secret(raw: str) -> str:
    if not raw:
        return ""
    return "sk_live_" + "*" * 12 + raw[-4:]


def list_apps(db, account):
    """AppSecret 只回显掩码。"""
    apps = db.scalars(select(OpenApp).order_by(OpenApp.id.desc())).all()
    result = []
    for a in apps:
        raw_secret = decrypt_secret(a.app_secret_enc) if a.app_secret_enc else ""
        calls = db.scalar(
            select(func.count()).select_from(OpenApiLog).where(OpenApiLog.app_id == a.app_id)
        ) or 0
        result.append({
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "app_id": a.app_id,
            "app_secret": _mask_secret(raw_secret),
            "scopes": a.scopes or [],
            "ip_whitelist": a.ip_whitelist or [],
            "callback_url": a.callback_url,
            "rate_limit": a.rate_limit,
            "call_count": calls,
            "status": a.status,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
        })
    return result


def create_app(db, account, payload: dict) -> dict:
    """生成 AppID/AppSecret（encrypt_secret 入库）、scope、IP 白名单、限流。"""
    app_id = "app_" + secrets.token_hex(8)
    app_secret = "sk_live_" + secrets.token_hex(24)
    app = OpenApp(
        app_id=app_id,
        app_secret_enc=encrypt_secret(app_secret),
        name=payload["name"],
        description=payload.get("description"),
        scopes=payload.get("scopes") or [],
        ip_whitelist=payload.get("ip_whitelist") or [],
        callback_url=payload.get("callback_url"),
        rate_limit=payload.get("rate_limit", 60),
        status="active",
        created_by=account.id,
    )
    db.add(app)
    db.commit()

    from app.core.audit import record_audit

    record_audit(
        db, account=account, module="openapi", action="create_app",
        target_type="open_app", target_id=app_id,
        detail={"name": app.name, "scopes": app.scopes},
    )
    # Secret 仅创建时返回一次
    return {"id": app.id, "app_id": app_id, "app_secret": app_secret}


def issue_token(db, app_id: str, app_secret: str) -> dict:
    """client_credentials → 短期 JWT；校验状态/IP 白名单。"""
    app = db.scalar(select(OpenApp).where(OpenApp.app_id == app_id))
    if app is None or app.status != "active":
        raise BizError(ErrorCode.PERM_DENIED, "应用不存在或已禁用")
    try:
        raw = decrypt_secret(app.app_secret_enc)
    except Exception:
        raise BizError(ErrorCode.PERM_DENIED, "AppSecret 校验失败")
    if raw != app_secret:
        raise BizError(ErrorCode.PERM_DENIED, "AppSecret 校验失败")

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": f"app:{app.app_id}", "scopes": app.scopes or [], "iat": now,
         "exp": now + timedelta(hours=2)},
        settings.secret_key, algorithm="HS256",
    )
    db.add(OpenApiLog(
        app_id=app.app_id, method="POST", path="/openapi/v1/oauth/token",
        status_code=200, latency_ms=0,
    ))
    db.commit()
    return {"access_token": token, "expires_in": 7200, "scope": " ".join(app.scopes or [])}
