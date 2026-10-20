"""Yiyang C07/G18 regulatory reporting templates, tasks and row snapshots.

Revision ID: ix0007
Revises: ix0006
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0007"
down_revision = "ix0006"
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade() -> None:
    op.create_table(
        "t_internship_regulatory_template_version",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("report_code", sa.String(16), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("template_name", sa.String(200), nullable=False),
        sa.Column("source_label", sa.String(120), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("official_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("field_schema_json", sa.JSON(), nullable=False),
        sa.Column("enum_schema_json", sa.JSON(), nullable=True),
        sa.Column("cross_rule_json", sa.JSON(), nullable=True),
        sa.Column("mapping_schema_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("effective_at", sa.DateTime(), nullable=True),
        sa.Column("change_reason", sa.String(500), nullable=True),
        *_common(),
        sa.UniqueConstraint("tenant_id", "report_code", "version_no", name="uk_ix_reg_tpl_version"),
    )
    op.create_index("ix_ix_reg_tpl_active", "t_internship_regulatory_template_version",
                    ["tenant_id", "report_code", "status", "is_deleted"])
    op.create_index("ix_t_internship_regulatory_template_version_tenant_id",
                    "t_internship_regulatory_template_version", ["tenant_id"])
    op.create_index("ix_t_internship_regulatory_template_version_report_code",
                    "t_internship_regulatory_template_version", ["report_code"])

    op.create_table(
        "t_internship_regulatory_task",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("task_no", sa.String(80), nullable=False),
        sa.Column("report_code", sa.String(16), nullable=False),
        sa.Column("template_version_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'GENERATED'")),
        sa.Column("status_history_json", sa.JSON(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_filename", sa.String(255), nullable=True),
        sa.Column("output_sha256", sa.String(64), nullable=True),
        sa.Column("output_size", sa.BigInteger(), nullable=True),
        sa.Column("error_filename", sa.String(255), nullable=True),
        sa.Column("error_sha256", sa.String(64), nullable=True),
        sa.Column("external_submission_ref", sa.String(200), nullable=True),
        sa.Column("receipt_code", sa.String(120), nullable=True),
        sa.Column("receipt_message", sa.String(1000), nullable=True),
        sa.Column("created_by_name", sa.String(100), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("exported_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("receipt_at", sa.DateTime(), nullable=True),
        *_common(),
        sa.UniqueConstraint("tenant_id", "task_no", name="uk_ix_reg_task_no"),
    )
    op.create_index("ix_ix_reg_task_batch", "t_internship_regulatory_task",
                    ["tenant_id", "batch_id", "report_code", "status", "is_deleted"])
    for col in ("tenant_id", "report_code", "template_version_id", "batch_id"):
        op.create_index(f"ix_t_internship_regulatory_task_{col}", "t_internship_regulatory_task", [col])

    op.create_table(
        "t_internship_regulatory_task_row",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=True),
        sa.Column("internship_id", sa.BigInteger(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("validation_errors_json", sa.JSON(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        *_common(),
        sa.UniqueConstraint("tenant_id", "task_id", "row_no", name="uk_ix_reg_task_row_no"),
    )
    op.create_index("ix_ix_reg_task_row_valid", "t_internship_regulatory_task_row",
                    ["tenant_id", "task_id", "is_valid", "is_deleted"])
    for col in ("tenant_id", "task_id", "student_id", "internship_id", "is_valid"):
        op.create_index(f"ix_t_internship_regulatory_task_row_{col}",
                        "t_internship_regulatory_task_row", [col])


def downgrade() -> None:
    op.drop_table("t_internship_regulatory_task_row")
    op.drop_table("t_internship_regulatory_task")
    op.drop_table("t_internship_regulatory_template_version")
