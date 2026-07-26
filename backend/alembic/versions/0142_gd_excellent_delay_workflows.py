"""Add graduation excellent-outcome and delayed-defense workflows.

Revision ID: 0142_gd_excellent_delay
Revises: 0141_merge_gd_intern_affairs_heads

守卫说明：0001_init_core_tables 是 metadata.create_all 活基线——全新库跑链时
会先按当前模型建出本迁移目标表，故 create_table / create_index 必须幂等。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0142_gd_excellent_delay"
down_revision = "0141_merge_gd_intern_affairs_heads"
branch_labels = None
depends_on = None


def _table_names():
    return set(inspect(op.get_bind()).get_table_names())


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return set()
    return {idx["name"] for idx in inspect(bind).get_indexes(table)}


def _common_columns():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade():
    names = _table_names()

    if "t_gd_excellent_outcome" not in names:
        op.create_table(
            "t_gd_excellent_outcome",
            *_common_columns(),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_MAJOR"),
            sa.Column("nomination_reason", sa.String(2000), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=True),
            sa.Column("grade_snapshot_json", sa.JSON(), nullable=True),
            sa.Column("nominated_by", sa.String(100), nullable=True),
            sa.Column("nominated_at", sa.DateTime(), nullable=True),
            sa.Column("major_review_comment", sa.String(1000), nullable=True),
            sa.Column("major_reviewed_by", sa.String(100), nullable=True),
            sa.Column("major_reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("college_review_comment", sa.String(1000), nullable=True),
            sa.Column("college_reviewed_by", sa.String(100), nullable=True),
            sa.Column("college_reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_excellent_student"),
        )
    excellent_indexes = _index_names("t_gd_excellent_outcome")
    if "ix_gd_excellent_outcome_tenant_id" not in excellent_indexes:
        op.create_index("ix_gd_excellent_outcome_tenant_id", "t_gd_excellent_outcome", ["tenant_id"])
    if "ix_gd_excellent_outcome_gd_student_id" not in excellent_indexes:
        op.create_index("ix_gd_excellent_outcome_gd_student_id", "t_gd_excellent_outcome", ["gd_student_id"])
    if "ix_gd_excellent_outcome_batch_id" not in excellent_indexes:
        op.create_index("ix_gd_excellent_outcome_batch_id", "t_gd_excellent_outcome", ["batch_id"])
    if "ix_gd_excellent_batch_status" not in excellent_indexes:
        op.create_index(
            "ix_gd_excellent_batch_status",
            "t_gd_excellent_outcome",
            ["tenant_id", "batch_id", "status", "is_deleted"],
        )

    names = _table_names()
    if "t_gd_defense_delay" not in names:
        op.create_table(
            "t_gd_defense_delay",
            *_common_columns(),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("active_key", sa.String(100), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_ADVISOR"),
            sa.Column("reason", sa.String(2000), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=True),
            sa.Column("requested_at", sa.DateTime(), nullable=True),
            sa.Column("advisor_comment", sa.String(1000), nullable=True),
            sa.Column("advisor_reviewed_by", sa.String(100), nullable=True),
            sa.Column("advisor_reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("major_comment", sa.String(1000), nullable=True),
            sa.Column("major_reviewed_by", sa.String(100), nullable=True),
            sa.Column("major_reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("college_comment", sa.String(1000), nullable=True),
            sa.Column("college_reviewed_by", sa.String(100), nullable=True),
            sa.Column("college_reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("planned_defense_date", sa.String(50), nullable=True),
            sa.Column("defense_group_id", sa.BigInteger(), nullable=True),
            sa.Column("scheduled_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "active_key", name="uk_gd_delay_active"),
        )
    delay_indexes = _index_names("t_gd_defense_delay")
    if "ix_gd_defense_delay_tenant_id" not in delay_indexes:
        op.create_index("ix_gd_defense_delay_tenant_id", "t_gd_defense_delay", ["tenant_id"])
    if "ix_gd_defense_delay_gd_student_id" not in delay_indexes:
        op.create_index("ix_gd_defense_delay_gd_student_id", "t_gd_defense_delay", ["gd_student_id"])
    if "ix_gd_defense_delay_batch_id" not in delay_indexes:
        op.create_index("ix_gd_defense_delay_batch_id", "t_gd_defense_delay", ["batch_id"])
    if "ix_gd_defense_delay_defense_group_id" not in delay_indexes:
        op.create_index("ix_gd_defense_delay_defense_group_id", "t_gd_defense_delay", ["defense_group_id"])
    if "ix_gd_delay_batch_status" not in delay_indexes:
        op.create_index(
            "ix_gd_delay_batch_status",
            "t_gd_defense_delay",
            ["tenant_id", "batch_id", "status", "is_deleted"],
        )


def downgrade():
    names = _table_names()
    if "t_gd_defense_delay" in names:
        op.drop_table("t_gd_defense_delay")
    if "t_gd_excellent_outcome" in names:
        op.drop_table("t_gd_excellent_outcome")
