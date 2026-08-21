"""RBAC 权限点树状层级 + 角色菜单权限补全 + 读接口菜单守卫

Revision ID: 7f3a1b9c2d4e
Revises: 345903539c7b
Create Date: 2026-08-21 12:00:00.000000

数据迁移：
1. 功能权限点 parent_id 挂到对应菜单权限点（前端树状展示）
2. operator 补 menu:/xxx 菜单权限（此前仅有功能权限，RBAC 菜单过滤会误伤）
3. auditor 补只读菜单权限（此前无权限点）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "7f3a1b9c2d4e"
down_revision: Union[str, None] = "345903539c7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    t = sa.table(
        "sys_permission",
        sa.column("id", sa.Integer),
        sa.column("perm_code", sa.String(128)),
        sa.column("parent_id", sa.BigInteger),
    )
    # 1. 功能权限点挂到菜单权限点下（菜单 parent_id=0 为根）
    menu_of = {
        "campaign:create": "menu:/campaign",
        "campaign:control": "menu:/campaign",
        "campaign:delete": "menu:/campaign",
        "campaign:reveal": "menu:/campaign",
        "channel:manage": "menu:/send-config",
        "template:manage": "menu:/template",
        "settings:manage": "menu:/settings",
        "license:manage": "menu:/settings",
        "report:classify": "menu:/mail-report",
        "org:manage": "menu:/users",
        "training:manage": "menu:/training",
        "ai:review": "menu:/ai",
        "openapi:manage": "menu:/openapi",
        "system:account": "menu:/settings",
    }
    conn = op.get_bind()
    for perm_code, menu_code in menu_of.items():
        menu_id = conn.execute(
            sa.select(t.c.id).where(t.c.perm_code == menu_code)
        ).scalar()
        conn.execute(
            t.update().where(t.c.perm_code == perm_code).values(parent_id=menu_id)
        )

    # 2. 角色菜单权限补全（INSERT IGNORE：幂等，已存在不重复）
    rp = sa.table(
        "sys_role_permission",
        sa.column("role_id", sa.BigInteger),
        sa.column("permission_id", sa.BigInteger),
    )
    # operator（role_id=2）：有功能权限的模块补菜单可见
    operator_menus = (
        "menu:/dashboard", "menu:/campaign", "menu:/template", "menu:/send-config",
        "menu:/users", "menu:/training", "menu:/reports", "menu:/mail-report", "menu:/ai",
    )
    # auditor（role_id=3）：只读报表与审计日志
    auditor_menus = ("menu:/dashboard", "menu:/campaign", "menu:/reports", "menu:/settings")
    inserts = []
    for role_id, menus in ((2, operator_menus), (3, auditor_menus)):
        for menu_code in menus:
            perm_id = conn.execute(
                sa.select(t.c.id).where(t.c.perm_code == menu_code)
            ).scalar()
            inserts.append({"role_id": role_id, "permission_id": perm_id})
    for row in inserts:
        conn.execute(mysql.insert(rp).prefix_with("IGNORE").values(**row))


def downgrade() -> None:
    # 权限点 parent_id 还原为 0（树状层级撤销）
    t = sa.table(
        "sys_permission",
        sa.column("parent_id", sa.BigInteger),
    )
    op.get_bind().execute(t.update().values(parent_id=0))
