"""campaign 移除 domain_id（链接域改由追踪落地域配置决定）

Revision ID: 63f9409271e0
Revises: 14d2a51b4a95
Create Date: 2026-08-26 17:18:17.500245

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '63f9409271e0'
down_revision: Union[str, None] = '14d2a51b4a95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 链接域不再由演练绑定 PhishDomain 决定（SPF/DKIM 是发件域指标，与链接域无关），
    # 改由「追踪/落地域基础 URL」（演练级覆盖 > 全局设置 > .env）统一配置。
    op.drop_column('campaign', 'domain_id')
    # 顺手收敛历史 comment 漂移（模型注释早已存在，DB 未落）
    op.alter_column('campaign_attachment', 'deliver_mode',
                    existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=8),
                    comment='inline/link',
                    existing_nullable=False,
                    existing_server_default=sa.text("'inline'"))
    op.alter_column('campaign_target', 'attach_variant_path',
                    existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=512),
                    comment='附件变体文件路径（溯源留痕）',
                    existing_nullable=True)
    op.alter_column('campaign_target', 'attach_variant_hash',
                    existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=64),
                    comment='附件变体 sha256',
                    existing_nullable=True)


def downgrade() -> None:
    op.add_column('campaign', sa.Column('domain_id', mysql.BIGINT(), autoincrement=False, nullable=True))
    op.alter_column('campaign_target', 'attach_variant_hash',
                    existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=64),
                    comment=None,
                    existing_comment='附件变体 sha256',
                    existing_nullable=True)
    op.alter_column('campaign_target', 'attach_variant_path',
                    existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=512),
                    comment=None,
                    existing_comment='附件变体文件路径（溯源留痕）',
                    existing_nullable=True)
    op.alter_column('campaign_attachment', 'deliver_mode',
                    existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=8),
                    comment=None,
                    existing_comment='inline/link',
                    existing_nullable=False,
                    existing_server_default=sa.text("'inline'"))
