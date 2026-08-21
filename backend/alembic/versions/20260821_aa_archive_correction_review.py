"""W1: persist post-archive correction rejection review metadata.

Revision ID: 20260821_aa_archive_review
Revises: 20260820_teacher_emp_reco

The migration is intentionally a single descendant of the latest main Alembic head
observed immediately before creation.  It only extends the existing Stage C3 correction
case; ARCHIVED/Manifest/fact tables and their history are untouched.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260821_aa_archive_review"
down_revision = "20260820_teacher_emp_reco"
branch_labels = None
depends_on = None

_TABLE = "t_aa_post_archive_correction_case"


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(_TABLE)}


def upgrade() -> None:
    existing = _columns()
    if "rejected_by" not in existing:
        op.add_column(_TABLE, sa.Column("rejected_by", sa.BigInteger(), nullable=True))
    if "rejected_at" not in existing:
        op.add_column(_TABLE, sa.Column("rejected_at", sa.DateTime(), nullable=True))
    if "reject_reason" not in existing:
        op.add_column(_TABLE, sa.Column("reject_reason", sa.String(length=500), nullable=True))


def downgrade() -> None:
    existing = _columns()
    if "reject_reason" in existing:
        op.drop_column(_TABLE, "reject_reason")
    if "rejected_at" in existing:
        op.drop_column(_TABLE, "rejected_at")
    if "rejected_by" in existing:
        op.drop_column(_TABLE, "rejected_by")
