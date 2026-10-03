"""Yiyang AP04 student multi-plan assignment.

Revision ID: ix0021
Revises: ix0020
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0021"
down_revision = "ix0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_plan_assignment",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("internship_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("plan_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("plan_batch_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("assignment_source", sa.String(30), nullable=False, server_default="MANUAL"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("assigned_by_name", sa.String(100), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("remove_reason", sa.String(500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "internship_id", "plan_id",
            name="uk_ix_plan_assignment_internship_plan",
        ),
    )
    op.create_index(
        "ix_ix_plan_assignment_active",
        "t_internship_plan_assignment",
        ["tenant_id", "internship_id", "status", "is_deleted"],
    )

    # Existing published plans already have ACK/task facts from the legacy one-plan flow.
    # Backfill only the new relationship fact so upgraded schools do not appear unassigned.
    op.execute(sa.text("""
        INSERT INTO t_internship_plan_assignment (
            tenant_id, internship_id, student_id, plan_id, plan_batch_id,
            assignment_source, is_primary, status, assigned_by_name, assigned_at,
            version, is_deleted, created_at, updated_at
        )
        SELECT
            p.tenant_id, r.id, r.student_id, p.id, p.batch_id,
            'PRIMARY_AUTO', 1, 'ACTIVE',
            COALESCE(p.published_by_name, '系统'),
            COALESCE(p.published_at, CURRENT_TIMESTAMP),
            0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM t_internship_batch_plan p
        JOIN t_internship_record r
          ON r.tenant_id = p.tenant_id
         AND r.batch_id = p.batch_id
         AND r.is_deleted = 0
        WHERE p.status = 'PUBLISHED'
          AND p.is_deleted = 0
    """))


def downgrade() -> None:
    op.drop_index("ix_ix_plan_assignment_active", table_name="t_internship_plan_assignment")
    op.drop_table("t_internship_plan_assignment")
