"""E-A01 M1: recruitment campaign and enterprise identity authority tables.

Revision ID: 20260815_internship_e_m1
Revises: 20260814_merge_ix_v93_main

V3 deliberately groups the four E1 tables in one migration. This migration is additive and
keeps EmpCompany / InternshipPosition / InternshipApplication / InternshipRecord untouched.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_internship_e_m1"
down_revision = "20260814_merge_ix_v93_main"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_internship_e_m1 requires MySQL")


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_internship_recruitment_campaign"):
        op.create_table(
            "t_internship_recruitment_campaign",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("campaign_code", sa.String(100), nullable=False),
            sa.Column("campaign_name", sa.String(200), nullable=False),
            sa.Column("round_no", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("invite_start_at", sa.DateTime()),
            sa.Column("invite_end_at", sa.DateTime()),
            sa.Column("position_submit_start_at", sa.DateTime()),
            sa.Column("position_submit_end_at", sa.DateTime()),
            sa.Column("student_select_start_at", sa.DateTime()),
            sa.Column("student_select_end_at", sa.DateTime()),
            sa.Column("enterprise_decision_start_at", sa.DateTime()),
            sa.Column("enterprise_decision_end_at", sa.DateTime()),
            sa.Column("school_confirm_start_at", sa.DateTime()),
            sa.Column("school_confirm_end_at", sa.DateTime()),
            sa.Column("enterprise_access_end_at", sa.DateTime()),
            sa.Column("enterprise_confirm_required", sa.Boolean(), nullable=False),
            sa.Column("remark", sa.String(500)),
            *_common_columns(),
            sa.UniqueConstraint("tenant_id", "campaign_code", name="uk_intern_recruit_campaign_code"),
            sa.UniqueConstraint("tenant_id", "batch_id", "round_no", name="uk_intern_recruit_campaign_round"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_recruitment_campaign_tenant_id", "t_internship_recruitment_campaign", ["tenant_id"])
        op.create_index("ix_intern_recruit_campaign_batch_status", "t_internship_recruitment_campaign", ["tenant_id", "batch_id", "status", "is_deleted"])
        op.create_index("ix_intern_recruit_campaign_select_window", "t_internship_recruitment_campaign", ["tenant_id", "status", "student_select_start_at", "student_select_end_at"])

    if not insp.has_table("t_internship_campaign_enterprise"):
        op.create_table(
            "t_internship_campaign_enterprise",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("campaign_id", sa.BigInteger(), nullable=False),
            sa.Column("company_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("invite_source", sa.String(30), nullable=False),
            sa.Column("invited_by_user_id", sa.BigInteger()),
            sa.Column("invited_at", sa.DateTime()),
            sa.Column("accepted_at", sa.DateTime()),
            sa.Column("declined_at", sa.DateTime()),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("revoke_reason", sa.String(500)),
            *_common_columns(),
            sa.UniqueConstraint("tenant_id", "campaign_id", "company_id", name="uk_intern_campaign_enterprise"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_campaign_enterprise_tenant_id", "t_internship_campaign_enterprise", ["tenant_id"])
        op.create_index("ix_intern_campaign_enterprise_campaign_status", "t_internship_campaign_enterprise", ["tenant_id", "campaign_id", "status", "is_deleted"])
        op.create_index("ix_intern_campaign_enterprise_company_status", "t_internship_campaign_enterprise", ["tenant_id", "company_id", "status", "is_deleted"])

    if not insp.has_table("t_internship_enterprise_member"):
        op.create_table(
            "t_internship_enterprise_member",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("company_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("contact_id", sa.BigInteger()),
            sa.Column("member_role", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False),
            sa.Column("invited_phone_hash", sa.String(128)),
            sa.Column("invite_token_hash", sa.String(128)),
            sa.Column("invite_expires_at", sa.DateTime()),
            sa.Column("invited_at", sa.DateTime()),
            sa.Column("accepted_at", sa.DateTime()),
            sa.Column("last_active_at", sa.DateTime()),
            *_common_columns(),
            sa.UniqueConstraint("tenant_id", "company_id", "user_id", name="uk_intern_enterprise_member"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_enterprise_member_tenant_id", "t_internship_enterprise_member", ["tenant_id"])
        op.create_index("ix_intern_enterprise_member_user_status", "t_internship_enterprise_member", ["tenant_id", "user_id", "status", "is_deleted"])
        op.create_index("ix_intern_enterprise_member_company_status", "t_internship_enterprise_member", ["tenant_id", "company_id", "status", "is_deleted"])

    if not insp.has_table("t_internship_enterprise_access_grant"):
        op.create_table(
            "t_internship_enterprise_access_grant",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("member_id", sa.BigInteger(), nullable=False),
            sa.Column("company_id", sa.BigInteger(), nullable=False),
            sa.Column("grant_type", sa.String(30), nullable=False),
            sa.Column("campaign_id", sa.BigInteger()),
            sa.Column("batch_id", sa.BigInteger()),
            sa.Column("valid_from", sa.DateTime(), nullable=False),
            sa.Column("valid_until", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("revoked_by_user_id", sa.BigInteger()),
            sa.Column("revoke_reason", sa.String(500)),
            *_common_columns(),
            sa.UniqueConstraint("tenant_id", "member_id", "grant_type", "campaign_id", "batch_id", name="uk_intern_enterprise_access_grant"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_internship_enterprise_access_grant_tenant_id", "t_internship_enterprise_access_grant", ["tenant_id"])
        op.create_index("ix_intern_enterprise_grant_member_validity", "t_internship_enterprise_access_grant", ["tenant_id", "member_id", "status", "valid_until"])
        op.create_index("ix_intern_enterprise_grant_company_validity", "t_internship_enterprise_access_grant", ["tenant_id", "company_id", "status", "valid_until"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in (
        "t_internship_enterprise_access_grant",
        "t_internship_enterprise_member",
        "t_internship_campaign_enterprise",
        "t_internship_recruitment_campaign",
    ):
        if insp.has_table(table):
            op.drop_table(table)
