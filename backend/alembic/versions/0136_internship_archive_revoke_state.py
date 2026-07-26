"""internship archive revoke state and force evidence

Revision ID: 0136_intern_archive_state
Revises: 0135_gd_topic_advisor_mentor_id
"""
from alembic import op
import sqlalchemy as sa

revision = "0136_intern_archive_state"
down_revision = "0135_gd_topic_advisor_mentor_id"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("t_internship_archive", sa.Column("previous_record_status", sa.String(20)))
    op.add_column("t_internship_archive", sa.Column("package_invalidated_at", sa.DateTime()))
    op.add_column("t_internship_archive", sa.Column("revoked_by_name", sa.String(50)))
    op.add_column("t_internship_archive", sa.Column("revoked_at", sa.DateTime()))
    op.add_column("t_internship_archive", sa.Column("revoke_reason", sa.String(500)))
    op.add_column("t_internship_archive", sa.Column("force_reason", sa.String(500)))
    op.add_column("t_internship_archive", sa.Column("force_evidence_file_ids", sa.JSON()))


def downgrade():
    for name in (
        "force_evidence_file_ids", "force_reason", "revoke_reason", "revoked_at",
        "revoked_by_name", "package_invalidated_at", "previous_record_status",
    ):
        op.drop_column("t_internship_archive", name)
