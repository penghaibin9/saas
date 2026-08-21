"""Teacher V3 T7: first-class employment recommendation fact.

Revision ID: 20260820_teacher_emp_reco
Revises: 20260818_acad_bc_final

Copied from the already-merged Teacher V3 line so this PR can reconcile both
unreleased schema branches before it is merged into main.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260820_teacher_emp_reco"
down_revision = "20260818_acad_bc_final"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_emp_recommendation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("emp_student_id", sa.BigInteger(), nullable=False),
        sa.Column("student_profile_id", sa.BigInteger(), nullable=True),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=True),
        sa.Column("teacher_name", sa.String(length=100), nullable=True),
        sa.Column("company_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("job_title_snapshot", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'RECOMMENDED'")),
        sa.Column("outcome", sa.String(length=50), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("outcome_note", sa.String(length=500), nullable=True),
        sa.Column("recommended_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_t_emp_recommendation_tenant_id", "t_emp_recommendation", ["tenant_id"], unique=False)
    op.create_index("ix_emp_reco_student_status", "t_emp_recommendation", ["tenant_id", "emp_student_id", "status", "is_deleted"], unique=False)
    op.create_index("ix_emp_reco_job_status", "t_emp_recommendation", ["tenant_id", "job_id", "status", "is_deleted"], unique=False)
    op.create_index("ix_emp_reco_teacher_time", "t_emp_recommendation", ["tenant_id", "teacher_user_id", "recommended_at", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_emp_reco_teacher_time", table_name="t_emp_recommendation")
    op.drop_index("ix_emp_reco_job_status", table_name="t_emp_recommendation")
    op.drop_index("ix_emp_reco_student_status", table_name="t_emp_recommendation")
    op.drop_index("ix_t_emp_recommendation_tenant_id", table_name="t_emp_recommendation")
    op.drop_table("t_emp_recommendation")
