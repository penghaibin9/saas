"""
数据库会话（BACKEND-OVERNIGHT 阶段8）
────────────────────────────────────────────────────────────
- 默认 DB_ENABLED=false：不创建 engine、不连库、不建表、不删表。
- DB_ENABLED=true 时按 DATABASE_URL 惰性创建 engine/session（PostgreSQL）。
- 测试环境用 TEST_DATABASE_URL（SQLite 内存库）。
- 永不自动 drop/reset；建表只允许经 Alembic 迁移或显式 init_db（开发用）。
"""
from __future__ import annotations

from typing import Iterator, Optional

from app.core.config import settings

_engine = None
_SessionLocal = None


class DBNotEnabledError(RuntimeError):
    def __init__(self):
        super().__init__(
            "数据库未启用（DB_ENABLED=false）。当前接口走 mock 数据；"
            "如需连库：在 backend/.env 设置 DB_ENABLED=true 与 DATABASE_URL，见 backend/README.md。"
        )


def get_engine(url: Optional[str] = None):
    """惰性创建 engine；DB_ENABLED=false 且未显式给 url 时抛友好错误。"""
    global _engine
    target = url or (settings.DATABASE_URL if settings.DB_ENABLED else "")
    if not target:
        raise DBNotEnabledError()
    if _engine is None or url:
        from sqlalchemy import create_engine
        engine = create_engine(target, pool_pre_ping=True, future=True)
        if url:
            return engine
        _engine = engine
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        from sqlalchemy.orm import sessionmaker
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)
    return _SessionLocal


def get_db() -> Iterator:
    """FastAPI 依赖：仅在 DB_ENABLED=true 的接口分支中使用。"""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def db_enabled() -> bool:
    return bool(settings.DB_ENABLED and settings.DATABASE_URL)
