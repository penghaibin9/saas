"""学生心理健康自评：建表 t_affairs_psy_survey_submission（原始作答+算术汇总分，非诊断）。

全新业务表，downgrade drop。幂等：inspect 判表。

Revision ID: 0082_affairs_psy_survey
Revises: 0081_13b_attendance
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0082_affairs_psy_survey"
down_revision = "0081_13b_attendance"
branch_labels = None
depends_on = None

TABLE = "t_affairs_psy_survey_submission"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("answers_json", sa.Text(), nullable=False),
            sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("wants_contact", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("triggered_referral_id", sa.BigInteger()),
            sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_psy_survey_student", TABLE, ["tenant_id", "student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
