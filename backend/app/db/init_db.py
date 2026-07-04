"""
开发辅助建表（不在启动时自动调用；生产一律走 Alembic）。
用法（显式手动）：
    from app.db.init_db import create_all
    create_all()   # 仅当 DB_ENABLED=true
禁止：自动 drop、自动重置数据。
"""
from __future__ import annotations

from app.db.base import metadata
from app.db.session import get_engine


def create_all(url: str | None = None) -> None:
    metadata.create_all(bind=get_engine(url))
