"""E-A01 M3: student internship profile and immutable application material snapshot.

Revision ID: 20260815_internship_e_m3
Revises: 20260815_internship_e_m1

Historical applications are not backfilled with today's profile. New snapshot/application links
remain nullable for old rows. Snapshot rows are append-only and protected by MySQL triggers.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_internship_e_m3"
down_revision = "20260815_internship_e_m1"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_internship_e_m3 requires MySQL")


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def _column_names(insp, table: str) -> set[str]:
    return {column["name"] for column in insp.get_columns(table)} if insp.has_table(table) else set()


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)

    if not insp.has_table("t_internship_student_profile"):
        op.create_table(
            "t_internship_student_profile",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("profile_version", sa.Integer(), nullable=False),
            sa.Column("headline", sa.String(120)),
            sa.Column("self_intro", sa.Text()),
            sa.Column("strengths", sa.Text()),
            sa.Column("available_from", sa.Date()),
            sa.Column("available_until", sa.Date()),
            sa.Column("expected_locations_json", sa.JSON()),
            sa.Column("skill_tags_json", sa.JSON()),
            sa.Column("resume_template_code", sa.String(50), nullable=False),
            *_common_columns(),
            sa.UniqueConstraint("tenant_id", "student_id", name="uk_intern_student_profile"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_student_profile_tenant_id", "t_internship_student_profile", ["tenant_id"])
        op.create_index("ix_intern_student_profile_student", "t_internship_student_profile", ["tenant_id", "student_id", "is_deleted"])

    if not insp.has_table("t_internship_student_profile_item"):
        op.create_table(
            "t_internship_student_profile_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("profile_id", sa.BigInteger(), nullable=False),
            sa.Column("item_type", sa.String(30), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("organization", sa.String(200)),
            sa.Column("description", sa.Text()),
            sa.Column("start_date", sa.Date()),
            sa.Column("end_date", sa.Date()),
            sa.Column("level", sa.String(100)),
            sa.Column("source_type", sa.String(30), nullable=False),
            sa.Column("source_ref_type", sa.String(80)),
            sa.Column("source_ref_id", sa.String(100)),
            sa.Column("verification_status", sa.String(30), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_student_profile_item_tenant_id", "t_internship_student_profile_item", ["tenant_id"])
        op.create_index("ix_intern_profile_item_type", "t_internship_student_profile_item", ["tenant_id", "profile_id", "item_type", "is_deleted"])
        op.create_index("ix_intern_profile_item_source", "t_internship_student_profile_item", ["tenant_id", "source_ref_type", "source_ref_id", "is_deleted"])

    if not insp.has_table("t_internship_application_material_snapshot"):
        op.create_table(
            "t_internship_application_material_snapshot",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("volunteer_group_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("campaign_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("submission_version", sa.Integer(), nullable=False),
            sa.Column("profile_version", sa.Integer(), nullable=False),
            sa.Column("profile_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("school_fact_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("attachment_file_ids_json", sa.JSON()),
            sa.Column("material_policy_snapshot_json", sa.JSON()),
            sa.Column("consent_version", sa.String(80), nullable=False),
            sa.Column("consent_at", sa.DateTime(), nullable=False),
            sa.Column("contact_sharing_policy", sa.JSON(), nullable=False),
            sa.Column("snapshot_hash", sa.String(64), nullable=False),
            sa.Column("generated_profile_pdf_file_id", sa.BigInteger()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.UniqueConstraint("tenant_id", "volunteer_group_id", "submission_version", name="uk_intern_material_snapshot_submission"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_application_material_snapshot_tenant_id", "t_internship_application_material_snapshot", ["tenant_id"])
        op.create_index("ix_intern_material_snapshot_group_version", "t_internship_application_material_snapshot", ["tenant_id", "volunteer_group_id", "submission_version"])
        op.create_index("ix_intern_material_snapshot_student_created", "t_internship_application_material_snapshot", ["tenant_id", "student_id", "created_at"])
        op.create_index("ix_intern_material_snapshot_campaign_student", "t_internship_application_material_snapshot", ["tenant_id", "campaign_id", "student_id"])
        op.create_index("ix_t_internship_application_material_snapshot_snapshot_hash", "t_internship_application_material_snapshot", ["snapshot_hash"])

    campaign_columns = _column_names(insp, "t_internship_recruitment_campaign")
    if "application_material_policy_json" not in campaign_columns:
        op.add_column("t_internship_recruitment_campaign", sa.Column("application_material_policy_json", sa.JSON(), nullable=True))

    application_columns = _column_names(insp, "t_internship_application")
    if "application_statement" not in application_columns:
        op.add_column("t_internship_application", sa.Column("application_statement", sa.Text(), nullable=True))
    if "material_snapshot_id" not in application_columns:
        op.add_column("t_internship_application", sa.Column("material_snapshot_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_t_internship_application_material_snapshot_id", "t_internship_application", ["material_snapshot_id"])

    op.execute("DROP TRIGGER IF EXISTS trg_intern_material_snapshot_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_intern_material_snapshot_no_delete")
    op.execute(
        """
        CREATE TRIGGER trg_intern_material_snapshot_no_update
        BEFORE UPDATE ON t_internship_application_material_snapshot
        FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'INTERNSHIP_MATERIAL_SNAPSHOT_IMMUTABLE'
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_intern_material_snapshot_no_delete
        BEFORE DELETE ON t_internship_application_material_snapshot
        FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'INTERNSHIP_MATERIAL_SNAPSHOT_IMMUTABLE'
        """
    )


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    op.execute("DROP TRIGGER IF EXISTS trg_intern_material_snapshot_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_intern_material_snapshot_no_delete")

    application_columns = _column_names(insp, "t_internship_application")
    if "material_snapshot_id" in application_columns:
        index_names = {idx["name"] for idx in insp.get_indexes("t_internship_application")}
        if "ix_t_internship_application_material_snapshot_id" in index_names:
            op.drop_index("ix_t_internship_application_material_snapshot_id", table_name="t_internship_application")
        op.drop_column("t_internship_application", "material_snapshot_id")
    if "application_statement" in application_columns:
        op.drop_column("t_internship_application", "application_statement")

    campaign_columns = _column_names(insp, "t_internship_recruitment_campaign")
    if "application_material_policy_json" in campaign_columns:
        op.drop_column("t_internship_recruitment_campaign", "application_material_policy_json")

    for table in (
        "t_internship_application_material_snapshot",
        "t_internship_student_profile_item",
        "t_internship_student_profile",
    ):
        if insp.has_table(table):
            op.drop_table(table)
