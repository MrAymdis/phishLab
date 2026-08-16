"""账号服务：登录为脚手架内真实实现；菜单/SSO 待一期实现。"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BizError, ErrorCode
from app.core.security import create_token, verify_password

from .models import LoginLog, SysAccount
from .schemas import LoginRequest


def login(db: Session, req: LoginRequest, ip: str | None = None) -> dict:
    account = db.scalar(select(SysAccount).where(SysAccount.username == req.username))
    ok = account is not None and verify_password(req.password, account.password_hash)
    db.add(
        LoginLog(
            account_id=account.id if account else None,
            username=req.username,
            login_type="local",
            success=1 if ok else 0,
            fail_reason=None if ok else "用户名或密码错误",
            ip=ip,
        )
    )
    db.commit()
    if account is None or not ok:
        raise BizError(ErrorCode.UNAUTHORIZED, "用户名或密码错误")
    if account.status != 1:
        raise BizError(ErrorCode.ACCOUNT_DISABLED)
    account.last_login_at = datetime.now()
    db.commit()
    return {
        "token": create_token(account.id, account.username),
        "account_id": account.id,
        "username": account.username,
        "real_name": account.real_name,
    }


# 11 项统一导航（与前端 permission store DEFAULT_MENUS 一致）
_MENUS: list[dict] = [
    {"path": "/dashboard", "title": "数据概览", "icon": "Odometer"},
    {"path": "/campaign", "title": "演练管理", "icon": "Aim"},
    {"path": "/template", "title": "素材模板", "icon": "Files"},
    {"path": "/send-config", "title": "发送配置", "icon": "Message"},
    {"path": "/users", "title": "用户和组", "icon": "User"},
    {"path": "/training", "title": "安全培训", "icon": "Reading"},
    {"path": "/reports", "title": "数据报表", "icon": "DataAnalysis"},
    {"path": "/mail-report", "title": "邮件举报", "icon": "Bell"},
    {"path": "/settings", "title": "系统设置", "icon": "Setting"},
    {"path": "/ai", "title": "智能助手", "icon": "ChatDotRound"},
    {"path": "/openapi", "title": "API开放平台", "icon": "Connection"},
]

# 菜单 → License 功能开关（其余菜单所有版本可见）
_MENU_FEATURE_GATE = {"/ai": "ai", "/openapi": "openapi"}


def get_menus(db: Session, account: SysAccount) -> list[dict]:
    """返回当前账号可见菜单（License 模块开关；RBAC 菜单级权限 TODO(一期)）。"""
    from app.modules.license import service as license_service  # 延迟导入避免循环

    menus = []
    for m in _MENUS:
        gate = _MENU_FEATURE_GATE.get(m["path"])
        if gate and not license_service.feature_enabled(db, gate):
            continue
        menus.append(m)
    return menus
