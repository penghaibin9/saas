"""R9 选课、考勤、考务、成绩统一名单消费证据表。

仅新增兼容表，不改写存量业务记录；历史考勤、考务、成绩任务保持无快照，
由试点前欠账扫描显式识别，禁止迁移时按课程名或行政班猜测。

Revision ID: 0129_aa_roster_consumer_snapshot
Revises: 0128_aa_grade_course_identity
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0129_aa_roster_consumer_snapshot"
down_revision = "0128_aa_grade_course_identity"
branch_labels = None
depends_on = None

_TABLE = "t_aa_roster_consumer_snapshot"


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _indexes(bind):
    return {row["name"] for row in inspect(bind).get_indexes(_TABLE)} if _TABLE in _tables(bind) else set()


def _uniques(bind):
    return {row["name"] for row in inspect(bind).get_unique_constraints(_TABLE)} if _TABLE in _tables(bind) else set()


def _ensure_index(bind, name, columns):
    if _TABLE in _tables(bind) and name not in _indexes(bind):
        op.create_index(name, _TABLE, columns)


def _ensure_unique(bind, name, columns):
    if _TABLE in _tables(bind) and name not in _uniques(bind) and name not in _indexes(bind):
        op.create_unique_constraint(name, _TABLE, columns)


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in _tables(bind):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("consumer_type", sa.String(length=40), nullable=False),
            sa.Column("consumer_id", sa.BigInteger(), nullable=False),
            sa.Column("teaching_task_id", sa.BigInteger(), nullable=False),
            sa.Column("teaching_class_id", sa.BigInteger(), nullable=True),
            sa.Column("roster_version_id", sa.BigInteger(), nullable=True),
            sa.Column("roster_version_no", sa.Integer(), nullable=True),
            sa.Column("roster_source", sa.String(length=40), nullable=False),
            sa.Column("roster_hash", sa.String(length=64), nullable=False),
            sa.Column("member_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("student_ids_json", sa.Text(), nullable=False),
            sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("captured_by", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
            sa.UniqueConstraint("tenant_id", "consumer_type", "consumer_id", name="uk_aa_roster_consumer"),
        )

    _ensure_unique(bind, "uk_aa_roster_consumer", ["tenant_id", "consumer_type", "consumer_id"])
    for name, columns in (
        ("ix_aa_roster_consumer_tenant", ["tenant_id"]),
        ("ix_aa_roster_consumer_business", ["tenant_id", "consumer_type", "consumer_id", "status"]),
        ("ix_aa_roster_consumer_task", ["tenant_id", "teaching_task_id"]),
        ("ix_aa_roster_consumer_class", ["tenant_id", "teaching_class_id"]),
        ("ix_aa_roster_consumer_version", ["tenant_id", "roster_version_id"]),
        ("ix_aa_roster_consumer_hash", ["tenant_id", "roster_hash"]),
    ):
        _ensure_index(bind, name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE in _tables(bind):
        op.drop_table(_TABLE)
