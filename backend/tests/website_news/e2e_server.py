"""Loopback-only test fixture API, never mounted by production app.main."""
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from app.api.v1 import website_news as api
from app.core.security import get_current_user
from app.core.exceptions import register_exception_handlers
url=os.environ['NEWS_TEST_DATABASE_URL']
if os.environ.get('NEWS_E2E_TEST_ONLY')!='true' or make_url(url).get_backend_name()!='mysql' or not make_url(url).database.startswith('test_'):
    raise RuntimeError('Explicit disposable MySQL test context required')
engine=create_engine(url,pool_pre_ping=True);Session=sessionmaker(engine,expire_on_commit=False)
api.get_sessionmaker=lambda:Session
app=FastAPI();register_exception_handlers(app)
app.dependency_overrides[get_current_user]=lambda:{'userId':'fixture-editor','userType':'PLATFORM_SUPER_ADMIN'}
app.include_router(api.router,prefix='/api/v1');app.include_router(api.public_api,prefix='/api/v1');app.include_router(api.public_pages)
