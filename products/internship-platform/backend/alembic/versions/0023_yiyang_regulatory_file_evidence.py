"""Yiyang C07/G18 regulatory template/output file evidence.

Revision ID: ix0023
Revises: ix0022
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0023"
down_revision = "ix0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_internship_regulatory_template_version",
        sa.Column("source_file_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "t_internship_regulatory_template_version",
        sa.Column("source_file_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "t_internship_regulatory_template_version",
        sa.Column("source_file_sha256", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_ix_reg_tpl_source_file",
        "t_internship_regulatory_template_version",
        ["tenant_id", "source_file_id", "is_deleted"],
    )

    op.add_column(
        "t_internship_regulatory_task",
        sa.Column("output_file_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "t_internship_regulatory_task",
        sa.Column("error_file_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_ix_reg_task_output_file",
        "t_internship_regulatory_task",
        ["tenant_id", "output_file_id"],
    )
    op.create_index(
        "ix_ix_reg_task_error_file",
        "t_internship_regulatory_task",
        ["tenant_id", "error_file_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ix_reg_task_error_file", table_name="t_internship_regulatory_task")
    op.drop_index("ix_ix_reg_task_output_file", table_name="t_internship_regulatory_task")
    op.drop_column("t_internship_regulatory_task", "error_file_id")
    op.drop_column("t_internship_regulatory_task", "output_file_id")

    op.drop_index("ix_ix_reg_tpl_source_file", table_name="t_internship_regulatory_template_version")
    op.drop_column("t_internship_regulatory_template_version", "source_file_sha256")
    op.drop_column("t_internship_regulatory_template_version", "source_file_name")
    op.drop_column("t_internship_regulatory_template_version", "source_file_id")
