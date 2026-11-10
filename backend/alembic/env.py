import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings

# 引入基础配置
config = context.config

# 配置 Python 统一日志记录器
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 动态将配置中的数据库 URI 注入 Alembic
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)

# 后续 ORM 模型元数据将挂载在此处，当前为空
from app.models import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成可离线执行的纯 SQL 变更脚本"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：使用 asyncpg 异步引擎直接对数据库执行迁移"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
