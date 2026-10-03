from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
_engine=None
_factory=None
def db_enabled():return bool((settings.DATABASE_URL or "").strip())
def get_engine(url=None):
    global _engine
    target=(url or settings.DATABASE_URL or "").strip()
    if not target: raise RuntimeError("DATABASE_URL 未配置")
    if url:return create_engine(target,pool_pre_ping=True,future=True)
    if _engine is None:_engine=create_engine(target,pool_pre_ping=True,future=True)
    return _engine
def get_sessionmaker():
    global _factory
    if _factory is None:_factory=sessionmaker(bind=get_engine(),autoflush=False,expire_on_commit=False,future=True)
    return _factory
