"""AI 域：Provider 配置、会话、消息、草稿审核、用量。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Date, DateTime, Integer, LargeBinary, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MediumText, TimestampMixin, pk


class AiProvider(Base, TimestampMixin):
    __tablename__ = "ai_provider"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(16), comment="openai/claude/wenxin/tongyi/local")
    endpoint: Mapped[str | None] = mapped_column(String(255))
    api_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    model: Mapped[str | None] = mapped_column(String(64))
    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.70"))
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    system_prompt: Mapped[str | None] = mapped_column(String(4000))
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    data_outbound: Mapped[int] = mapped_column(Integer, default=1, comment="0=数据不外发(仅本地模型)")


class AiSession(Base):
    __tablename__ = "ai_session"

    id: Mapped[int] = pk()
    account_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str | None] = mapped_column(String(128))
    page_context: Mapped[dict | None] = mapped_column(JSON, comment="页面上下文快照")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class AiMessage(Base):
    __tablename__ = "ai_message"

    id: Mapped[int] = pk()
    session_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(12), comment="user/assistant/system")
    content: Mapped[str | None] = mapped_column(MediumText)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class AiDraft(Base):
    """AI 产出统一草稿审核：先草稿、人工确认后入库（全局硬约束）。"""

    __tablename__ = "ai_draft"

    id: Mapped[int] = pk()
    biz_type: Mapped[str] = mapped_column(
        String(24), index=True, comment="email_template/landing_page/course/report_summary"
    )
    biz_id: Mapped[int | None] = mapped_column(BigInteger, comment="确认入库后回填")
    title: Mapped[str | None] = mapped_column(String(128))
    content: Mapped[str | None] = mapped_column(MediumText)
    status: Mapped[str] = mapped_column(String(12), default="draft", comment="draft/approved/discarded")
    session_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class AiUsageStat(Base):
    __tablename__ = "ai_usage_stat"
    __table_args__ = (UniqueConstraint("provider_id", "stat_date", name="uq_ai_usage_provider_date"),)

    id: Mapped[int] = pk()
    provider_id: Mapped[int] = mapped_column(BigInteger)
    stat_date: Mapped[date] = mapped_column(Date)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_out: Mapped[int] = mapped_column(BigInteger, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
