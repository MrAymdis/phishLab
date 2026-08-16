"""报表域：离线汇总表（实时计数在 campaign_stat / Redis）。"""
from datetime import date

from sqlalchemy import BigInteger, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, pk


class StatDaily(Base):
    __tablename__ = "stat_daily"
    __table_args__ = (
        UniqueConstraint("stat_date", "dim_type", "dim_id", "dim_key", name="uq_stat_daily_dim"),
    )

    id: Mapped[int] = pk()
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    dim_type: Mapped[str] = mapped_column(String(16), comment="platform/dept/scene/user")
    dim_id: Mapped[int | None] = mapped_column(BigInteger, comment="部门ID/用户ID")
    dim_key: Mapped[str | None] = mapped_column(String(32), comment="场景标签")
    campaign_cnt: Mapped[int] = mapped_column(Integer, default=0)
    target_cnt: Mapped[int] = mapped_column(Integer, default=0)
    delivered_cnt: Mapped[int] = mapped_column(Integer, default=0)
    open_cnt: Mapped[int] = mapped_column(Integer, default=0)
    click_cnt: Mapped[int] = mapped_column(Integer, default=0)
    submit_cnt: Mapped[int] = mapped_column(Integer, default=0)
    report_cnt: Mapped[int] = mapped_column(Integer, default=0)
