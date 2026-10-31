"""Anonymous request rate counters; never store visitor form contents."""
from alembic import op
import sqlalchemy as sa
revision = '0003_public_rate'
down_revision = '0002_website_accounts'
branch_labels = depends_on = None
def upgrade():
    op.create_table('website_public_rate',sa.Column('key',sa.String(64),primary_key=True),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('reset_at',sa.DateTime(),nullable=False),mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.create_index('ix_website_public_rate_reset_at','website_public_rate',['reset_at'])
def downgrade():
    raise RuntimeError('保留防滥用计数，不自动执行数据库回退')
