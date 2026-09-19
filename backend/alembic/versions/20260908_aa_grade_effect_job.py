"""Durable post-publication warning effects, without duplicating formal grades."""
from alembic import op
import sqlalchemy as sa

revision = '20260908_aa_grade_effect_job'
down_revision = '20260907_aa_classroom_buildings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('t_aa_grade_effect_job',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('grade_task_id', sa.BigInteger(), nullable=False),
        sa.Column('source_kind', sa.String(24), nullable=False),
        sa.Column('source_id', sa.BigInteger(), nullable=False),
        sa.Column('state', sa.String(16), nullable=False, server_default='PENDING'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_run_at', sa.DateTime(), nullable=False),
        sa.Column('lease_token', sa.String(36)),
        sa.Column('lease_until', sa.DateTime()),
        sa.Column('last_error', sa.String(200)),
        sa.Column('result_json', sa.JSON()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.BigInteger()), sa.Column('updated_by', sa.BigInteger()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('tenant_id', 'source_kind', 'source_id', name='uk_aa_grade_effect_source'))
    op.create_index('ix_t_aa_grade_effect_job_tenant_id', 't_aa_grade_effect_job', ['tenant_id'])
    op.create_index('ix_aa_grade_effect_due', 't_aa_grade_effect_job', ['tenant_id', 'state', 'next_run_at'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM t_aa_grade_effect_job')).scalar_one():
        raise RuntimeError('Grade effect evidence exists; refusing destructive downgrade.')
    op.drop_table('t_aa_grade_effect_job')
