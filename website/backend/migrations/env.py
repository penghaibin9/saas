from alembic import context
from website_app.db import get_engine, Base
from website_app import auth
from website_app import consultations
from website_app.news import models
from website_app.integrations import routes

if context.is_offline_mode():
    raise RuntimeError('官网迁移须连接已核验的专用数据库')
with get_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
