"""Graduation round 3 audit actor, permission and scope evidence."""

from alembic import op
import sqlalchemy as sa


revision = "gd_r3_audit_context"
down_revision = "gd_r2_followup_recheck"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("t_gd_audit_trail", sa.Column("actor_user_id", sa.BigInteger(), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("actor_context_id", sa.String(64), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("actor_name_snapshot", sa.String(100), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("role_code", sa.String(64), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("permission_code", sa.String(120), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("data_scope_snapshot", sa.JSON(), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("batch_id", sa.BigInteger(), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("before_json", sa.JSON(), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("after_json", sa.JSON(), nullable=True))
    op.add_column("t_gd_audit_trail", sa.Column("reason", sa.String(1000), nullable=True))
    op.create_index("ix_gd_audit_batch", "t_gd_audit_trail", ["tenant_id", "batch_id"])
    op.add_column("t_excel_import_job", sa.Column("file_sha256", sa.String(64), nullable=True))
    op.add_column("t_excel_import_job", sa.Column("dry_run_sha256", sa.String(64), nullable=True))
    op.add_column("t_excel_import_job", sa.Column("preview_token_sha256", sa.String(64), nullable=True))
    op.add_column("t_excel_import_job", sa.Column("batch_scope", sa.String(500), nullable=True))
    op.add_column("t_excel_import_job", sa.Column("data_scope_snapshot", sa.JSON(), nullable=True))
    op.add_column(
        "t_excel_import_job",
        sa.Column("expected_success_rows", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    for column in (
        "expected_success_rows", "data_scope_snapshot", "batch_scope",
        "preview_token_sha256", "dry_run_sha256", "file_sha256",
    ):
        op.drop_column("t_excel_import_job", column)
    op.drop_index("ix_gd_audit_batch", table_name="t_gd_audit_trail")
    for column in (
        "reason", "after_json", "before_json", "batch_id", "data_scope_snapshot",
        "permission_code", "role_code", "actor_name_snapshot", "actor_context_id", "actor_user_id",
    ):
        op.drop_column("t_gd_audit_trail", column)
