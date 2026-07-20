"""Alembic 环境：加载 app.db.base.metadata；连接串优先 env DATABASE_URL；不自动执行迁移。"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import metadata  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 连接串优先级：env DATABASE_URL > 应用配置 effective_database_url（MySQL-only 收口后默认 MySQL）
#              > alembic.ini 占位默认。确保迁移默认落 MySQL，不再回落 PostgreSQL 占位。
env_url = os.environ.get("DATABASE_URL", "").strip()
if not env_url:
    try:
        from app.core.config import settings  # noqa: E402
        env_url = (settings.effective_database_url or "").strip()
    except Exception:
        env_url = ""
if env_url:
    config.set_main_option("sqlalchemy.url", env_url)

target_metadata = metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_comments=False)
    with context.begin_transaction():
        context.run_migrations()


def _ensure_wide_version_table(connectable) -> None:
    """预建/加宽 alembic_version.version_num 到 VARCHAR(255)。

    Alembic 默认 version_num 为 VARCHAR(32)，而本项目部分 revision id（如
    0010_13b_p2_status_change_program，33 字符）超过 32，导致 UPDATE 截断报
    1406 Data too long，全链迁移在 0010 处中断。此处在迁移前主动加宽，兼顾
    全新库（预建）与既有库（ALTER）。仅 MySQL 需要，其它方言跳过。

    关键：在【独立且显式 commit 的连接】上完成，避免遗留未提交事务，
    导致 SA 2.0 在连接关闭时回滚 alembic 的 version 戳（DML）。"""
    if connectable.dialect.name != "mysql":
        return
    from sqlalchemy import text
    with connectable.connect() as c:
        c.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            "version_num VARCHAR(255) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)) "
            "DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
        c.execute(text(
            "ALTER TABLE alembic_version MODIFY version_num VARCHAR(255) NOT NULL"))
        c.commit()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    _ensure_wide_version_table(connectable)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_comments=False)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
