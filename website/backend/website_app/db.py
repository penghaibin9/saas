"""Website-owned MySQL connection; never falls back to the student service."""
import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

class DBNotEnabledError(RuntimeError):
    pass

def database_url():
    raw = os.environ.get('WEBSITE_DATABASE_URL', '')
    if not raw:
        raise DBNotEnabledError('未配置官网专用数据库')
    url = make_url(raw)
    if url.get_backend_name() != 'mysql' or not (url.database or '').startswith(('yueke_website_', 'test_website_')):
        raise DBNotEnabledError('仅允许官网独立 MySQL 数据库，拒绝连接学校业务库')
    if url.username == 'root':
        raise DBNotEnabledError('官网服务必须使用专用数据库账号')
    return url

@lru_cache
def get_engine():
    return create_engine(database_url(), pool_pre_ping=True, pool_recycle=1800, hide_parameters=True,
                         connect_args={'connect_timeout': 5, 'read_timeout': 30, 'write_timeout': 30})

@lru_cache
def get_sessionmaker():
    return sessionmaker(get_engine(), expire_on_commit=False)
