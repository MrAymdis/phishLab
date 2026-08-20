"""平台设置：KV 表（logo/名称/版权/像素开关/留存天数/免责声明/AI开关）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pk


class PlatformSetting(Base):
    __tablename__ = "platform_setting"

    setting_key: Mapped[str] = mapped_column(
        String(64), primary_key=True,
        comment="logo/name/copyright/retention_days/disclaimer/ai_switches",
    )
    setting_value: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
