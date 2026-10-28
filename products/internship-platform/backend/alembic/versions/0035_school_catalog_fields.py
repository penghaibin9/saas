"""Separate national major codes and school notice labels from stable business identifiers."""
from alembic import op
import sqlalchemy as sa

revision='ix0035'
down_revision='ix0034'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('t_major',sa.Column('national_code',sa.String(20),nullable=True))
    op.add_column('t_internship_emergency_notice',sa.Column('school_category',sa.String(50),nullable=True))


def downgrade():
    raise RuntimeError('保留已维护的专业代码和历史公告分类；回退程序时保留增量字段')
