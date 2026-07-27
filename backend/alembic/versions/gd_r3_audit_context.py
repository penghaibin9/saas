"""Graduation round 3 audit actor, permission and scope evidence.

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时这些列/索引可能已
提前创建，故先探测再执行原始 DDL（同 0103/0104/0105 约定）。
"""

from alembic import op
import sqlalchemy as sa


revision = "gd_r3_audit_context"
down_revision = "gd_r2_followup_recheck"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _index_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table)}


def upgrade():
    audit_columns = _column_names("t_gd_audit_trail")
    for name, col in (
        ("actor_user_id", sa.BigInteger()),
        ("actor_context_id", sa.String(64)),
        ("actor_name_snapshot", sa.String(100)),
        ("role_code", sa.String(64)),
        ("permission_code", sa.String(120)),
        ("data_scope_snapshot", sa.JSON()),
        ("batch_id", sa.BigInteger()),
        ("before_json", sa.JSON()),
        ("after_json", sa.JSON()),
        ("reason", sa.String(1000)),
    ):
        if name not in audit_columns:
            op.add_column("t_gd_audit_trail", sa.Column(name, col, nullable=True))
    if "ix_gd_audit_batch" not in _index_names("t_gd_audit_trail"):
        op.create_index("ix_gd_audit_batch", "t_gd_audit_trail", ["tenant_id", "batch_id"])

    excel_columns = _column_names("t_excel_import_job")
    for name, col in (
        ("file_sha256", sa.String(64)),
        ("dry_run_sha256", sa.String(64)),
        ("preview_token_sha256", sa.String(64)),
        ("batch_scope", sa.String(500)),
        ("data_scope_snapshot", sa.JSON()),
    ):
        if name not in excel_columns:
            op.add_column("t_excel_import_job", sa.Column(name, col, nullable=True))
    if "expected_success_rows" not in excel_columns:
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
