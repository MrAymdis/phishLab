"""账号服务：登录/菜单/平台账号管理（RBAC 账号维度）。"""
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BizError, ErrorCode
from app.core.security import create_token, hash_password, verify_password

from .models import LoginLog, SysAccount
from .schemas import AccountCreate, AccountUpdate, LoginRequest, PasswordChange, ProfileUpdate


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


def list_accounts(db: Session, page: int = 1, page_size: int = 10, kw: str = "") -> dict:
    """平台账号分页列表（含角色列表），按创建时间倒序。"""
    from app.modules.rbac.models import SysAccountRole, SysRole

    stmt = select(SysAccount)
    if kw:
        like = f"%{kw}%"
        stmt = stmt.where(or_(SysAccount.username.like(like), SysAccount.real_name.like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.order_by(SysAccount.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    role_rows = db.execute(
        select(SysAccountRole.account_id, SysRole.id, SysRole.name)
        .join(SysRole, SysRole.id == SysAccountRole.role_id)
        .where(SysAccountRole.account_id.in_([a.id for a in rows]))
    ).all()
    roles_map: dict[int, list[dict]] = {}
    for aid, rid, rname in role_rows:
        roles_map.setdefault(aid, []).append({"id": rid, "name": rname})
    return {
        "total": total or 0,
        "list": [
            {
                "id": a.id, "username": a.username, "real_name": a.real_name,
                "status": a.status, "last_login_at": a.last_login_at,
                "created_at": a.created_at, "roles": roles_map.get(a.id, []),
            }
            for a in rows
        ],
    }


def create_account(db: Session, account: SysAccount, payload: AccountCreate) -> int:
    """新建平台账号：用户名唯一、密码 PBKDF2 哈希、分配角色（写审计）。"""
    from app.modules.rbac.models import SysAccountRole, SysRole

    if db.scalar(select(SysAccount).where(SysAccount.username == payload.username)):
        raise BizError(ErrorCode.PARAM_INVALID, f"用户名 {payload.username} 已存在")
    if payload.role_ids:
        role_count = db.scalar(
            select(func.count()).select_from(SysRole).where(SysRole.id.in_(payload.role_ids))
        )
        if role_count != len(payload.role_ids):
            raise BizError(ErrorCode.PARAM_INVALID, "存在无效角色")
    acc = SysAccount(
        username=payload.username,
        real_name=payload.real_name,
        password_hash=hash_password(payload.password),
        status=1,
    )
    db.add(acc)
    db.flush()
    for rid in payload.role_ids:
        db.add(SysAccountRole(account_id=acc.id, role_id=rid))
    db.commit()
    record_account_audit(db, account, "create", "sys_account", acc.id, payload.dict())
    return acc.id


def update_account(db: Session, operator: SysAccount, aid: int, payload: AccountUpdate) -> None:
    """更新账号资料/状态/角色（覆盖式）。防自锁：不能禁用自己。"""
    from app.modules.rbac.models import SysAccountRole

    acc = _get_account_or_404(db, aid)
    if payload.status == 0 and acc.id == operator.id:
        raise BizError(ErrorCode.PARAM_INVALID, "不能禁用当前登录账号")
    acc.real_name = payload.real_name
    acc.status = payload.status
    # 覆盖式分配角色
    db.execute(SysAccountRole.__table__.delete().where(SysAccountRole.account_id == aid))
    for rid in payload.role_ids:
        db.add(SysAccountRole(account_id=aid, role_id=rid))
    db.commit()
    record_account_audit(db, operator, "update", "sys_account", aid, payload.dict())


def reset_password(db: Session, operator: SysAccount, aid: int, new_password: str) -> None:
    """管理员重置密码（PBKDF2 哈希，不留明文，写审计）。"""
    acc = _get_account_or_404(db, aid)
    acc.password_hash = hash_password(new_password)
    db.commit()
    record_account_audit(db, operator, "reset_password", "sys_account", aid, {"username": acc.username})


def update_profile(db: Session, account: SysAccount, payload: ProfileUpdate) -> None:
    """个人中心：修改本人资料（写审计）。"""
    account.real_name = payload.real_name
    db.commit()
    record_account_audit(db, account, "update_profile", "sys_account", account.id,
                         {"real_name": payload.real_name})


def change_password(db: Session, account: SysAccount, payload: PasswordChange) -> None:
    """个人中心：修改本人密码（验证旧密码，PBKDF2 哈希存储，写审计）。"""
    if not verify_password(payload.old_password, account.password_hash):
        raise BizError(ErrorCode.UNAUTHORIZED, "原密码不正确")
    account.password_hash = hash_password(payload.new_password)
    db.commit()
    record_account_audit(db, account, "change_password", "sys_account", account.id, {})


def _get_account_or_404(db: Session, aid: int) -> SysAccount:
    acc = db.get(SysAccount, aid)
    if acc is None:
        raise BizError(ErrorCode.NOT_FOUND, "账号不存在")
    return acc


def record_account_audit(db: Session, operator: SysAccount, action: str,
                         target_type: str, target_id: int, detail: dict) -> None:
    """账号管理操作审计（统一入口）。"""
    from app.core.audit import record_audit

    record_audit(
        db, account=operator, module="account", action=action,
        target_type=target_type, target_id=str(target_id), detail=detail,
    )


def get_menus(db: Session, account: SysAccount) -> list[dict]:
    """返回当前账号可见菜单（License 模块开关 ∩ RBAC 菜单级权限）。

    super_admin 角色直通全量；其余账号仅返回拥有 menu:/xxx 权限点的菜单。
    """
    from sqlalchemy import select

    from app.modules.license import service as license_service  # 延迟导入避免循环
    from app.modules.rbac.models import SysAccountRole, SysPermission, SysRole, SysRolePermission

    is_super = db.scalar(
        select(SysRole.id)
        .join(SysAccountRole, SysAccountRole.role_id == SysRole.id)
        .where(SysAccountRole.account_id == account.id, SysRole.code == "super_admin")
    ) is not None
    if is_super:
        allowed_routes = None  # None = 全量
    else:
        allowed_routes = set(db.scalars(
            select(SysPermission.route)
            .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
            .join(SysAccountRole, SysAccountRole.role_id == SysRolePermission.role_id)
            .where(SysAccountRole.account_id == account.id, SysPermission.route.is_not(None))
        ).all())

    menus = []
    for m in _MENUS:
        gate = _MENU_FEATURE_GATE.get(m["path"])
        if gate and not license_service.feature_enabled(db, gate):
            continue
        if allowed_routes is not None and m["path"] not in allowed_routes:
            continue
        menus.append(m)
    return menus
