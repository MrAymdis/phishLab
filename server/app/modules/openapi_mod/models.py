"""开放平台域：应用、调用日志。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class OpenApp(Base, TimestampMixin):
    __tablename__ = "open_app"

    id: Mapped[int] = pk()
    app_id: Mapped[str] = mapped_column(String(32), unique=True)
    app_secret_enc: Mapped[bytes] = mapped_column(LargeBinary, comment="AES-GCM加密")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    scopes: Mapped[list] = mapped_column(JSON, comment="campaign/user/template/report/mail_report/system")
    ip_whitelist: Mapped[list | None] = mapped_column(JSON)
    callback_url: Mapped[str | None] = mapped_column(String(255))
    rate_limit: Mapped[int] = mapped_column(Integer, default=60, comment="次/分钟")
    status: Mapped[str] = mapped_column(String(12), default="active", comment="active/disabled")
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class OpenApiLog(Base):
    """调用日志：量大时二期迁 ES。"""

    __tablename__ = "open_api_log"

    id: Mapped[int] = pk()
    app_id: Mapped[str] = mapped_column(String(32), index=True)
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(255))
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(64))
    req_body: Mapped[str | None] = mapped_column(Text)
    resp_body: Mapped[str | None] = mapped_column(Text)
    error_msg: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
