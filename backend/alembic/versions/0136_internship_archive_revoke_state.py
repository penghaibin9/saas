"""internship archive revoke state and force evidence

Revision ID: 0136_intern_archive_state
Revises: 0135_gd_topic_advisor_mentor_id

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时这些列可能已提前
创建，故先探测再加列（同 0103/0104/0105 约定）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0136_intern_archive_state"
down_revision = "0135_gd_topic_advisor_mentor_id"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def upgrade():
    existing = _column_names("t_internship_archive")
    for name, col in (
        ("previous_record_status", sa.String(20)),
        ("package_invalidated_at", sa.DateTime()),
        ("revoked_by_name", sa.String(50)),
        ("revoked_at", sa.DateTime()),
        ("revoke_reason", sa.String(500)),
        ("force_reason", sa.String(500)),
        ("force_evidence_file_ids", sa.JSON()),
    ):
        if name not in existing:
            op.add_column("t_internship_archive", sa.Column(name, col))


def downgrade():
    for name in (
        "force_evidence_file_ids", "force_reason", "revoke_reason", "revoked_at",
        "revoked_by_name", "package_invalidated_at", "previous_record_status",
    ):
        op.drop_column("t_internship_archive", name)
