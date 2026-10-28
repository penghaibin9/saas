"""Add the title and opt-in encrypted location without inventing historical facts."""
from alembic import op
import sqlalchemy as sa

revision = 'ix0032'
down_revision = 'ix0031'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('t_internship_visit', sa.Column('visit_title', sa.String(200), nullable=True))
    op.add_column('t_internship_visit', sa.Column('location_encrypted', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('t_internship_visit', 'location_encrypted')
    op.drop_column('t_internship_visit', 'visit_title')
