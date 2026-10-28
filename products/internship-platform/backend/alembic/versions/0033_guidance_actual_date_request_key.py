"""Actual guidance date and scoped retry key; historical facts stay unknown."""
from alembic import op
import sqlalchemy as sa

revision = 'ix0033'
down_revision = 'ix0032'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('t_internship_guidance', sa.Column('guidance_date', sa.Date(), nullable=True))
    op.add_column('t_internship_guidance', sa.Column('request_key', sa.String(64), nullable=True))
    op.create_unique_constraint('uk_intern_guidance_request', 't_internship_guidance',
                               ['tenant_id', 'internship_id', 'request_key'])


def downgrade():
    op.drop_constraint('uk_intern_guidance_request', 't_internship_guidance', type_='unique')
    op.drop_column('t_internship_guidance', 'request_key')
    op.drop_column('t_internship_guidance', 'guidance_date')
