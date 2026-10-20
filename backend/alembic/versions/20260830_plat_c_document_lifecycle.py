"""Add PLAT-C document derivatives and lifecycle fact projection.

Revision ID: 20260830_plat_c_lifecycle
Revises: 20260830_plat_b_forms
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260830_plat_c_lifecycle"
down_revision = "20260830_plat_b_forms"
branch_labels = None
depends_on = None

assert len(revision) <= 32


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("t_file_derived_artifact"):
        op.create_table(
            "t_file_derived_artifact",
            *_common_columns(),
            sa.Column("source_file_version_id", sa.BigInteger(), nullable=False),
            sa.Column("source_sha256", sa.String(length=64), nullable=False),
            sa.Column("derivative_kind", sa.String(length=40), nullable=False),
            sa.Column("extractor_code", sa.String(length=80), nullable=False),
            sa.Column("extractor_version", sa.String(length=64), nullable=False),
            sa.Column("generated_file_object_id", sa.BigInteger(), nullable=True),
            sa.Column("content_sha256", sa.String(length=64), nullable=True),
            sa.Column("block_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("sensitivity_level", sa.String(length=30), nullable=False),
            sa.Column("retention_until", sa.DateTime(), nullable=True),
            sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.UniqueConstraint(
                "tenant_id", "source_file_version_id", "source_sha256", "derivative_kind",
                "extractor_code", "extractor_version", name="uk_file_derived_artifact_identity",
            ),
        )
        op.create_index("ix_t_file_derived_artifact_tenant_id", "t_file_derived_artifact", ["tenant_id"])
        op.create_index(
            "ix_t_file_derived_artifact_source_file_version_id",
            "t_file_derived_artifact", ["source_file_version_id"],
        )
        op.create_index(
            "ix_t_file_derived_artifact_generated_file_object_id",
            "t_file_derived_artifact", ["generated_file_object_id"],
        )
        op.create_index("ix_t_file_derived_artifact_status", "t_file_derived_artifact", ["status"])
        op.create_index(
            "ix_file_derived_source", "t_file_derived_artifact",
            ["tenant_id", "source_file_version_id", "status", "id"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("t_document_compare_result"):
        op.create_table(
            "t_document_compare_result",
            *_common_columns(),
            sa.Column("left_file_version_id", sa.BigInteger(), nullable=False),
            sa.Column("left_source_sha256", sa.String(length=64), nullable=False),
            sa.Column("right_file_version_id", sa.BigInteger(), nullable=False),
            sa.Column("right_source_sha256", sa.String(length=64), nullable=False),
            sa.Column("algorithm_code", sa.String(length=80), nullable=False),
            sa.Column("algorithm_version", sa.String(length=64), nullable=False),
            sa.Column("generated_file_object_id", sa.BigInteger(), nullable=True),
            sa.Column("diff_sha256", sa.String(length=64), nullable=True),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("sensitivity_level", sa.String(length=30), nullable=False),
            sa.Column("retention_until", sa.DateTime(), nullable=True),
            sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.UniqueConstraint(
                "tenant_id", "left_file_version_id", "left_source_sha256",
                "right_file_version_id", "right_source_sha256", "algorithm_code",
                "algorithm_version", name="uk_document_compare_identity",
            ),
        )
        op.create_index("ix_t_document_compare_result_tenant_id", "t_document_compare_result", ["tenant_id"])
        op.create_index(
            "ix_t_document_compare_result_left_file_version_id",
            "t_document_compare_result", ["left_file_version_id"],
        )
        op.create_index(
            "ix_t_document_compare_result_right_file_version_id",
            "t_document_compare_result", ["right_file_version_id"],
        )
        op.create_index(
            "ix_t_document_compare_result_generated_file_object_id",
            "t_document_compare_result", ["generated_file_object_id"],
        )
        op.create_index("ix_t_document_compare_result_status", "t_document_compare_result", ["status"])
        op.create_index(
            "ix_document_compare_left", "t_document_compare_result",
            ["tenant_id", "left_file_version_id", "status", "id"],
        )
        op.create_index(
            "ix_document_compare_right", "t_document_compare_result",
            ["tenant_id", "right_file_version_id", "status", "id"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("t_student_lifecycle_fact"):
        op.create_table(
            "t_student_lifecycle_fact",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("college_id", sa.BigInteger(), nullable=True),
            sa.Column("source_module", sa.String(length=64), nullable=False),
            sa.Column("fact_type", sa.String(length=80), nullable=False),
            sa.Column("source_biz_type", sa.String(length=80), nullable=False),
            sa.Column("source_biz_id", sa.String(length=100), nullable=False),
            sa.Column("source_version", sa.String(length=100), nullable=False),
            sa.Column("event_time", sa.DateTime(), nullable=False),
            sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.String(length=500), nullable=True),
            sa.Column("importance", sa.String(length=30), nullable=False, server_default="NORMAL"),
            sa.Column("visibility_code", sa.String(length=50), nullable=False),
            sa.Column("sensitivity_level", sa.String(length=30), nullable=False),
            sa.Column("target_ref_json", sa.JSON(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("dedupe_key", sa.String(length=160), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.UniqueConstraint("tenant_id", "dedupe_key", name="uk_student_lifecycle_fact_dedupe"),
        )
        op.create_index("ix_t_student_lifecycle_fact_tenant_id", "t_student_lifecycle_fact", ["tenant_id"])
        op.create_index("ix_t_student_lifecycle_fact_student_id", "t_student_lifecycle_fact", ["student_id"])
        op.create_index("ix_t_student_lifecycle_fact_college_id", "t_student_lifecycle_fact", ["college_id"])
        op.create_index(
            "ix_lifecycle_fact_timeline", "t_student_lifecycle_fact",
            ["tenant_id", "student_id", "event_time", "id"],
        )
        op.create_index(
            "ix_lifecycle_fact_module", "t_student_lifecycle_fact",
            ["tenant_id", "student_id", "source_module", "event_time", "id"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in (
        "t_student_lifecycle_fact",
        "t_document_compare_result",
        "t_file_derived_artifact",
    ):
        if inspector.has_table(table_name):
            op.drop_table(table_name)
            inspector = sa.inspect(op.get_bind())
