"""init core tables — 第一批 19 张核心表（冻结册 §4.1/4.2/4.3/4.6/4.7 + 模块13/14/15/16/17）

Revision ID: 0001_init_core_tables
Revises:
Create Date: 2026-07-04

实现说明：第一版直接以 app.models 的 metadata 建表（与模型定义单一事实来源，
避免手写漂移）；P3 接真实 PostgreSQL 后改用 `alembic revision --autogenerate`
生成精确 DDL 差量。本迁移不自动执行、不 drop 既有数据表以外的任何东西。
"""
from __future__ import annotations

from alembic import op

revision = "0001_init_core_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.base import metadata
    bind = op.get_bind()
    metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.db.base import metadata
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
