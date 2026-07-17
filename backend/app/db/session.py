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
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_use_lifo=True,
            connect_args={
                "connect_timeout": settings.DB_CONNECT_TIMEOUT,
                "read_timeout": settings.DB_READ_TIMEOUT,
                "write_timeout": settings.DB_WRITE_TIMEOUT,
            },
        )
    elif head.startswith("sqlite"):
        # SQLite：允许跨线程（FastAPI 多线程访问同一文件库）
        kwargs["connect_args"] = {"check_same_thread": False}
    elif head.startswith("postgresql") or head.startswith("postgres"):
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_use_lifo=True,
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
        from app.db.observability import install_engine_observers
        install_engine_observers(engine)
        if url:
            return engine
        _engine = engine
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        from sqlalchemy.orm import sessionmaker
        _install_sandbox_baseline_guard()
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)
    return _SessionLocal


_sandbox_guard_installed = False


def _install_sandbox_baseline_guard() -> None:
    """阻止业务会话硬删/软删沙箱基线；现场新增行不在索引中，可正常删除。"""
    global _sandbox_guard_installed
    if _sandbox_guard_installed:
        return
    from sqlalchemy import event, inspect, select
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    @event.listens_for(Session, "before_flush")
    def _protect_sandbox_baseline(session, _flush_context, _instances):
        from app.models.sandbox import SandboxBaseline
        from app.services.sandbox_service import SANDBOX_TID

        candidates = []
        for obj in session.deleted:
            if getattr(obj, "tenant_id", None) == SANDBOX_TID and getattr(obj, "id", None):
                candidates.append(obj)
        for obj in session.dirty:
            if getattr(obj, "tenant_id", None) != SANDBOX_TID or not getattr(obj, "id", None):
                continue
            state = inspect(obj)
            if "is_deleted" in state.attrs and state.attrs.is_deleted.history.has_changes() \
                    and getattr(obj, "is_deleted", False):
                candidates.append(obj)
        for obj in candidates:
            table_name = getattr(getattr(obj, "__table__", None), "name", "")
            if not table_name or table_name == SandboxBaseline.__tablename__:
                continue
            try:
                protected = session.scalar(select(SandboxBaseline.id).where(
                    SandboxBaseline.tenant_id == SANDBOX_TID,
                    SandboxBaseline.table_name == table_name,
                    SandboxBaseline.row_id == int(obj.id),
                ))
            except SQLAlchemyError:
                # 兼容尚未执行新迁移的开发库；迁移后自动启用硬保护。
                return
            if protected:
                from app.core.exceptions import AppException
                raise AppException(
                    "DATA_CONFLICT",
                    "这是系统预制的演示基线数据，不能删除；可编辑，也可在运营平台恢复整校演示数据。",
                    {"table": table_name, "rowId": str(obj.id), "baseline": True},
                )

    _sandbox_guard_installed = True


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
