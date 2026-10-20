"""Separate recovery risk from login eligibility; preserve original account access."""
from alembic import op
import sqlalchemy as sa

revision = '20260910_phone_recovery_freeze'
down_revision = '20260910_phone_sms_purpose'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('t_user_phone_login_binding', sa.Column('recovery_frozen', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM t_user_phone_login_binding WHERE recovery_frozen = 1)')).scalar():
        raise RuntimeError('Recovery restrictions exist; retain them and use a forward migration.')
    op.drop_column('t_user_phone_login_binding', 'recovery_frozen')
