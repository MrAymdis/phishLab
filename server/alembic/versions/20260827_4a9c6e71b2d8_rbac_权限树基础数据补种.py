"""RBAC 权限树基础数据补种：sys_permission 菜单/功能权限点

Revision ID: 4a9c6e71b2d8
Revises: bdfe7e3fa834
Create Date: 2026-08-27 12:00:00.000000

背景：基础权限点此前仅由 scripts/seed_demo.py（开发演示数据）播种，
生产部署（POST /api/v1/auth/init 或 seed_admin.py 初始化）不运行该脚本，
导致 sys_permission 为空——角色编辑页权限树无数据、自定义角色无法授权。
本迁移把权限树作为平台基础数据在迁移链里幂等补种（INSERT IGNORE 按
perm_code 唯一约束去重，dev 库已由 seed_demo 播种则全部跳过）。

数据：11 个菜单权限点（menu:/xxx，type=1）+ 13 个功能权限点（type=3，
parent_id 挂对应菜单）+ 1 个按钮权限点（system:account，type=2）；
super_admin 角色绑定全部菜单权限点（与 seed_demo 一致，保证角色编辑页
勾选态展示；功能权限 super_admin 代码层直通无需绑定）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "4a9c6e71b2d8"
down_revision: Union[str, None] = "bdfe7e3fa834"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MENUS = [
    ("数据概览", "/dashboard"), ("演练管理", "/campaign"), ("素材模板", "/template"),
    ("发送配置", "/send-config"), ("用户和组", "/users"), ("安全培训", "/training"),
    ("数据报表", "/reports"), ("邮件举报", "/mail-report"), ("系统设置", "/settings"),
    ("智能助手", "/ai"), ("API开放平台", "/openapi"),
]

# (perm_code, 所属菜单路由, 名称, 备注)
_FUNCS = [
    ("campaign:create", "/campaign", "创建/复制演练", ""),
    ("campaign:control", "/campaign", "启动/暂停/恢复/终止/暂存/测试发送", ""),
    ("campaign:delete", "/campaign", "删除演练", ""),
    ("campaign:reveal", "/campaign", "提交事件取证解密（红线）", ""),
    ("channel:manage", "/send-config", "通道/域名/伪装发件人增删改与测试发信", ""),
    ("template:manage", "/template", "邮件模板/落地页增删改与克隆（红线）", ""),
    ("settings:manage", "/settings", "平台参数修改（留存期等红线配置）", ""),
    ("license:manage", "/settings", "License 激活/离线导入", ""),
    ("report:classify", "/mail-report", "举报人工研判", ""),
    ("org:manage", "/users", "部门/员工/标签增删改", ""),
    ("training:manage", "/training", "课程/培训任务增删改", ""),
    ("ai:review", "/ai", "AI 草稿审核（入库/丢弃）", ""),
    ("openapi:manage", "/openapi", "开放平台应用创建/管理", ""),
]

# 页面/按钮级权限点（type=2，不在 seed_demo 列表但被 accounts 路由 require_perm 引用）
_BUTTONS = [
    ("system:account", "/settings", "平台账号管理"),
]


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

    # 1. 菜单权限点（幂等：perm_code 唯一约束 + INSERT IGNORE）
    for i, (name, route) in enumerate(_MENUS):
        conn.execute(
            mysql.insert(t).prefix_with("IGNORE").values(
                parent_id=0, name=name, perm_code=f"menu:{route}",
                type=1, route=route, sort=i,
            )
        )

    # 2. 功能权限点挂到对应菜单下
    for i, (code, menu_route, name, remark) in enumerate(_FUNCS):
        menu_id = conn.execute(
            sa.select(t.c.id).where(t.c.perm_code == f"menu:{menu_route}")
        ).scalar()
        if menu_id is None:
            continue
        conn.execute(
            mysql.insert(t).prefix_with("IGNORE").values(
                parent_id=menu_id, name=name, perm_code=code,
                type=3, route="", sort=1000 + i,
            )
        )

    # 2.5 页面/按钮级权限点（type=2）：挂对应菜单下，sort 按代码内约定
    for i, (code, menu_route, name) in enumerate(_BUTTONS):
        menu_id = conn.execute(
            sa.select(t.c.id).where(t.c.perm_code == f"menu:{menu_route}")
        ).scalar()
        if menu_id is None:
            continue
        conn.execute(
            mysql.insert(t).prefix_with("IGNORE").values(
                parent_id=menu_id, name=name, perm_code=code,
                type=2, route="", sort=80,
            )
        )

    # 3. super_admin 绑定全部菜单权限点（角色编辑页勾选态展示一致；幂等）
    role_id = conn.execute(
        sa.text("SELECT id FROM sys_role WHERE code = 'super_admin' LIMIT 1")
    ).scalar()
    if role_id is None:
        return
    rp = sa.table(
        "sys_role_permission",
        sa.column("role_id", sa.BigInteger),
        sa.column("permission_id", sa.BigInteger),
    )
    menu_ids = conn.execute(
        sa.select(t.c.id).where(t.c.perm_code.like("menu:%"))
    ).scalars().all()
    for mid in menu_ids:
        conn.execute(
            mysql.insert(rp).prefix_with("IGNORE").values(
                role_id=role_id, permission_id=mid,
            )
        )


def downgrade() -> None:
    t = sa.table(
        "sys_permission",
        sa.column("id", sa.BigInteger),
        sa.column("perm_code", sa.String(128)),
    )
    conn = op.get_bind()
    codes = [f"menu:{route}" for _n, route in _MENUS] + [c for c, *_ in _FUNCS] \
        + [c for c, *_ in _BUTTONS]
    conn.execute(sa.delete(t).where(t.c.perm_code.in_(codes)))
