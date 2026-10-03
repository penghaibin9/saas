"""Restore the standalone security audit destination; retain evidence on rollback."""
from alembic import op
import sqlalchemy as sa
revision = 'ix0025'
down_revision = 'ix0024'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('t_security_audit_log'):
        return
    op.create_table('t_security_audit_log',
        sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),
        sa.Column('tenant_id',sa.BigInteger(),nullable=False),
        sa.Column('operator_id',sa.BigInteger()),sa.Column('operator_name',sa.String(100)),
        sa.Column('current_role',sa.String(100)),sa.Column('data_scope',sa.String(100)),
        sa.Column('action',sa.String(100),nullable=False),sa.Column('resource',sa.String(200)),
        sa.Column('resource_id',sa.String(100)),sa.Column('ip',sa.String(64)),
        sa.Column('user_agent',sa.String(500)),sa.Column('trace_id',sa.String(100)),
        sa.Column('request_method',sa.String(10)),sa.Column('request_path',sa.String(500)),
        sa.Column('result',sa.String(50)),sa.Column('detail_json',sa.JSON()),
        sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('created_by',sa.BigInteger()))
    op.create_index('ix_audit_tenant_created_id','t_security_audit_log',['tenant_id','created_at','id'])
    op.create_index('ix_audit_tenant_operator_created','t_security_audit_log',['tenant_id','operator_id','created_at'])
    for name in ('tenant_id','operator_id','trace_id','created_at'):
        op.create_index('ix_t_security_audit_log_'+name,'t_security_audit_log',[name])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM t_security_audit_log')).scalar():
        raise RuntimeError('Retained security audit records prevent destructive downgrade')
    op.drop_table('t_security_audit_log')
