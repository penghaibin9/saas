"""Stage C1 closeout: preserve temporal boundary microseconds on MySQL.

Revision ID: 20260809_aa_fact_time_precision_c1
Revises: 20260809_aa_stage_c3

A second-only DATETIME collapses a read immediately before a fact switch and the
switch itself into the same value.  That makes as-of replay and scheduled effective
changes nondeterministic.  MySQL production columns therefore use DATETIME(6).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20260809_aa_fact_time_precision_c1"
down_revision = "20260809_aa_stage_c3"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return any(row["name"] == column for row in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    if _column_exists(bind, "t_aa_student_academic_fact", "valid_from"):
        op.alter_column(
            "t_aa_student_academic_fact",
            "valid_from",
            existing_type=sa.DateTime(),
            type_=mysql.DATETIME(fsp=6),
            existing_nullable=False,
        )
    if _column_exists(bind, "t_aa_student_academic_fact", "valid_to"):
        op.alter_column(
            "t_aa_student_academic_fact",
            "valid_to",
            existing_type=sa.DateTime(),
            type_=mysql.DATETIME(fsp=6),
            existing_nullable=True,
        )
    if _column_exists(bind, "t_aa_status_change", "effective_date"):
        op.alter_column(
            "t_aa_status_change",
            "effective_date",
            existing_type=sa.DateTime(),
            type_=mysql.DATETIME(fsp=6),
            existing_nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    if _column_exists(bind, "t_aa_status_change", "effective_date"):
        op.alter_column(
            "t_aa_status_change",
            "effective_date",
            existing_type=mysql.DATETIME(fsp=6),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
    if _column_exists(bind, "t_aa_student_academic_fact", "valid_to"):
        op.alter_column(
            "t_aa_student_academic_fact",
            "valid_to",
            existing_type=mysql.DATETIME(fsp=6),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
    if _column_exists(bind, "t_aa_student_academic_fact", "valid_from"):
        op.alter_column(
            "t_aa_student_academic_fact",
            "valid_from",
            existing_type=mysql.DATETIME(fsp=6),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
