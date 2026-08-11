"""Widen graduation-audit evidence projection to TEXT.

The immutable graduation evaluation run already stores ``item_results_json`` as
TEXT, while the legacy compatibility projection kept the original VARCHAR(4000)
from migration 0014.  The current graduation precheck writes the same complete
11-dimension evidence payload to both stores, so a valid payload can exceed the
legacy MySQL limit and fail the whole transaction with DataError.

Revision ID: 20260810_grad_audit_text
Revises: 20260810_schema_reconcile
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_grad_audit_text"
down_revision = "20260810_schema_reconcile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "t_aa_graduation_audit_result",
        "item_results_json",
        existing_type=sa.String(length=4000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Deliberately use a normal narrowing ALTER rather than truncating data in
    # application code. MySQL will fail the downgrade if existing evidence no
    # longer fits VARCHAR(4000), preventing silent loss of audit evidence.
    op.alter_column(
        "t_aa_graduation_audit_result",
        "item_results_json",
        existing_type=sa.Text(),
        type_=sa.String(length=4000),
        existing_nullable=True,
    )
