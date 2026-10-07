from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL 未配置，拒绝执行 Standalone migration")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
