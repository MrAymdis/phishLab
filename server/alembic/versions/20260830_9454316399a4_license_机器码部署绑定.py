"""license_机器码部署绑定

Revision ID: 9454316399a4
Revises: 9b3d5c7e2f1a
Create Date: 2026-08-30 11:37:14.148034

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9454316399a4'
down_revision: Union[str, None] = '9b3d5c7e2f1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 仅授权部署绑定列；autogenerate 附带的其他注释漂移/索引重命名已剔除（无功能变化）
    op.add_column('license', sa.Column('machine_code', sa.String(length=64), nullable=True,
                                       comment='部署机器指纹（部署绑定）'))


def downgrade() -> None:
    op.drop_column('license', 'machine_code')
