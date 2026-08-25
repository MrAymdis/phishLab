"""dmarc_status 加宽至16存p=值

Revision ID: 6675f488dacb
Revises: a1c3e5a7b9d1
Create Date: 2026-08-25 09:44:53.778761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6675f488dacb'
down_revision: Union[str, None] = 'a1c3e5a7b9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('phish_domain', 'dmarc_status',
               existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=8),
               type_=sa.String(length=16),
               comment='p= 值 reject/quarantine/none，无记录 fail，查询失败 unknown',
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('phish_domain', 'dmarc_status',
               existing_type=sa.String(length=16),
               type_=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=8),
               comment=None,
               existing_comment='p= 值 reject/quarantine/none，无记录 fail，查询失败 unknown',
               existing_nullable=False)
