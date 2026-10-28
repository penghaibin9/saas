"""Retain the application that actually established the current placement.

Old autonomous rows remain unattributed; do not infer an owner from matching
names or rewrite historical approvals. Existing placement snapshots retain
their independent, immutable application link.
"""
from alembic import op
import sqlalchemy as sa

revision = 'ix0031'
down_revision = 'ix0030'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('t_internship_record', sa.Column('current_application_id', sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column('t_internship_record', 'current_application_id')
