"""Freeze correction-request material evidence without guessing legacy bindings."""
from alembic import op
import sqlalchemy as sa

revision = "20260909_aa_change_materials"
down_revision = "20260909_aa_retake_origin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("t_aa_grade_change_request", sa.Column("evidence_manifest_json", sa.String(4000), nullable=True))
    op.add_column("t_aa_grade_change_request", sa.Column("evidence_manifest_hash", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("t_aa_grade_change_request", "evidence_manifest_hash")
    op.drop_column("t_aa_grade_change_request", "evidence_manifest_json")
