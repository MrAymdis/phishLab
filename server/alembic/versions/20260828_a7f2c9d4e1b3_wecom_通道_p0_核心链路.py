"""企业微信通道 P0：通道扩列 + 员工 userid + 演练授权快照 + 企微消息模板

Revision ID: a7f2c9d4e1b3
Revises: 4a9c6e71b2d8
Create Date: 2026-08-28 10:00:00.000000

背景：企业微信通道（自建应用 message/send 投递）核心链路，见
《企业微信通道设计方案》§11 P0。OAuth 溯源（track_event.wecom_visitor_user_id、
/wx/cb 回调）属 P1，本迁移不含。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7f2c9d4e1b3"
down_revision: Union[str, None] = "4a9c6e71b2d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. send_channel 扩列（宽表模式，同 sms_*/ews_* 风格）
    op.add_column("send_channel", sa.Column("wecom_corp_id", sa.String(64), nullable=True))
    op.add_column("send_channel", sa.Column("wecom_agent_id", sa.String(32), nullable=True))
    op.add_column("send_channel", sa.Column("wecom_secret_enc", sa.LargeBinary(), nullable=True))
    op.add_column("send_channel", sa.Column("wecom_app_name", sa.String(64), nullable=True))

    # 2. emp_user 增企业微信身份（目标展开用，唯一索引）
    op.add_column("emp_user", sa.Column("wecom_userid", sa.String(64), nullable=True))
    op.create_index("uk_emp_wecom_userid", "emp_user", ["wecom_userid"], unique=True)

    # 3. campaign：授权勾选项快照（企微 4 项专有条款）+ 企微消息模板
    op.add_column("campaign", sa.Column("auth_snapshot", sa.JSON(), nullable=True))
    op.add_column("campaign", sa.Column("wecom_template_id", sa.BigInteger(), nullable=True))

    # 4. wecom_template 新表（P0 手工维护版；AI 审核流 P1 接入）
    op.create_table(
        "wecom_template",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("msg_type", sa.String(16), nullable=False, server_default="textcard"),
        sa.Column("title", sa.String(128), nullable=True),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("btn_text", sa.String(16), nullable=False, server_default="查看详情"),
        sa.Column("url_mode", sa.String(16), nullable=False, server_default="track"),
        sa.Column("custom_url", sa.String(255), nullable=True),
        sa.Column("media_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("wecom_template")
    op.drop_column("campaign", "wecom_template_id")
    op.drop_column("campaign", "auth_snapshot")
    op.drop_index("uk_emp_wecom_userid", table_name="emp_user")
    op.drop_column("emp_user", "wecom_userid")
    op.drop_column("send_channel", "wecom_app_name")
    op.drop_column("send_channel", "wecom_secret_enc")
    op.drop_column("send_channel", "wecom_agent_id")
    op.drop_column("send_channel", "wecom_corp_id")
