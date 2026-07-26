"""Add graduation excellent-outcome and delayed-defense workflows.

Revision ID: 0142_gd_excellent_delay
Revises: 0141_merge_gd_intern_affairs_heads
"""
from alembic import op
import sqlalchemy as sa

revision = "0142_gd_excellent_delay"
down_revision = "0141_merge_gd_intern_affairs_heads"
branch_labels = None
depends_on = None


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
    op.create_index("ix_gd_excellent_outcome_tenant_id", "t_gd_excellent_outcome", ["tenant_id"])
    op.create_index("ix_gd_excellent_outcome_gd_student_id", "t_gd_excellent_outcome", ["gd_student_id"])
    op.create_index("ix_gd_excellent_outcome_batch_id", "t_gd_excellent_outcome", ["batch_id"])
    op.create_index("ix_gd_excellent_batch_status", "t_gd_excellent_outcome", ["tenant_id", "batch_id", "status", "is_deleted"])

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
    op.create_index("ix_gd_defense_delay_tenant_id", "t_gd_defense_delay", ["tenant_id"])
    op.create_index("ix_gd_defense_delay_gd_student_id", "t_gd_defense_delay", ["gd_student_id"])
    op.create_index("ix_gd_defense_delay_batch_id", "t_gd_defense_delay", ["batch_id"])
    op.create_index("ix_gd_defense_delay_defense_group_id", "t_gd_defense_delay", ["defense_group_id"])
    op.create_index("ix_gd_delay_batch_status", "t_gd_defense_delay", ["tenant_id", "batch_id", "status", "is_deleted"])


def downgrade():
    op.drop_table("t_gd_defense_delay")
    op.drop_table("t_gd_excellent_outcome")
