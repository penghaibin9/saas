"""Frozen website account tables, unrelated to school users."""
from alembic import op
import sqlalchemy as sa
revision = '0002_website_accounts'
down_revision = '0001_website_news'
branch_labels = depends_on = None

def upgrade():
    op.create_table('website_user', sa.Column('id',sa.String(32),primary_key=True),sa.Column('username',sa.String(80),nullable=False,unique=True),sa.Column('display_name',sa.String(100),nullable=False),sa.Column('password_hash',sa.String(256),nullable=False),sa.Column('role',sa.String(20),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.create_table('website_session',sa.Column('digest',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(32),sa.ForeignKey('website_user.id'),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False),mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.create_index('ix_website_session_user_id','website_session',['user_id'])
    op.create_index('ix_website_session_expires_at','website_session',['expires_at'])
    op.create_table('website_login_attempt',sa.Column('key',sa.String(64),primary_key=True),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('reset_at',sa.DateTime(),nullable=False),mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.create_index('ix_website_login_attempt_reset_at','website_login_attempt',['reset_at'])
    op.create_table('website_auth_audit',sa.Column('id',sa.String(32),primary_key=True),sa.Column('user_id',sa.String(32)),sa.Column('action',sa.String(32),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),mysql_engine='InnoDB',mysql_charset='utf8mb4')

def downgrade():
    raise RuntimeError('保留官网账号和审计记录，不执行破坏性回退；可回退应用版本')
