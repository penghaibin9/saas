"""PLAT-10：问题管理、已知错误与事故复盘。

Revision ID: 0171_problem_management
Revises: 0170_customer_success
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0171_problem_management"
down_revision = "0170_customer_success"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0171_problem_management requires MySQL")


def _common() -> list:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_problem"):
        op.create_table(
            "t_problem",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
            sa.Column("root_cause", sa.String(2000)),
            sa.Column("workaround", sa.String(2000)),
            sa.Column("source_incident_id", sa.BigInteger()),
            sa.Column("permanent_fix_change_id", sa.BigInteger()),
            sa.Column("known_error_published", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("closed_at", sa.DateTime()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_problem_status", "t_problem", ["status"])
        op.create_index("ix_t_problem_source_incident", "t_problem", ["source_incident_id"])

    if not insp.has_table("t_problem_postmortem"):
        op.create_table(
            "t_problem_postmortem",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("problem_id", sa.BigInteger(), nullable=False),
            sa.Column("what_happened", sa.String(4000)),
            sa.Column("timeline_json", sa.JSON(), nullable=False),
            sa.Column("impact_summary", sa.String(2000)),
            sa.Column("action_items_json", sa.JSON(), nullable=False),
            sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("author_user_id", sa.BigInteger()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_problem_postmortem_problem", "t_problem_postmortem", ["problem_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_problem_postmortem", "t_problem"):
        if insp.has_table(table):
            op.drop_table(table)
