"""RBAC 权限树补种：ai:manage 权限点

Revision ID: 9b3d5c7e2f1a
Revises: a7f2c9d4e1b3
Create Date: 2026-08-30 12:00:00.000000

背景：AI 模块 /api/v1/ai/providers* 接口 require_perm("ai:manage")
（LLM Provider 接入/管理），但 4a9c6e71b2d8 权限树补种时"智能助手"
菜单下只种了 ai:review（草稿审核），漏种 ai:manage。自定义角色在角色
编辑页权限树"全选"也拿不到该权限点，智能助手页 Provider 相关接口一律
报"无操作权限（ai:manage）"。

本迁移把该权限点幂等补种（INSERT IGNORE 按 perm_code 唯一约束去重），
挂到 menu:/ai 下、type=3 与其余功能权限点一致。已有自定义角色如需该
权限，需在角色编辑页重新勾选保存（不自动授权，避免权限静默扩张）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "9b3d5c7e2f1a"
down_revision: Union[str, None] = "a7f2c9d4e1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    t = sa.table(
        "sys_permission",
        sa.column("id", sa.BigInteger),
        sa.column("parent_id", sa.BigInteger),
        sa.column("name", sa.String(64)),
        sa.column("perm_code", sa.String(128)),
        sa.column("type", sa.Integer),
        sa.column("route", sa.String(128)),
        sa.column("sort", sa.Integer),
    )
    conn = op.get_bind()
    menu_id = conn.execute(
        sa.select(t.c.id).where(t.c.perm_code == "menu:/ai")
    ).scalar()
    if menu_id is None:
        return  # 菜单权限点不存在（异常环境）：跳过，不产生孤儿权限点
    conn.execute(
        mysql.insert(t).prefix_with("IGNORE").values(
            parent_id=menu_id, name="LLM Provider 接入/管理", perm_code="ai:manage",
            type=3, route="", sort=1050,
        )
    )


def downgrade() -> None:
    t = sa.table("sys_permission", sa.column("perm_code", sa.String(128)))
    conn = op.get_bind()
    conn.execute(sa.delete(t).where(t.c.perm_code == "ai:manage"))
