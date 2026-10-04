"""Add nullable independent student origin and nationality; retain all historical facts.

Existing rows remain uncollected. No orientation imports, inference or data backfill.
Older code can keep reading the existing columns. Roll forward to repair; downgrade
is allowed only while both new columns are empty, to protect collected facts.
"""
from alembic import op
import sqlalchemy as sa

revision = 'ix0028'
down_revision = 'ix0027'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('t_student_profile', sa.Column('nation', sa.String(50), nullable=True,
                  comment='学生本人或学校维护的民族；未采集保持空值'))
    op.add_column('t_student_profile', sa.Column('source_region', sa.String(100), nullable=True,
                  comment='生源地（地区名称，不采集详细家庭地址）'))


def downgrade():
    populated = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM t_student_profile WHERE nation IS NOT NULL OR source_region IS NOT NULL'
    )).scalar()
    if populated:
        raise RuntimeError('Collected student basic information must be retained; roll forward instead')
    op.drop_column('t_student_profile', 'source_region')
    op.drop_column('t_student_profile', 'nation')
