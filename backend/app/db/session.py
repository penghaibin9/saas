"""
数据库会话
────────────────────────────────────────────────────────────
- 默认 DB_ENABLED=false：不创建 engine、不连库、不建表、不删表。
- DB_ENABLED=true 时按 effective_database_url 惰性创建 engine/session。
  支持 sqlite（本地 dev，默认，保留）/ mysql（部署演示）/ postgresql。
- 测试环境用 TEST_DATABASE_URL（SQLite 内存库）。
- 永不自动 drop/reset；建表只允许经 Alembic 迁移或显式 init_db / init_mysql_db（开发用）。
"""
from __future__ import annotations

from typing import Iterator, Optional

from app.core.config import settings

_engine = None
_SessionLocal = None


class DBNotEnabledError(RuntimeError):
    def __init__(self):
        super().__init__(
            "数据库未启用（DB_ENABLED=false 或连接串为空）。当前接口走 mock 数据；"
            "如需连库：在 backend/.env 设置 DB_ENABLED=true 与 DB_DRIVER=mysql + DB_* "
            "（或直接 DATABASE_URL），见 backend/README.md。"
        )


def _engine_kwargs(url: str) -> dict:
    """按方言给出安全的 engine 参数。"""
    head = url.split(":", 1)[0].lower()
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if head.startswith("mysql") or head.startswith("mariadb"):
        # MySQL：连接池 + 回收，规避 wait_timeout；charset 已在 URL 上（utf8mb4）
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE,
        )
    elif head.startswith("sqlite"):
        # SQLite：允许跨线程（FastAPI 多线程访问同一文件库）
        kwargs["connect_args"] = {"check_same_thread": False}
    elif head.startswith("postgresql") or head.startswith("postgres"):
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE,
        )
    return kwargs


def get_engine(url: Optional[str] = None):
    """惰性创建 engine；DB_ENABLED=false 且未显式给 url 时抛友好错误。"""
    global _engine
    target = url or (settings.effective_database_url if settings.DB_ENABLED else "")
    if not target:
        raise DBNotEnabledError()
    if _engine is None or url:
        from sqlalchemy import create_engine
        engine = create_engine(target, **_engine_kwargs(target))
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
    return bool(settings.DB_ENABLED and settings.effective_database_url)


def reset_state() -> None:
    """重置 engine/session 缓存（切换 DATABASE_URL / 测试夹具用）。"""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
