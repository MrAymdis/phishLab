"""素材域：邮件模板、落地页、表单字段、附件载荷、二维码。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MediumText, TimestampMixin, pk


class EmailTemplate(Base, TimestampMixin):
    __tablename__ = "email_template"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    scene: Mapped[str] = mapped_column(String(16), comment="finance/hr/system/holiday/prize/security")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_body: Mapped[str] = mapped_column(MediumText, nullable=False)
    variables: Mapped[list | None] = mapped_column(JSON, comment="使用的变量清单")
    source: Mapped[str] = mapped_column(String(12), default="builtin", comment="builtin/custom/ai/cloned")
    status: Mapped[str] = mapped_column(String(12), default="draft", comment="draft/approved")
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class LandingPage(Base, TimestampMixin):
    __tablename__ = "landing_page"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(24), comment="mail_login/oa_login/pan_auth/custom/cloned")
    slug: Mapped[str] = mapped_column(String(48), unique=True, comment="URL: /p/{slug}")
    html_content: Mapped[str | None] = mapped_column(MediumText)
    page_schema: Mapped[dict | None] = mapped_column(JSON, comment="构建器区块描述")
    form_schema: Mapped[dict | None] = mapped_column(JSON, comment="表单字段定义")
    source: Mapped[str] = mapped_column(String(12), default="builtin")
    clone_from_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(12), default="draft")
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class LandingFormField(Base):
    __tablename__ = "landing_form_field"

    id: Mapped[int] = pk()
    page_id: Mapped[int] = mapped_column(BigInteger, index=True)
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(64))
    input_type: Mapped[str] = mapped_column(String(16), default="text")
    sensitive_flag: Mapped[int] = mapped_column(Integer, default=0, comment="1=口令类,脱敏存储")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class AttachmentPayload(Base, TimestampMixin):
    __tablename__ = "attachment_payload"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), comment="macro_doc/exe/other")
    file_path: Mapped[str] = mapped_column(String(512), comment="MinIO隔离桶")
    file_hash: Mapped[str | None] = mapped_column(String(64))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class AttachmentDownloadLog(Base):
    __tablename__ = "attachment_download_log"

    id: Mapped[int] = pk()
    payload_id: Mapped[int] = mapped_column(BigInteger, index=True)
    account_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(16), comment="download/delete")
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class QrAsset(Base, TimestampMixin):
    __tablename__ = "qr_asset"

    id: Mapped[int] = pk()
    name: Mapped[str | None] = mapped_column(String(128))
    landing_page_id: Mapped[int] = mapped_column(BigInteger)
    short_code: Mapped[str] = mapped_column(String(12), unique=True)
    img_path: Mapped[str | None] = mapped_column(String(512))
