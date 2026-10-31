"""Independent encrypted consultation storage with owner-approved retention."""
from alembic import op
import sqlalchemy as sa
revision = '0006_website_consultation'
down_revision = '0005_revision_required_metadata'
branch_labels = depends_on = None

def upgrade():
    op.create_table('website_consultation',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('request_id', sa.String(32), nullable=False, unique=True),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('private_data', sa.Text(), nullable=False),
        sa.Column('phone_mask', sa.String(20), nullable=False),
        sa.Column('source_path', sa.String(180), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False))
    op.create_index('ix_website_consultation_expires_at', 'website_consultation', ['expires_at'])
    op.create_table('website_consultation_audit',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('consultation_id', sa.String(32), sa.ForeignKey('website_consultation.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id', sa.String(32)),
        sa.Column('action', sa.String(24), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_website_consultation_audit_consultation_id', 'website_consultation_audit', ['consultation_id'])

def downgrade():
    raise RuntimeError('咨询资料需要先保护和核对，不自动删除保存的数据')
