"""RBAC：角色/权限/关联 + 审计日志。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class SysRole(Base, TimestampMixin):
    __tablename__ = "sys_role"

    id: Mapped[int] = pk()
    code: Mapped[str] = mapped_column(String(32), unique=True, comment="super_admin/operator/auditor")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    data_scope: Mapped[int] = mapped_column(Integer, default=1, comment="1全部 2本部门及子级 3本部门 4仅本人 5自定义")
    remark: Mapped[str | None] = mapped_column(String(255))


class SysPermission(Base, TimestampMixin):
    __tablename__ = "sys_permission"

    id: Mapped[int] = pk()
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    perm_code: Mapped[str] = mapped_column(String(128), unique=True, comment="如 campaign:create")
    type: Mapped[int] = mapped_column(Integer, comment="1菜单 2按钮 3接口")
    route: Mapped[str | None] = mapped_column(String(128), comment="前端路由")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class SysRolePermission(Base):
    __tablename__ = "sys_role_permission"

    role_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    permission_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class SysAccountRole(Base):
    __tablename__ = "sys_account_role"

    account_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class SysRoleDept(Base):
    """data_scope=5 时的自定义可见部门。"""

    __tablename__ = "sys_role_dept"

    role_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dept_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class AuditLog(Base):
    """审计日志：只记创建时间，不可更新。"""

    __tablename__ = "audit_log"

    id: Mapped[int] = pk()
    account_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    account_name: Mapped[str | None] = mapped_column(String(64))
    module: Mapped[str] = mapped_column(String(32), index=True, comment="campaign/template/channel/ai/license...")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSON, comment="变更摘要/前后值")
    ip: Mapped[str | None] = mapped_column(String(64))
    ua: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
