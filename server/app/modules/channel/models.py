"""发送配置域：发送通道、伪装发件人、演练域名 DNS、日发送量。"""
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class SendChannel(Base, TimestampMixin):
    __tablename__ = "send_channel"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(8), comment="smtp/ews/sms/wecom")
    # SMTP
    smtp_host: Mapped[str | None] = mapped_column(String(128))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_encrypt: Mapped[str | None] = mapped_column(String(12), comment="starttls/ssl/none")
    smtp_username: Mapped[str | None] = mapped_column(String(128))
    smtp_password_enc: Mapped[bytes | None] = mapped_column(LargeBinary, comment="AES-GCM加密")
    # EWS
    ews_url: Mapped[str | None] = mapped_column(String(255))
    ews_username: Mapped[str | None] = mapped_column(String(128))
    ews_password_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    ews_auth_mode: Mapped[str | None] = mapped_column(String(8), comment="basic/oauth2")
    oauth_client_id: Mapped[str | None] = mapped_column(String(128))
    oauth_client_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    oauth_tenant_id: Mapped[str | None] = mapped_column(String(128))
    # SMS
    sms_provider: Mapped[str | None] = mapped_column(
        String(16), comment="aliyun/tencent/huawei/netease/custom_http/serial_4g"
    )
    sms_api_url: Mapped[str | None] = mapped_column(String(255))
    sms_sign: Mapped[str | None] = mapped_column(String(64))
    sms_key: Mapped[str | None] = mapped_column(String(128))
    sms_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    sms_template_id: Mapped[str | None] = mapped_column(String(64))
    serial_port: Mapped[str | None] = mapped_column(String(64))
    baud_rate: Mapped[int | None] = mapped_column(Integer)
    sim_number: Mapped[str | None] = mapped_column(String(32))
    # 企业微信（自建应用消息 API）
    wecom_corp_id: Mapped[str | None] = mapped_column(String(64))
    wecom_agent_id: Mapped[str | None] = mapped_column(String(32))
    wecom_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary, comment="应用 Secret，AES-GCM加密（红线2）")
    wecom_app_name: Mapped[str | None] = mapped_column(String(64), comment="应用显示名（仅展示；企微侧自定义名称/头像）")
    daily_limit: Mapped[int] = mapped_column(Integer, default=5000, comment="每日上限,超限顺延")
    is_default: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default="normal", comment="normal/abnormal/disabled")
    last_test_result: Mapped[dict | None] = mapped_column(JSON)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime)


class SenderProfile(Base, TimestampMixin):
    __tablename__ = "sender_profile"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(8), comment="mail/sms")
    channel_id: Mapped[int | None] = mapped_column(BigInteger, comment="关联发送通道ID，空=用默认SMTP通道")
    display_name: Mapped[str | None] = mapped_column(String(128), comment="发件人显示名称")
    from_addr: Mapped[str | None] = mapped_column(String(128), comment="发件邮箱(需绑定已配域名)")
    reply_to: Mapped[str | None] = mapped_column(String(128))
    sms_number: Mapped[str | None] = mapped_column(String(32))
    sms_sign: Mapped[str | None] = mapped_column(String(64))
    scene_tags: Mapped[list | None] = mapped_column(
        JSON, comment='["finance","hr","system","holiday","prize","security"]'
    )


class PhishDomain(Base, TimestampMixin):
    __tablename__ = "phish_domain"

    id: Mapped[int] = pk()
    domain: Mapped[str] = mapped_column(String(128), unique=True)
    purpose: Mapped[str | None] = mapped_column(String(255))
    spf_status: Mapped[str] = mapped_column(String(8), default="unknown", comment="ok/fail/unknown")
    dkim_status: Mapped[str] = mapped_column(String(8), default="unknown")
    dmarc_status: Mapped[str] = mapped_column(String(16), default="unknown",
                                              comment="p= 值 reject/quarantine/none，无记录 fail，查询失败 unknown")
    mx_status: Mapped[str] = mapped_column(String(8), default="unknown")
    deliver_score: Mapped[int] = mapped_column(Integer, default=0, comment="送达评分0-100")
    repair_tips: Mapped[str | None] = mapped_column(Text)
    dkim_selector: Mapped[str] = mapped_column(String(32), default="phish")
    dkim_public_key: Mapped[str | None] = mapped_column(Text)
    dkim_private_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="active")


class SendQuotaUsage(Base):
    __tablename__ = "send_quota_usage"
    __table_args__ = (UniqueConstraint("channel_id", "stat_date", name="uq_quota_channel_date"),)

    id: Mapped[int] = pk()
    channel_id: Mapped[int] = mapped_column(BigInteger)
    stat_date: Mapped[date] = mapped_column(Date)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
