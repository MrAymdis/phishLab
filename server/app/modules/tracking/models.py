"""追踪域模型（无管理端路由；事件由 track 边缘服务写入，此处供迁移与查询）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pk


class TrackEvent(Base):
    """行为事件大表：生产按月分区，按数据留存策略清理。"""

    __tablename__ = "track_event"

    id: Mapped[int] = pk()
    campaign_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    token: Mapped[str | None] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(
        String(12), index=True, comment="open/click/submit/report/attach_run/bounce"
    )
    ip: Mapped[str | None] = mapped_column(String(64))
    ua: Mapped[str | None] = mapped_column(String(512))
    fingerprint_id: Mapped[int | None] = mapped_column(BigInteger)
    detail: Mapped[dict | None] = mapped_column(JSON, comment="脱敏后:字段名集合/长度/链接/耗时")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Fingerprint(Base):
    __tablename__ = "fingerprint"

    id: Mapped[int] = pk()
    fp_hash: Mapped[str] = mapped_column(String(32), unique=True, comment="Canvas/WebGL/字体/时区等合成")
    guess_user_id: Mapped[int | None] = mapped_column(BigInteger, comment="推断关联员工")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    seen_count: Mapped[int] = mapped_column(Integer, default=0)
