"""Yiyang C03/G09 configurable material collection requirements.

Revision ID: ix0005
Revises: ix0004
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0005"
down_revision = "ix0004"
branch_labels = None
depends_on = None


def _common_columns():
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
        "t_internship_material_requirement",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("material_code", sa.String(80), nullable=False),
        sa.Column("material_name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("audience_type", sa.String(30), nullable=False, server_default=sa.text("'ALL'")),
        sa.Column("audience_filter_json", sa.JSON(), nullable=True),
        sa.Column("allowed_extensions_json", sa.JSON(), nullable=True),
        sa.Column("min_files", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("max_files", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("reviewer_permission", sa.String(120), nullable=False, server_default=sa.text("'internship.material.review'")),
        sa.Column("archive_category", sa.String(80), nullable=False, server_default=sa.text("'CUSTOM_MATERIAL'")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("current_template_version_id", sa.BigInteger(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "material_code",
            name="uk_ix_material_requirement_code",
        ),
    )
    op.create_index(
        "ix_ix_material_requirement_status",
        "t_internship_material_requirement",
        ["tenant_id", "batch_id", "status", "is_deleted"],
    )
    op.create_index(
        "ix_t_internship_material_requirement_batch_id",
        "t_internship_material_requirement",
        ["batch_id"],
    )
    op.create_index(
        "ix_t_internship_material_requirement_current_template_version_id",
        "t_internship_material_requirement",
        ["current_template_version_id"],
    )
    op.create_index(
        "ix_t_internship_material_requirement_tenant_id",
        "t_internship_material_requirement",
        ["tenant_id"],
    )

    op.create_table(
        "t_internship_material_template_version",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("requirement_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name_snapshot", sa.String(300), nullable=True),
        sa.Column("sha256_snapshot", sa.String(64), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("uploaded_by_name", sa.String(100), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "requirement_id", "version_no",
            name="uk_ix_material_template_version",
        ),
    )
    op.create_index(
        "ix_ix_material_template_current",
        "t_internship_material_template_version",
        ["tenant_id", "requirement_id", "is_current", "is_deleted"],
    )
    op.create_index(
        "ix_t_internship_material_template_version_requirement_id",
        "t_internship_material_template_version",
        ["requirement_id"],
    )
    op.create_index(
        "ix_t_internship_material_template_version_file_id",
        "t_internship_material_template_version",
        ["file_id"],
    )
    op.create_index(
        "ix_t_internship_material_template_version_tenant_id",
        "t_internship_material_template_version",
        ["tenant_id"],
    )

    op.create_table(
        "t_internship_material_submission",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("requirement_id", sa.BigInteger(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("submit_comment", sa.String(500), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_name", sa.String(100), nullable=True),
        sa.Column("review_comment", sa.String(500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "requirement_id", "internship_id",
            name="uk_ix_material_submission_student_requirement",
        ),
    )
    op.create_index(
        "ix_ix_material_submission_status",
        "t_internship_material_submission",
        ["tenant_id", "batch_id", "status", "is_deleted"],
    )
    for column in ("tenant_id", "requirement_id", "internship_id", "student_id", "batch_id"):
        op.create_index(
            f"ix_t_internship_material_submission_{column}",
            "t_internship_material_submission",
            [column],
        )

    op.create_table(
        "t_internship_material_submission_file",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("submission_id", sa.BigInteger(), nullable=False),
        sa.Column("slot_no", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("current_version_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "submission_id", "slot_no",
            name="uk_ix_material_submission_slot",
        ),
    )
    op.create_index(
        "ix_ix_material_submission_file_current",
        "t_internship_material_submission_file",
        ["tenant_id", "submission_id", "is_deleted"],
    )
    for column in ("tenant_id", "submission_id", "asset_id", "current_version_id", "file_id"):
        op.create_index(
            f"ix_t_internship_material_submission_file_{column}",
            "t_internship_material_submission_file",
            [column],
        )


def downgrade() -> None:
    op.drop_table("t_internship_material_submission_file")
    op.drop_table("t_internship_material_submission")
    op.drop_table("t_internship_material_template_version")
    op.drop_table("t_internship_material_requirement")
