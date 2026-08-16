"""RBAC / 审计路由（服务逻辑一期实现）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import response as resp
from app.core.deps import get_current_account
from app.core.errors import BizError, ErrorCode
from app.core.pagination import page_params
from app.db.session import get_db

roles = APIRouter(prefix="/api/v1/roles", tags=["系统设置-RBAC"], dependencies=[Depends(get_current_account)])
audit = APIRouter(prefix="/api/v1/audit-logs", tags=["系统设置-审计"], dependencies=[Depends(get_current_account)])
login_logs = APIRouter(prefix="/api/v1/login-logs", tags=["系统设置-审计"], dependencies=[Depends(get_current_account)])
routers = [roles, audit, login_logs]


@roles.get("", summary="角色列表")
def list_roles(db: Session = Depends(get_db)):
    from .models import SysRole

    return resp.ok([{"id": r.id, "code": r.code, "name": r.name, "data_scope": r.data_scope}
                    for r in db.query(SysRole).all()])


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
