"""campaign 演练级追踪落地域覆盖

Revision ID: 14d2a51b4a95
Revises: 6675f488dacb
Create Date: 2026-08-26 17:10:33.529480

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '14d2a51b4a95'
down_revision: Union[str, None] = '6675f488dacb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaign', sa.Column('track_base_url', sa.String(length=128), nullable=True,
                                        comment='演练级追踪域覆盖，空=全局设置'))
    op.add_column('campaign', sa.Column('landing_base_url', sa.String(length=128), nullable=True,
                                        comment='演练级落地域覆盖，空=全局设置'))


def downgrade() -> None:
    op.drop_column('campaign', 'landing_base_url')
    op.drop_column('campaign', 'track_base_url')
