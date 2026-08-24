"""campaign_attachment 关联表 + 目标/统计附件追踪字段

Revision ID: a1c3e5a7b9d1
Revises: af400606d2a8
Create Date: 2026-08-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c3e5a7b9d1'
down_revision: Union[str, None] = '68fd1f123734'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 演练↔附件载荷关联（一期直发模式 inline）
    op.create_table('campaign_attachment',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('campaign_id', sa.BigInteger(), nullable=False),
        sa.Column('payload_id', sa.BigInteger(), nullable=False),
        sa.Column('deliver_mode', sa.String(length=8), nullable=False, server_default='inline'),
        sa.Column('sort', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_campaign_attachment')),
        sa.UniqueConstraint('campaign_id', 'payload_id', name='uk_campaign_payload'),
    )
    op.create_index(op.f('ix_campaign_attachment_campaign_id'), 'campaign_attachment', ['campaign_id'])
    # 目标：附件打开计数 + 变体文件留痕（溯源/合规证据）
    op.add_column('campaign_target', sa.Column('attach_run_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('campaign_target', sa.Column('first_attach_run_at', sa.DateTime(), nullable=True))
    op.add_column('campaign_target', sa.Column('last_attach_run_at', sa.DateTime(), nullable=True))
    op.add_column('campaign_target', sa.Column('attach_variant_path', sa.String(length=512), nullable=True))
    op.add_column('campaign_target', sa.Column('attach_variant_hash', sa.String(length=64), nullable=True))
    # 冗余计数表：附件运行人数
    op.add_column('campaign_stat', sa.Column('attach_cnt', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('campaign_stat', 'attach_cnt')
    op.drop_column('campaign_target', 'attach_variant_hash')
    op.drop_column('campaign_target', 'attach_variant_path')
    op.drop_column('campaign_target', 'last_attach_run_at')
    op.drop_column('campaign_target', 'first_attach_run_at')
    op.drop_column('campaign_target', 'attach_run_count')
    op.drop_index(op.f('ix_campaign_attachment_campaign_id'), table_name='campaign_attachment')
    op.drop_table('campaign_attachment')
