"""internship real actor closure and evidence provenance

Revision ID: 0137_intern_role_closure
Revises: 0136_intern_archive_state
"""
from alembic import op
import sqlalchemy as sa

revision = "0137_intern_role_closure"
down_revision = "0136_intern_archive_state"
branch_labels = None
depends_on = None


def upgrade():
    for name, col in (
        ("content_hash", sa.String(64)), ("client_ip_digest", sa.String(128)),
        ("confirmed_by_user_id", sa.String(64)), ("confirmed_student_id", sa.BigInteger()),
        ("guardian_token_hash", sa.String(64)), ("guardian_token_expires_at", sa.DateTime()),
        ("guardian_token_used_at", sa.DateTime()), ("guardian_token_revoked_at", sa.DateTime()),
    ):
        op.add_column("t_internship_consent", sa.Column(name, col, nullable=True))
    for name, col in (
        ("course_content_snapshot", sa.Text()), ("course_content_hash", sa.String(64)),
        ("submitted_at", sa.DateTime()), ("answer_snapshot", sa.JSON()),
        ("commitment_content_hash", sa.String(64)), ("commitment_device_digest", sa.String(128)),
        ("reviewed_by_user_id", sa.String(64)),
    ):
        op.add_column("t_internship_safety_completion", sa.Column(name, col, nullable=True))
    for name, col in (
        ("requested_by_name", sa.String(100)), ("requested_by_user_id", sa.String(64)),
        ("reviewed_by_name", sa.String(100)), ("reviewed_at", sa.DateTime()),
    ):
        op.add_column("t_internship_compliance_exemption", sa.Column(name, col, nullable=True))
    provenance = (
        ("source_type", sa.String(30)), ("recorded_by_user_id", sa.String(64)),
        ("recorded_by_name", sa.String(100)), ("recorded_at", sa.DateTime()),
        ("source_file_id", sa.String(64)), ("enterprise_contact_id", sa.BigInteger()),
        ("source_remark", sa.String(500)),
    )
    for table in ("t_internship_agreement", "t_internship_enterprise_eval"):
        for name, col in provenance:
            op.add_column(table, sa.Column(name, col, nullable=True))
    for name, col in (
        ("force_bypassed_items", sa.JSON()), ("force_rule_version", sa.String(64)),
        ("force_approved_role", sa.String(50)), ("force_approved_by", sa.String(100)),
    ):
        op.add_column("t_internship_archive", sa.Column(name, col, nullable=True))


def downgrade():
    for name in ("force_approved_by", "force_approved_role", "force_rule_version", "force_bypassed_items"):
        op.drop_column("t_internship_archive", name)
    provenance_names = (
        "source_remark", "enterprise_contact_id", "source_file_id", "recorded_at",
        "recorded_by_name", "recorded_by_user_id", "source_type",
    )
    for table in ("t_internship_enterprise_eval", "t_internship_agreement"):
        for name in provenance_names:
            op.drop_column(table, name)
    for name in ("reviewed_at", "reviewed_by_name", "requested_by_user_id", "requested_by_name"):
        op.drop_column("t_internship_compliance_exemption", name)
    for name in (
        "reviewed_by_user_id", "commitment_device_digest", "commitment_content_hash",
        "answer_snapshot", "submitted_at", "course_content_hash", "course_content_snapshot",
    ):
        op.drop_column("t_internship_safety_completion", name)
    for name in (
        "guardian_token_revoked_at", "guardian_token_used_at", "guardian_token_expires_at",
        "guardian_token_hash", "confirmed_student_id", "confirmed_by_user_id",
        "client_ip_digest", "content_hash",
    ):
        op.drop_column("t_internship_consent", name)
