"""Freeze dynamic correction evidence in the canonical request."""
from alembic import op
import sqlalchemy as sa

revision = "20260909_aa_change_components"
down_revision = "20260909_aa_change_materials"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("t_aa_grade_change_request", sa.Column("score_snapshot_json", sa.Text(), nullable=True))
    op.add_column("t_aa_grade_change_request", sa.Column("score_snapshot_hash", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("t_aa_grade_change_request", "score_snapshot_hash")
    op.drop_column("t_aa_grade_change_request", "score_snapshot_json")
