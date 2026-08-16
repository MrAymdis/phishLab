"""平台账号与登录日志。注意：平台账号 ≠ 演练目标员工（emp_user）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class SysAccount(Base, TimestampMixin):
    __tablename__ = "sys_account"

    id: Mapped[int] = pk()
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    emp_user_id: Mapped[int | None] = mapped_column(BigInteger, comment="可选:关联员工档案")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1启用 0禁用")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class LoginLog(Base, TimestampMixin):
    __tablename__ = "login_log"

    id: Mapped[int] = pk()
    account_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    login_type: Mapped[str] = mapped_column(String(16), comment="local/sso_oidc/sso_cas/ldap")
    success: Mapped[int] = mapped_column(Integer)
    fail_reason: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(String(64))
    ua: Mapped[str | None] = mapped_column(String(255))
