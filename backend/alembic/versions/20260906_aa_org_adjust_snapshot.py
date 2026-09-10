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
    for column, limit, nullable in [('from_class_ids', 500, False), ('check_result_json', 2000, True)]:
        op.alter_column(TABLE, column, existing_type=sa.String(limit), type_=mysql.LONGTEXT(), existing_nullable=nullable)


def downgrade():
    # MySQL DDL commits implicitly: validate BOTH columns before shrinking either.
    bind = op.get_bind()
    oversized = bind.execute(sa.text(
        f'SELECT COUNT(*) FROM {TABLE} WHERE CHAR_LENGTH(from_class_ids) > 500 OR CHAR_LENGTH(check_result_json) > 2000'
    )).scalar_one()
    if oversized:
        raise RuntimeError('Existing organization adjustment receipts exceed the old limits; downgrade would truncate history.')
    for column, limit, nullable in [('from_class_ids', 500, False), ('check_result_json', 2000, True)]:
        op.alter_column(TABLE, column, existing_type=mysql.LONGTEXT(), type_=sa.String(limit), existing_nullable=nullable)
