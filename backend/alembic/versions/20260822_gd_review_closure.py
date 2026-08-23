"""W7 review closure: formal review evidence snapshot + append-only feedback.

Revision ID: 20260822_gd_review_closure
Revises: 20260820_teacher_emp_reco
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260822_gd_review_closure"
down_revision = "20260820_teacher_emp_reco"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_gd_review", sa.Column("material_id", sa.BigInteger(), nullable=True))
    op.add_column("t_gd_review", sa.Column("file_version_id", sa.BigInteger(), nullable=True))
    op.add_column("t_gd_review", sa.Column("source_sha256", sa.String(length=64), nullable=True))
    op.add_column("t_gd_review", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.create_index("ix_gd_review_frozen_version", "t_gd_review", ["tenant_id", "file_version_id"], unique=False)
    op.create_index("ix_gd_review_material", "t_gd_review", ["tenant_id", "material_id"], unique=False)

    op.create_table(
        "t_gd_review_feedback",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
        sa.Column("gd_student_id", sa.BigInteger(), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("source_record_id", sa.BigInteger(), nullable=False),
        sa.Column("review_id", sa.BigInteger(), nullable=True),
        sa.Column("material_id", sa.BigInteger(), nullable=True),
        sa.Column("file_version_id", sa.BigInteger(), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("round_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=True),
        sa.Column("summary", sa.String(length=2000), nullable=True),
        sa.Column("result", sa.String(length=30), nullable=False),
        sa.Column("reviewer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_mentor_id", sa.BigInteger(), nullable=True),
        sa.Column("visible_to_student", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("is_superseded", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_gd_review_feedback_idem"),
    )
    op.create_index("ix_gd_feedback_batch_stage", "t_gd_review_feedback", ["tenant_id", "batch_id", "stage", "created_at", "id"], unique=False)
    op.create_index("ix_gd_feedback_source", "t_gd_review_feedback", ["tenant_id", "stage", "source_record_id", "created_at", "id"], unique=False)
    op.create_index("ix_gd_feedback_student_version", "t_gd_review_feedback", ["tenant_id", "gd_student_id", "file_version_id", "created_at", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_gd_feedback_student_version", table_name="t_gd_review_feedback")
    op.drop_index("ix_gd_feedback_source", table_name="t_gd_review_feedback")
    op.drop_index("ix_gd_feedback_batch_stage", table_name="t_gd_review_feedback")
    op.drop_table("t_gd_review_feedback")
    op.drop_index("ix_gd_review_material", table_name="t_gd_review")
    op.drop_index("ix_gd_review_frozen_version", table_name="t_gd_review")
    op.drop_column("t_gd_review", "started_at")
    op.drop_column("t_gd_review", "source_sha256")
    op.drop_column("t_gd_review", "file_version_id")
    op.drop_column("t_gd_review", "material_id")
