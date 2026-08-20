"""举报域：邮件举报记录、积分流水。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class MailReport(Base, TimestampMixin):
    __tablename__ = "mail_report"

    id: Mapped[int] = pk()
    channel: Mapped[str] = mapped_column(String(16), comment="outlook_plugin/webmail/manual/api")
    reporter_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    reporter_email: Mapped[str | None] = mapped_column(String(128))
    message_id: Mapped[str | None] = mapped_column(String(255))
    from_addr: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(512))
    eml_path: Mapped[str | None] = mapped_column(String(512))
    headers: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(
        String(16), default="pending", index=True,
        comment="pending/drill/real_phishing/false_positive/spam",
    )
    classifier: Mapped[str | None] = mapped_column(String(8), comment="auto/manual")
    matched_campaign_id: Mapped[int | None] = mapped_column(BigInteger)
    handler_id: Mapped[int | None] = mapped_column(BigInteger)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)
    handle_remark: Mapped[str | None] = mapped_column(String(512))
    reward_points: Mapped[int] = mapped_column(Integer, default=0)


class ReportRewardLog(Base):
    __tablename__ = "report_reward_log"

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    report_id: Mapped[int | None] = mapped_column(BigInteger)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class ReportRewardItem(Base):
    """举报积分兑换商品（奖品目录）。"""
    __tablename__ = "report_reward_item"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16))
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class ReportRedemption(Base):
    """兑换记录：员工扣积分换奖品。"""
    __tablename__ = "report_redemption"

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    item_id: Mapped[int] = mapped_column(BigInteger)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
