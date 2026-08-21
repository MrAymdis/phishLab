"""RBAC / 审计路由：角色列表/创建/详情/权限保存 + 审计日志。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.audit import record_audit
from app.core.deps import get_current_account, require_perm
from app.core.errors import BizError, ErrorCode
from app.core.pagination import page_params
from app.db.session import get_db

roles = APIRouter(prefix="/api/v1/roles", tags=["系统设置-RBAC"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/settings"))])
audit = APIRouter(prefix="/api/v1/audit-logs", tags=["系统设置-审计"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/settings"))])
login_logs = APIRouter(prefix="/api/v1/login-logs", tags=["系统设置-审计"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/settings"))])
routers = [roles, audit, login_logs]


class RolePayload(BaseModel):
    """创建/更新自定义角色：基本信息 + 权限点全量覆盖。"""

    name: str = Field(..., min_length=1, max_length=64, description="角色名称")
    code: str = Field("", max_length=32, description="角色标识（创建时必填，更新时忽略）")
    data_scope: int = Field(1, ge=1, le=5, description="1全部 2本部门及子级 3本部门 4仅本人 5自定义")
    remark: str | None = Field(None, max_length=255)
    permission_ids: list[int] = Field(default_factory=list, description="权限点全量覆盖")


@roles.get("", summary="角色列表（含人数）")
def list_roles(db: Session = Depends(get_db)):
    from .models import SysAccountRole, SysRole

    cnt = dict(db.execute(
        select(SysAccountRole.role_id, func.count()).group_by(SysAccountRole.role_id)
    ).all())
    return resp.ok([
        {
            "id": r.id, "code": r.code, "name": r.name,
            "data_scope": r.data_scope, "remark": r.remark or "",
            "user_count": cnt.get(r.id, 0),
        }
        for r in db.query(SysRole).all()
    ])


@roles.get("/permissions", summary="权限点全量（前端组树）")
def list_permissions(db: Session = Depends(get_db)):
    from .models import SysPermission

    rows = db.query(SysPermission).order_by(SysPermission.sort, SysPermission.id).all()
    return resp.ok([
        {
            "id": p.id, "parent_id": p.parent_id, "name": p.name,
            "perm_code": p.perm_code, "type": p.type,
        }
        for p in rows
    ])


@roles.post("", summary="创建自定义角色", dependencies=[Depends(require_perm("settings:manage"))])
def create_role(payload: RolePayload, account=Depends(get_current_account), db: Session = Depends(get_db)):
    from .models import SysRole, SysRolePermission

    code = payload.code.strip() or payload.name.strip()
    if db.scalar(select(SysRole).where(SysRole.code == code)):
        raise BizError(ErrorCode.PARAM_INVALID, f"角色标识 {code} 已存在")
    role = SysRole(
        code=code, name=payload.name.strip(),
        data_scope=payload.data_scope, remark=(payload.remark or "").strip() or None,
    )
    db.add(role)
    db.flush()
    for pid in dict.fromkeys(payload.permission_ids):  # 去重
        db.add(SysRolePermission(role_id=role.id, permission_id=pid))
    db.commit()
    record_audit(
        db, account=account, module="rbac", action="create_role",
        target_type="role", target_id=str(role.id),
        detail={"name": role.name, "code": role.code, "perms": len(payload.permission_ids)},
    )
    return resp.ok({"id": role.id})


@roles.get("/{role_id}", summary="角色详情（含权限点）")
def get_role(role_id: int, db: Session = Depends(get_db)):
    from .models import SysRole, SysRolePermission

    role = db.get(SysRole, role_id)
    if not role:
        raise BizError(ErrorCode.NOT_FOUND, "角色不存在")
    perm_ids = db.scalars(
        select(SysRolePermission.permission_id).where(SysRolePermission.role_id == role_id)
    ).all()
    return resp.ok({
        "id": role.id, "code": role.code, "name": role.name,
        "data_scope": role.data_scope, "remark": role.remark or "",
        "permission_ids": perm_ids,
    })


@roles.put("/{role_id}", summary="更新角色信息与权限（权限全量覆盖）",
           dependencies=[Depends(require_perm("settings:manage"))])
def update_role(role_id: int, payload: RolePayload,
                account=Depends(get_current_account), db: Session = Depends(get_db)):
    from .models import SysRole, SysRolePermission

    role = db.get(SysRole, role_id)
    if not role:
        raise BizError(ErrorCode.NOT_FOUND, "角色不存在")
    role.name = payload.name.strip()
    role.data_scope = payload.data_scope
    role.remark = (payload.remark or "").strip() or None
    # 权限点全量覆盖
    db.execute(SysRolePermission.__table__.delete().where(SysRolePermission.role_id == role_id))
    for pid in dict.fromkeys(payload.permission_ids):
        db.add(SysRolePermission(role_id=role_id, permission_id=pid))
    db.commit()
    record_audit(
        db, account=account, module="rbac", action="update_role",
        target_type="role", target_id=str(role_id),
        detail={"name": role.name, "perms": len(payload.permission_ids)},
    )
    return resp.ok(None)


@audit.get("", summary="操作日志（模块/操作人/时间筛选）")
def list_audit(
    module: str | None = None,
    kw: str | None = None,
    paging: tuple[int, int] = Depends(page_params),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func, or_, select

    from .models import AuditLog

    page, page_size = paging
    stmt = select(AuditLog)
    if module:
        stmt = stmt.where(AuditLog.module == module)
    if kw:
        like = f"%{kw}%"
        stmt = stmt.where(or_(
            AuditLog.account_name.like(like),
            AuditLog.action.like(like),
            AuditLog.target_id.like(like),
        ))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return resp.page(
        [
            {
                "id": r.id,
                "time": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "user": r.account_name,
                "action": f"{r.module}:{r.action}",
                "target": r.target_id or "",
                "ip": r.ip or "",
            }
            for r in rows
        ],
        total, page, page_size,
    )


@login_logs.get("", summary="登录日志")
def list_login_logs(paging: tuple[int, int] = Depends(page_params), db: Session = Depends(get_db)):
    from sqlalchemy import func, select

    from app.modules.account.models import LoginLog

    page, page_size = paging
    stmt = select(LoginLog)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(LoginLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return resp.page(
        [
            {
                "id": r.id,
                "time": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "user": r.username or "-",
                "ip": r.ip or "",
                "browser": r.ua or "",
                "status": "ok" if r.success == 1 else "fail",
            }
            for r in rows
        ],
        total, page, page_size,
    )
