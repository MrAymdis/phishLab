"""开放平台服务（三期模块）。OAuth2 client_credentials + 限流网关 + 调用审计。

业务端点实现见 biz.py；本文件负责网关层：access_token 鉴权（JWT 验签 → 应用
状态 → IP 白名单 → scope 校验 → 分钟限流）与调用日志落库（OpenApiLog）。
"""
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt
import redis
from fastapi import Request
from sqlalchemy import func, select

from app.core.config import settings
from app.core.errors import BizError, ErrorCode
from app.core.security import decrypt_secret, encrypt_secret

from .models import OpenApiLog, OpenApp

# scope → 可用端点域（创建应用时按此分配）
SCOPES = ("campaign", "report", "user", "template", "mail_report", "system")


def _redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _client_ip(request: Request) -> str:
    """调用方 IP：优先 X-Forwarded-For 首个（部署需 Nginx 设置 proxy_set_header，
    否则反代后一律取到网关 IP，白名单失效）。"""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def authenticate(request: Request, db, scope: str) -> OpenApp:
    """网关鉴权（fail-closed）：任一校验不通过即 401/403，不进入业务层。"""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise BizError(ErrorCode.UNAUTHORIZED, "缺少 Bearer access_token")
    token = auth[7:].strip()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise BizError(ErrorCode.TOKEN_EXPIRED, "access_token 已过期，请重新换取")
    except jwt.InvalidTokenError:
        raise BizError(ErrorCode.UNAUTHORIZED, "access_token 无效")
    sub = payload.get("sub", "")
    app_id = sub[4:] if sub.startswith("app:") else ""
    app = db.scalar(select(OpenApp).where(OpenApp.app_id == app_id))
    if app is None or app.status != "active":
        raise BizError(ErrorCode.PERM_DENIED, "应用不存在或已禁用")
    # token 与 DB 双侧校验 scope（应用被收回权限后旧 token 立即失效）
    if scope not in (payload.get("scopes") or []) or scope not in (app.scopes or []):
        raise BizError(ErrorCode.PERM_DENIED, f"应用无 {scope} 权限")
    ip = _client_ip(request)
    if app.ip_whitelist and ip not in app.ip_whitelist:
        raise BizError(ErrorCode.PERM_DENIED, f"调用 IP 不在白名单（{ip}）")
    _rate_limit(app, ip)
    return app


def _rate_limit(app: OpenApp, ip: str) -> None:
    """分钟限流：Redis INCR 计数；Redis 故障放行（限流设施不阻断业务）。"""
    try:
        minute = int(time.time()) // 60
        key = f"openapi:rl:{app.app_id}:{minute}"
        r = _redis()
        n = r.incr(key)
        if n == 1:
            r.expire(key, 120)
        if n > (app.rate_limit or 60):
            raise BizError(ErrorCode.RATE_LIMIT_EXCEEDED,
                           f"超过限流阈值（{app.rate_limit} 次/分钟）")
    except redis.RedisError:
        pass


def log_call(db, app: OpenApp, request: Request, status_code: int,
             started: float, error_msg: str | None = None) -> None:
    """调用审计落库（OpenApiLog）：method/path/状态/延迟/IP/错误摘要。

    不记录请求/响应正文——避免目标用户等敏感信息扩大落库面。
    """
    try:
        db.add(OpenApiLog(
            app_id=app.app_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            latency_ms=int((time.monotonic() - started) * 1000),
            ip=_client_ip(request),
            error_msg=(error_msg or "")[:500],
        ))
        db.commit()
    except Exception:
        db.rollback()


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
    for s in payload.get("scopes") or []:
        if s not in SCOPES:
            raise BizError(ErrorCode.PARAM_INVALID, f"scope 仅支持 {SCOPES}")
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
