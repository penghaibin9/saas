"""R10 动态成绩项与教务统计冻结快照。

Revision ID: 0130_aa_dynamic_grade_stats_snapshot
Revises: 0129_aa_roster_consumer_snapshot
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0130_aa_dynamic_grade_stats_snapshot"
down_revision = "0129_aa_roster_consumer_snapshot"
branch_labels = None
depends_on = None


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _common():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)
    if "t_aa_grade_scheme_snapshot" not in tables:
        op.create_table(
            "t_aa_grade_scheme_snapshot", *_common(),
            sa.Column("grade_task_id", sa.BigInteger(), nullable=False),
            sa.Column("scheme_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("scheme_json", sa.Text(), nullable=False),
            sa.Column("total_weight", sa.Float(), nullable=False, server_default=sa.text("100")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("locked_by", sa.String(length=100), nullable=True),
            sa.UniqueConstraint("tenant_id", "grade_task_id", name="uk_aa_grade_scheme_task"),
        )
        op.create_index("ix_aa_grade_scheme_status", "t_aa_grade_scheme_snapshot", ["tenant_id", "status"])
        op.create_index("ix_aa_grade_scheme_task", "t_aa_grade_scheme_snapshot", ["grade_task_id"])

    if "t_aa_grade_component_score" not in tables:
        op.create_table(
            "t_aa_grade_component_score", *_common(),
            sa.Column("grade_task_id", sa.BigInteger(), nullable=False),
            sa.Column("grade_record_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("component_code", sa.String(length=40), nullable=False),
            sa.Column("component_name", sa.String(length=80), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("weighted_score", sa.Float(), nullable=False),
            sa.Column("scheme_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.UniqueConstraint(
                "tenant_id", "grade_task_id", "student_id", "component_code",
                name="uk_aa_grade_component_student",
            ),
        )
        op.create_index("ix_aa_grade_component_record", "t_aa_grade_component_score", ["tenant_id", "grade_record_id"])
        op.create_index("ix_aa_grade_component_task", "t_aa_grade_component_score", ["tenant_id", "grade_task_id", "student_id"])

    if "t_aa_stats_snapshot" not in tables:
        op.create_table(
            "t_aa_stats_snapshot", *_common(),
            sa.Column("snapshot_type", sa.String(length=40), nullable=False, server_default="OVERVIEW"),
            sa.Column("term_id", sa.BigInteger(), nullable=True),
            sa.Column("college_id", sa.BigInteger(), nullable=True),
            sa.Column("major_id", sa.BigInteger(), nullable=True),
            sa.Column("scope_json", sa.Text(), nullable=False),
            sa.Column("filters_json", sa.Text(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("source_as_of", sa.DateTime(), nullable=True),
            sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("generated_by", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="FROZEN"),
        )
        op.create_index("ix_aa_stats_snapshot_type", "t_aa_stats_snapshot", ["tenant_id", "snapshot_type", "status"])
        op.create_index("ix_aa_stats_snapshot_term", "t_aa_stats_snapshot", ["tenant_id", "term_id", "generated_at"])
        op.create_index("ix_aa_stats_snapshot_hash", "t_aa_stats_snapshot", ["tenant_id", "payload_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)
    for table in ("t_aa_stats_snapshot", "t_aa_grade_component_score", "t_aa_grade_scheme_snapshot"):
        if table in tables:
            op.drop_table(table)
