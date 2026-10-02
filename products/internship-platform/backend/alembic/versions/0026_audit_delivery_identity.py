"""Add durable delivery identity and bounded queue indexes; keep prior migration immutable."""
from alembic import op
import sqlalchemy as sa

revision = 'ix0026'
down_revision = 'ix0025'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'source_event_id' not in {c['name'] for c in inspector.get_columns('t_security_audit_log')}:
        op.add_column('t_security_audit_log', sa.Column('source_event_id', sa.String(64), nullable=True))
    names = {i['name'] for i in sa.inspect(bind).get_indexes('t_security_audit_log')}
    if 'uk_security_audit_source_event' not in names:
        op.create_index('uk_security_audit_source_event', 't_security_audit_log',
                        ['tenant_id', 'source_event_id'], unique=True)
    names = {i['name'] for i in sa.inspect(bind).get_indexes('t_audit_outbox')}
    for name, columns in (
        ('ix_audit_outbox_delivery_due', ['status', 'next_retry_at', 'id']),
        ('ix_audit_outbox_tenant_status_created', ['tenant_id', 'status', 'created_at']),
    ):
        if name not in names:
            op.create_index(name, 't_audit_outbox', columns)


def downgrade():
    count = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM t_security_audit_log WHERE source_event_id IS NOT NULL')).scalar()
    if count:
        raise RuntimeError('Retained audit delivery identities prevent destructive downgrade')
    op.drop_index('ix_audit_outbox_tenant_status_created', table_name='t_audit_outbox')
    op.drop_index('ix_audit_outbox_delivery_due', table_name='t_audit_outbox')
    op.drop_index('uk_security_audit_source_event', table_name='t_security_audit_log')
    op.drop_column('t_security_audit_log', 'source_event_id')
