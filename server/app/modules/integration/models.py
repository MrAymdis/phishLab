"""系统集成域：Webhook、SIEM。"""
from sqlalchemy import JSON, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class WebhookConfig(Base, TimestampMixin):
    __tablename__ = "webhook_config"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    im_type: Mapped[str | None] = mapped_column(String(12), comment="wecom/dingtalk/feishu/custom")
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    event_types: Mapped[list] = mapped_column(JSON, comment="campaign_done/high_risk/new_real_phish...")
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class SiemConfig(Base, TimestampMixin):
    __tablename__ = "siem_config"

    id: Mapped[int] = pk()
    host: Mapped[str] = mapped_column(String(128), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=514)
    protocol: Mapped[str] = mapped_column(String(8), default="udp")
    format: Mapped[str] = mapped_column(String(8), default="cef", comment="cef/json")
    event_types: Mapped[list | None] = mapped_column(JSON)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
