"""组织与员工（演练对象）：部门树、员工档案、分组标签、风险画像、同步任务。"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, BigInteger, DateTime, Integer, LargeBinary, Numeric, String,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pk


class EmpDept(Base, TimestampMixin):
    __tablename__ = "emp_dept"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_emp_dept_source"),)

    id: Mapped[int] = pk()
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0)
    path: Mapped[str] = mapped_column(String(512), comment="/1/5/12/ 加速祖先查询")
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64))
    sort: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str | None] = mapped_column(String(16), comment="manual/ldap/wecom/dingtalk/feishu")
    source_id: Mapped[str | None] = mapped_column(String(128), comment="外部系统ID")


class EmpUser(Base, TimestampMixin):
    __tablename__ = "emp_user"

    id: Mapped[int] = pk()
    emp_no: Mapped[str | None] = mapped_column(String(64), comment="工号")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    mobile_enc: Mapped[bytes | None] = mapped_column(LargeBinary, comment="加密存储,展示掩码")
    dept_id: Mapped[int] = mapped_column(BigInteger, index=True)
    position: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1在职 0离职停用")
    initial_risk: Mapped[int] = mapped_column(Integer, default=70, comment="初始风险值0-100")
    source: Mapped[str] = mapped_column(String(16), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(128))


class EmpGroup(Base, TimestampMixin):
    __tablename__ = "emp_group"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))


class EmpGroupMember(Base):
    __tablename__ = "emp_group_member"

    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class EmpTag(Base, TimestampMixin):
    __tablename__ = "emp_tag"

    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(32), unique=True)
    color: Mapped[str | None] = mapped_column(String(16))


class EmpUserTag(Base):
    __tablename__ = "emp_user_tag"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tag_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class EmpRiskProfile(Base):
    """员工风险画像：定时任务增量重算。"""

    __tablename__ = "emp_risk_profile"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    total_score: Mapped[int] = mapped_column(Integer, default=70, comment="综合风险分0-100")
    email_recognize: Mapped[int] = mapped_column(Integer, default=70, comment="邮件识别维度")
    link_click: Mapped[int] = mapped_column(Integer, default=70, comment="链接点击维度")
    pwd_submit: Mapped[int] = mapped_column(Integer, default=70, comment="密码提交维度")
    attach_run: Mapped[int] = mapped_column(Integer, default=70, comment="附件下载维度")
    report_awareness: Mapped[int] = mapped_column(Integer, default=70, comment="举报意识维度")
    phish_count: Mapped[int] = mapped_column(Integer, default=0, comment="历史中招次数")
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    training_completion: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, comment="培训完成度%")
    risk_level: Mapped[int] = mapped_column(Integer, default=1, comment="1低(0-70) 2中(71-80) 3高(81-100)")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OrgSyncJob(Base, TimestampMixin):
    __tablename__ = "org_sync_job"

    id: Mapped[int] = pk()
    source: Mapped[str] = mapped_column(String(16), comment="ldap/wecom/dingtalk/feishu")
    config_enc: Mapped[bytes | None] = mapped_column(LargeBinary, comment="连接配置加密")
    cron: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[int] = mapped_column(Integer, default=1)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_result: Mapped[dict | None] = mapped_column(JSON)
