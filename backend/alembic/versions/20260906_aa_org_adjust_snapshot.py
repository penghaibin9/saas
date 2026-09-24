"""Preserve complete organization adjustment scope and precheck receipts.

Revision ID: 20260906_aa_org_adjust_snapshot
Revises: 20260901_orientation_self_activate_o6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '20260906_aa_org_adjust_snapshot'
down_revision = '20260901_orientation_self_activate_o6'
branch_labels = None
depends_on = None
TABLE = 't_aa_class_adjustment_request'


def upgrade():
    # Expand-only release: preserve the N-1 columns unchanged so previous application
    # bytes remain rollback-compatible.  The new LONGTEXT shadows are nullable,
    # backfilled from the legacy values, and can be adopted by a later release only
    # after the old writers have been retired.
    op.add_column(TABLE, sa.Column('from_class_ids_text', mysql.LONGTEXT(), nullable=True))
    op.add_column(TABLE, sa.Column('check_result_text', mysql.LONGTEXT(), nullable=True))
    op.execute(sa.text(
        f'UPDATE {TABLE} SET from_class_ids_text = from_class_ids, '
        'check_result_text = check_result_json '
        'WHERE from_class_ids_text IS NULL OR check_result_text IS NULL'
    ))


def downgrade():
    op.drop_column(TABLE, 'check_result_text')
    op.drop_column(TABLE, 'from_class_ids_text')
