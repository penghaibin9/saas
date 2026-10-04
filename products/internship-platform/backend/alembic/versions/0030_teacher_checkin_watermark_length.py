"""Retain the complete teacher photo watermark for a permitted 500-character address.

The watermark also contains the teacher name, local time and coordinates. Widen
only its storage column; existing evidence, photo bytes and bindings are retained.
"""
from alembic import op
import sqlalchemy as sa

revision = 'ix0030'
down_revision = 'ix0029'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('t_internship_teacher_checkin', 'watermark_text',
                    type_=sa.String(1000), existing_type=sa.String(500),
                    existing_nullable=True)


def downgrade():
    raise RuntimeError('Narrowing stored photo evidence can truncate addresses; retain data and roll forward')
