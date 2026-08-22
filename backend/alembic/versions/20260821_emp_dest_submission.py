"""SP-E02/E04: structured EmpDestinationSubmission + real single-node workflow.

Revision ID: 20260821_emp_dest_submission
Revises: 20260821_emp_dest_doc
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260821_emp_dest_submission"
down_revision = "20260821_emp_dest_doc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_emp_destination_submission",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), nullable=False),
        sa.Column("emp_student_id", sa.BigInteger(), nullable=True),
        sa.Column("destination_type", sa.String(length=50), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("job_title", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("contact", sa.String(length=100), nullable=True),
        sa.Column("remark", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'SUBMITTED'")),
        sa.Column("return_reason", sa.String(length=500), nullable=True),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("current_task_id", sa.BigInteger(), nullable=True),
        sa.Column("decision_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_t_emp_destination_submission_tenant_id", "t_emp_destination_submission",
                    ["tenant_id"], unique=False)
    op.create_index("ix_emp_dest_sub_student_id", "t_emp_destination_submission",
                    ["student_id"], unique=False)
    op.create_index("ix_emp_dest_sub_emp_student_id", "t_emp_destination_submission",
                    ["emp_student_id"], unique=False)
    op.create_index("ix_emp_dest_sub_workflow_instance_id", "t_emp_destination_submission",
                    ["workflow_instance_id"], unique=False)
    op.create_index("ix_emp_dest_sub_tenant_student_status", "t_emp_destination_submission",
                    ["tenant_id", "student_id", "status", "is_deleted"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_emp_dest_sub_tenant_student_status", table_name="t_emp_destination_submission")
    op.drop_index("ix_emp_dest_sub_workflow_instance_id", table_name="t_emp_destination_submission")
    op.drop_index("ix_emp_dest_sub_emp_student_id", table_name="t_emp_destination_submission")
    op.drop_index("ix_emp_dest_sub_student_id", table_name="t_emp_destination_submission")
    op.drop_index("ix_t_emp_destination_submission_tenant_id", table_name="t_emp_destination_submission")
    op.drop_table("t_emp_destination_submission")
