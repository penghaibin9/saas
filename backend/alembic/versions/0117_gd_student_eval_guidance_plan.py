"""毕设 P2：导师对学生评价表 + 指导计划签到表。

Revision ID: 0117_gd_student_eval_guidance_plan
Revises: 0116_gd_student_org_scope
Create Date: 2026-07-23

区别于既有 t_gd_mentor_eval（学院评导师）：本迁移新增导师→学生过程评价，
以及指导计划条目（签到字段落在计划行上，MVP 一计划一次签到）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0117_gd_student_eval_guidance_plan"
down_revision = "0116_gd_student_org_scope"
branch_labels = None
depends_on = None

NEW_TABLES = ("t_gd_student_eval", "t_gd_guidance_plan")


def _has(bind, table: str) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    from app.models import Base

    bind = op.get_bind()
    for table in NEW_TABLES:
        if not _has(bind, table) and table in Base.metadata.tables:
            Base.metadata.tables[table].create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        if _has(bind, table):
            op.execute(f"DROP TABLE IF EXISTS `{table}`")
