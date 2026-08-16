"""Alembic 环境：从应用配置读取 DATABASE_URL，元数据来自全部模块 models。"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base

# 导入所有模块模型，注册到 Base.metadata（顺序无关）
from app.modules import (  # noqa: F401
    account, rbac, org, campaign, tracking, template, channel,
    training, report, analytics, ai, openapi_mod, integration,
    license as license_mod, settings as settings_mod,
)
from app.modules.account import models as _m_account  # noqa: F401
from app.modules.rbac import models as _m_rbac  # noqa: F401
from app.modules.org import models as _m_org  # noqa: F401
from app.modules.campaign import models as _m_campaign  # noqa: F401
from app.modules.tracking import models as _m_tracking  # noqa: F401
from app.modules.template import models as _m_template  # noqa: F401
from app.modules.channel import models as _m_channel  # noqa: F401
from app.modules.training import models as _m_training  # noqa: F401
from app.modules.report import models as _m_report  # noqa: F401
from app.modules.analytics import models as _m_analytics  # noqa: F401
from app.modules.ai import models as _m_ai  # noqa: F401
from app.modules.openapi_mod import models as _m_openapi  # noqa: F401
from app.modules.integration import models as _m_integration  # noqa: F401
from app.modules.license import models as _m_license  # noqa: F401
from app.modules.settings import models as _m_settings  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 环境变量 DATABASE_URL 优先（便于验证/CI 覆盖）
config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", settings.database_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
