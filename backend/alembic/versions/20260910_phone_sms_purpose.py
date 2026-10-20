"""Extend the existing SMS queue; old consumers remain reset-only."""
from alembic import op
import sqlalchemy as sa

revision = '20260910_phone_sms_purpose'
down_revision = '20260910_phone_login_foundation'
branch_labels = None
depends_on = None


def upgrade():
    names = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('t_password_reset_sms_job')}
    if 'purpose' not in names:
        op.add_column('t_password_reset_sms_job', sa.Column('purpose', sa.String(30), nullable=False, server_default='RESET_PASSWORD'))
        op.create_index('ix_t_password_reset_sms_job_purpose', 't_password_reset_sms_job', ['purpose'])
    if 'challenge_ref' not in names:
        op.add_column('t_password_reset_sms_job', sa.Column('challenge_ref', sa.String(100)))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM t_password_reset_sms_job WHERE purpose <> 'RESET_PASSWORD')")).scalar():
        raise RuntimeError('New-purpose SMS history exists; retain its discriminator and use a forward migration.')
    op.drop_column('t_password_reset_sms_job', 'challenge_ref')
    op.drop_index('ix_t_password_reset_sms_job_purpose', table_name='t_password_reset_sms_job')
    op.drop_column('t_password_reset_sms_job', 'purpose')
