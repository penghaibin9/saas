"""R11 真实学校完整学期试点证据表。

仅新增试点控制与检查证据，不生成任何学校业务数据，也不回填“已完成”。

Revision ID: 0131_aa_real_semester_pilot
Revises: 0130_aa_dynamic_grade_stats_snapshot
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0131_aa_real_semester_pilot"
down_revision = "0130_aa_dynamic_grade_stats_snapshot"
branch_labels = None
depends_on = None


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _common():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)
    if "t_aa_semester_pilot" not in tables:
        op.create_table(
            "t_aa_semester_pilot", *_common(),
            sa.Column("term_id", sa.BigInteger(), nullable=False),
            sa.Column("term_code", sa.String(length=40), nullable=False),
            sa.Column("pilot_name", sa.String(length=160), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PREPARING"),
            sa.Column("purpose", sa.String(length=500), nullable=False),
            sa.Column("real_data_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("check_run_no", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("passed_stage_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("blocker_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("latest_evidence_hash", sa.String(length=64), nullable=True),
            sa.Column("latest_checked_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("completed_by", sa.String(length=100), nullable=True),
            sa.Column("completion_note", sa.String(length=500), nullable=True),
            sa.UniqueConstraint("tenant_id", "term_id", name="uk_aa_semester_pilot_term"),
        )
        op.create_index("ix_aa_semester_pilot_term", "t_aa_semester_pilot", ["term_id"])
        op.create_index("ix_aa_semester_pilot_status", "t_aa_semester_pilot", ["tenant_id", "status"])
        op.create_index("ix_aa_semester_pilot_hash", "t_aa_semester_pilot", ["tenant_id", "latest_evidence_hash"])

    if "t_aa_semester_pilot_checkpoint" not in tables:
        op.create_table(
            "t_aa_semester_pilot_checkpoint", *_common(),
            sa.Column("pilot_id", sa.BigInteger(), nullable=False),
            sa.Column("run_no", sa.Integer(), nullable=False),
            sa.Column("stage_code", sa.String(length=32), nullable=False),
            sa.Column("stage_name", sa.String(length=80), nullable=False),
            sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("blocker_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("warning_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("conclusion", sa.String(length=500), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("evidence_hash", sa.String(length=64), nullable=False),
            sa.Column("checked_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("checked_by", sa.String(length=100), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "pilot_id", "run_no", "stage_code",
                name="uk_aa_semester_pilot_checkpoint",
            ),
        )
        op.create_index("ix_aa_semester_checkpoint_pilot", "t_aa_semester_pilot_checkpoint", ["tenant_id", "pilot_id", "run_no"])
        op.create_index("ix_aa_semester_checkpoint_stage", "t_aa_semester_pilot_checkpoint", ["tenant_id", "stage_code", "passed"])
        op.create_index("ix_aa_semester_checkpoint_hash", "t_aa_semester_pilot_checkpoint", ["tenant_id", "evidence_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)
    if "t_aa_semester_pilot_checkpoint" in tables:
        op.drop_table("t_aa_semester_pilot_checkpoint")
    if "t_aa_semester_pilot" in tables:
        op.drop_table("t_aa_semester_pilot")
