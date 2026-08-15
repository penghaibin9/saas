"""E-A01 M4: volunteer-group coordination fact and teacher confirmation SLA.

Revision ID: 20260815_internship_e_m4
Revises: 20260815_internship_e_m3

This migration does not create a second volunteer/application table. Position choices remain
canonical internship application rows with volunteer_no 1/2/3.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_internship_e_m4"
down_revision = "20260815_internship_e_m3"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_internship_e_m4 requires MySQL")


def _column_names(insp, table: str) -> set[str]:
    return {column["name"] for column in insp.get_columns(table)} if insp.has_table(table) else set()


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)

    if not insp.has_table("t_internship_volunteer_group"):
        op.create_table(
            "t_internship_volunteer_group",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("record_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("campaign_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("submission_version", sa.Integer(), nullable=False),
            sa.Column("current_material_snapshot_id", sa.BigInteger()),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("locked_application_id", sa.BigInteger()),
            sa.Column("locked_at", sa.DateTime()),
            sa.Column("locked_by_decision_id", sa.BigInteger()),
            sa.Column("teacher_confirm_deadline", sa.DateTime()),
            sa.Column("approved_at", sa.DateTime()),
            sa.Column("revision_requested_at", sa.DateTime()),
            sa.Column("revision_reason", sa.String(500)),
            sa.Column("last_released_at", sa.DateTime()),
            sa.Column("last_release_reason", sa.String(500)),
            sa.Column("released_by_user_id", sa.BigInteger()),
            sa.Column("contact_consent_revoked_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.UniqueConstraint(
                "tenant_id", "record_id", "campaign_id",
                name="uk_intern_volunteer_group_record_campaign",
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_volunteer_group_tenant_id", "t_internship_volunteer_group", ["tenant_id"])
        op.create_index(
            "ix_intern_volunteer_group_student_status",
            "t_internship_volunteer_group",
            ["tenant_id", "student_id", "campaign_id", "status", "is_deleted"],
        )
        op.create_index(
            "ix_intern_volunteer_group_campaign_deadline",
            "t_internship_volunteer_group",
            ["tenant_id", "campaign_id", "status", "teacher_confirm_deadline", "is_deleted"],
        )
        op.create_index(
            "ix_intern_volunteer_group_record_status",
            "t_internship_volunteer_group",
            ["tenant_id", "record_id", "status", "is_deleted"],
        )

    campaign_columns = _column_names(insp, "t_internship_recruitment_campaign")
    if "teacher_confirm_sla_hours" not in campaign_columns:
        op.add_column(
            "t_internship_recruitment_campaign",
            sa.Column("teacher_confirm_sla_hours", sa.Integer(), nullable=False, server_default="48"),
        )
    else:
        op.execute(
            "UPDATE t_internship_recruitment_campaign "
            "SET teacher_confirm_sla_hours=48 WHERE teacher_confirm_sla_hours IS NULL"
        )
        op.alter_column(
            "t_internship_recruitment_campaign", "teacher_confirm_sla_hours",
            existing_type=sa.Integer(), nullable=False, server_default="48",
        )


def downgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())
    campaign_columns = _column_names(insp, "t_internship_recruitment_campaign")
    if "teacher_confirm_sla_hours" in campaign_columns:
        op.drop_column("t_internship_recruitment_campaign", "teacher_confirm_sla_hours")
    if insp.has_table("t_internship_volunteer_group"):
        op.drop_table("t_internship_volunteer_group")
