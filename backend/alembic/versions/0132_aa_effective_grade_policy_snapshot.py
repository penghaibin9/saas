"""P0-11 有效成绩规则快照。

历史成绩不回填、不按课程名猜测；仅为迁移后新发生的正式成绩写入/更正保存不可变策略证据。

Revision ID: 0132_aa_effective_grade_policy
Revises: 0131_aa_real_semester_pilot
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0132_aa_effective_grade_policy"
down_revision = "0131_aa_real_semester_pilot"
branch_labels = None
depends_on = None

_TABLE = "t_aa_effective_grade_policy_snapshot"


def _tables(bind):
    return set(inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE in _tables(bind):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("academic_grade_id", sa.BigInteger(), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("source_biz_type", sa.String(length=50), nullable=True),
        sa.Column("source_biz_id", sa.BigInteger(), nullable=True),
        sa.Column("policy_code", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("policy_json", sa.Text(), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("identity_type", sa.String(length=30), nullable=False),
        sa.Column("identity_key", sa.String(length=300), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("course_code", sa.String(length=50), nullable=True),
        sa.Column("course_version", sa.Integer(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=True),
        sa.Column("grade_source", sa.String(length=30), nullable=True),
        sa.Column("decision_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("tenant_id", "event_key", name="uk_aa_effective_grade_policy_event"),
    )
    op.create_index("ix_aa_effective_grade_policy_grade", _TABLE, ["tenant_id", "academic_grade_id"])
    op.create_index("ix_aa_effective_grade_policy_course", _TABLE, ["tenant_id", "course_id", "attempt_no"])
    op.create_index("ix_aa_effective_grade_policy_source", _TABLE, ["tenant_id", "source_biz_type", "source_biz_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE in _tables(bind):
        op.drop_table(_TABLE)
