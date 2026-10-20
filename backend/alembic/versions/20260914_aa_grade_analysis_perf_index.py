"""Cover school-wide grade-analysis identity probes without changing grade facts.

The analysis guard reads active grade identity and policy fields before deciding
whether SQL aggregation is safe.  Its former per-expression scan grows with the
entire school corpus; this covering index keeps the read path in the index while
the existing resolver remains authoritative for exceptional identities.

Revision ID: 20260914_aa_grade_analysis_perf
Revises: 20260910_phone_recovery_freeze
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


revision = "20260914_aa_grade_analysis_perf"
down_revision = "20260910_phone_recovery_freeze"
branch_labels = None
depends_on = None

_TABLE = "t_acad_grade"
_INDEX = "ix_acad_grade_analysis_identity"
_COLUMNS = [
    "tenant_id",
    "record_status",
    "is_deleted",
    "acad_student_id",
    "course_code",
    "course_id",
    "pass_status",
    "effective_attempt_strategy",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table(_TABLE) and _INDEX not in {
        row["name"] for row in inspector.get_indexes(_TABLE)
    }:
        op.create_index(_INDEX, _TABLE, _COLUMNS)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table(_TABLE) and _INDEX in {
        row["name"] for row in inspector.get_indexes(_TABLE)
    }:
        op.drop_index(_INDEX, table_name=_TABLE)
