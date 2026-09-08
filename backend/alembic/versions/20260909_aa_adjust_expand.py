"""Add large adjustment evidence without changing N-1 columns.

Legacy source JSON remains complete whenever it fits VARCHAR(500). Larger requests
use a V2_ state unknown to N-1 writers: old precheck/execute/cancel state guards
reject them rather than acting on an incomplete source scope. Full receipts have
an additive payload plus a hash of the legacy projection; an N-1 write invalidates
that payload instead of allowing a stale successful precheck to be replayed.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '20260909_aa_adjust_expand'
down_revision = '20260907_aa_classroom_buildings'
branch_labels = None
depends_on = None
TABLE = 't_aa_class_adjustment_request'


def upgrade():
    op.add_column(TABLE, sa.Column('from_class_ids_expanded', mysql.LONGTEXT(), nullable=True))
    op.add_column(TABLE, sa.Column('check_result_expanded', mysql.LONGTEXT(), nullable=True))


def downgrade():
    bind = op.get_bind()
    count = bind.execute(sa.text(
        'SELECT COUNT(*) FROM t_aa_class_adjustment_request '
        'WHERE from_class_ids_expanded IS NOT NULL OR check_result_expanded IS NOT NULL'
    )).scalar_one()
    if count:
        raise RuntimeError('Expanded adjustment evidence exists; application rollback must retain the additive columns.')
    op.drop_column(TABLE, 'check_result_expanded')
    op.drop_column(TABLE, 'from_class_ids_expanded')
