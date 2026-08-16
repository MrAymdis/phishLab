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


def get_menus(db: Session, account: SysAccount) -> list[dict]:
    """返回当前账号可见菜单（RBAC 菜单权限 ∩ License 模块开关）。TODO(一期)。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED, "动态菜单尚未实现")
