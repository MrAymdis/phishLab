"""授权域：License 与用量。"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class LicenseInfo(Base, TimestampMixin):
    __tablename__ = "license"

    id: Mapped[int] = pk()
    license_key: Mapped[str] = mapped_column(String(128), nullable=False)
    edition: Mapped[str] = mapped_column(String(16), comment="trial/standard/flagship")
    customer_name: Mapped[str | None] = mapped_column(String(128))
    user_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    mail_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    sms_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    campaign_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    activate_mode: Mapped[str | None] = mapped_column(String(8), comment="online/offline")
    signature: Mapped[str | None] = mapped_column(Text, comment="离线lic RSA签名")
    machine_code: Mapped[str | None] = mapped_column(String(64), comment="部署机器指纹（部署绑定）")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    expire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="active", comment="active/expired/revoked")


class LicenseUsage(Base):
    __tablename__ = "license_usage"

    id: Mapped[int] = pk()
    stat_date: Mapped[date] = mapped_column(Date, unique=True)
    mails_sent: Mapped[int] = mapped_column(Integer, default=0)
    sms_sent: Mapped[int] = mapped_column(Integer, default=0)
    campaigns_created: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
