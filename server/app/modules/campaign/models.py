"""演练域：演练主体、目标明细、批次、实时统计、预警。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaign"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024))
    type: Mapped[str] = mapped_column(String(16), comment="mail/sms/social/usb")
    status: Mapped[str] = mapped_column(
        String(16), default="draft", index=True,
        comment="draft/scheduled/sending/running/paused/completed/terminated",
    )
    creator_id: Mapped[int] = mapped_column(BigInteger, index=True)
    template_id: Mapped[int | None] = mapped_column(BigInteger)
    landing_page_id: Mapped[int | None] = mapped_column(BigInteger)
    channel_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_profile_id: Mapped[int | None] = mapped_column(BigInteger)
    # 演练级追踪/落地域覆盖（成对生效，空=沿用全局设置，见 settings.service.resolve_track_urls）
    track_base_url: Mapped[str | None] = mapped_column(String(128), comment="演练级追踪域覆盖，空=全局设置")
    landing_base_url: Mapped[str | None] = mapped_column(String(128), comment="演练级落地域覆盖，空=全局设置")
    target_mode: Mapped[str | None] = mapped_column(String(16), comment="dept/tag/csv/mix")
    target_snapshot: Mapped[dict | None] = mapped_column(JSON, comment="圈选条件快照")
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    schedule_type: Mapped[str] = mapped_column(String(8), default="now", comment="now/timed")
    schedule_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    batch_count: Mapped[int] = mapped_column(Integer, default=1)
    batch_interval_min: Mapped[int] = mapped_column(Integer, default=0)
    randomize_content: Mapped[int] = mapped_column(Integer, default=0, comment="内容随机化")
    time_jitter_sec: Mapped[int] = mapped_column(Integer, default=0, comment="发送时刻抖动")
    pixel_degrade: Mapped[int] = mapped_column(Integer, default=0, comment="追踪像素降级")
    training_policy: Mapped[str] = mapped_column(String(8), default="none", comment="redirect/popup/none/url")
    training_redirect_url: Mapped[str | None] = mapped_column(
        String(512), comment="url 模式：提交后 302 跳转的自定义页面"
    )
    course_ids: Mapped[list | None] = mapped_column(JSON, comment="关联培训课程")
    force_training_rules: Mapped[list | None] = mapped_column(JSON, comment="强制培训触发条件")
    auth_confirmed: Mapped[int] = mapped_column(Integer, default=0, comment="授权确认勾选")
    auth_snapshot: Mapped[list | None] = mapped_column(
        JSON, comment="授权勾选项快照（企微演练含 4 项专有条款，红线4）")
    wecom_template_id: Mapped[int | None] = mapped_column(BigInteger, comment="企微消息模板（social 演练用）")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class CampaignTarget(Base, TimestampMixin):
    __tablename__ = "campaign_target"
    __table_args__ = (
        UniqueConstraint("campaign_id", "user_id", name="uq_campaign_target_user"),
        # 投递列表/失败列表按状态过滤 + 按发送时间排序
        Index("ix_campaign_target_send_status_sent_at", "send_status", "sent_at"),
    )

    id: Mapped[int] = pk()
    campaign_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    batch_no: Mapped[int] = mapped_column(Integer, default=1)
    token: Mapped[str] = mapped_column(String(32), unique=True, comment="唯一追踪令牌")
    send_status: Mapped[str] = mapped_column(
        String(12), default="pending", comment="pending/sent/delivered/bounced/failed"
    )
    fail_reason: Mapped[str | None] = mapped_column(
        String(500), comment="投递失败原因（SMTP 拒收/认证失败/超时等）"
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    first_open_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_open_at: Mapped[datetime | None] = mapped_column(DateTime)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    first_click_at: Mapped[datetime | None] = mapped_column(DateTime)
    submit_flag: Mapped[int] = mapped_column(Integer, default=0)
    submit_at: Mapped[datetime | None] = mapped_column(DateTime)
    report_flag: Mapped[int] = mapped_column(Integer, default=0)
    report_at: Mapped[datetime | None] = mapped_column(DateTime)
    attach_run_count: Mapped[int] = mapped_column(Integer, default=0)
    first_attach_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_attach_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    attach_variant_path: Mapped[str | None] = mapped_column(
        String(512), comment="附件变体文件路径（溯源留痕）"
    )
    attach_variant_hash: Mapped[str | None] = mapped_column(String(64), comment="附件变体 sha256")
    fingerprint_id: Mapped[int | None] = mapped_column(BigInteger)
    training_assignment_id: Mapped[int | None] = mapped_column(BigInteger)


class CampaignAttachment(Base):
    """演练↔附件载荷关联（一期直发模式 deliver_mode=inline）。"""

    __tablename__ = "campaign_attachment"
    __table_args__ = (UniqueConstraint("campaign_id", "payload_id", name="uk_campaign_payload"),)

    id: Mapped[int] = pk()
    campaign_id: Mapped[int] = mapped_column(BigInteger, index=True)
    payload_id: Mapped[int] = mapped_column(BigInteger)
    deliver_mode: Mapped[str] = mapped_column(String(8), default="inline", comment="inline/link")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class CampaignBatch(Base, TimestampMixin):
    __tablename__ = "campaign_batch"
    __table_args__ = (UniqueConstraint("campaign_id", "batch_no", name="uq_campaign_batch"),)

    id: Mapped[int] = pk()
    campaign_id: Mapped[int] = mapped_column(BigInteger, index=True)
    batch_no: Mapped[int] = mapped_column(Integer)
    plan_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="pending", comment="pending/sending/done/failed")
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class CampaignStat(Base):
    """实时计数冗余表：Redis 定时回写，供列表页快速读取。"""

    __tablename__ = "campaign_stat"

    campaign_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    delivered_cnt: Mapped[int] = mapped_column(Integer, default=0)
    open_cnt: Mapped[int] = mapped_column(Integer, default=0)
    click_cnt: Mapped[int] = mapped_column(Integer, default=0)
    submit_cnt: Mapped[int] = mapped_column(Integer, default=0)
    report_cnt: Mapped[int] = mapped_column(Integer, default=0)
    attach_cnt: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CampaignAlert(Base):
    __tablename__ = "campaign_alert"

    id: Mapped[int] = pk()
    campaign_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type: Mapped[str] = mapped_column(
        String(32), comment="pwd_submit/exec_user/dept_threshold/fast_submit/repeat_n/"
                            "wecom_bounce/wecom_no_userid/wecom_channel_error"
    )
    level: Mapped[int] = mapped_column(Integer, default=2)
    message: Mapped[str] = mapped_column(String(512))
    target_user_id: Mapped[int | None] = mapped_column(BigInteger)
    handled: Mapped[int] = mapped_column(Integer, default=0)
    handled_by: Mapped[int | None] = mapped_column(BigInteger)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
