"""Internship round 4 evidence package and immutable archive snapshot metadata.

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时本 revision 的表与列
可能已提前创建，故建表/加列/加索引前先探测（同 0103/0104/0105 约定）。
"""
from alembic import op
import sqlalchemy as sa


revision = "0139_intern_evidence"
down_revision = "0138_intern_position_facts"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


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


def _unique_constraint_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {uc["name"] for uc in sa.inspect(bind).get_unique_constraints(table)}


def upgrade():
    if not _has_table("t_audit_outbox"):
        op.create_table(
            "t_audit_outbox",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("event_id", sa.String(64), nullable=False),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.UniqueConstraint("tenant_id", "event_id", name="uk_audit_outbox_event"),
        )
    if "ix_audit_outbox_tenant_status_retry" not in _index_names("t_audit_outbox"):
        op.create_index("ix_audit_outbox_tenant_status_retry", "t_audit_outbox",
                        ["tenant_id", "status", "next_retry_at"])

    evpkg_columns = _column_names("t_internship_evidence_package")
    for column_name, column_type in (
        ("package_sha256", sa.String(64)),
        ("package_size_bytes", sa.BigInteger()),
        ("invalidated_at", sa.DateTime()),
        ("invalidated_by_name", sa.String(100)),
        ("invalidation_reason", sa.String(500)),
    ):
        if column_name not in evpkg_columns:
            op.add_column("t_internship_evidence_package",
                          sa.Column(column_name, column_type, nullable=True))
    op.alter_column("t_internship_evidence_package", "status",
                    existing_type=sa.String(20), type_=sa.String(30),
                    existing_nullable=False)
    if "ix_ix_evpkg_sha256" not in _index_names("t_internship_evidence_package"):
        op.create_index("ix_ix_evpkg_sha256", "t_internship_evidence_package",
                        ["package_sha256"])
    if "uk_ix_evpkg_target_version" not in _unique_constraint_names("t_internship_evidence_package"):
        op.create_unique_constraint(
            "uk_ix_evpkg_target_version", "t_internship_evidence_package",
            ["tenant_id", "package_type", "target_id", "package_version"])
    if "snapshot_version" not in _column_names("t_internship_archive"):
        op.add_column("t_internship_archive",
                      sa.Column("snapshot_version", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE t_internship_evidence_package "
        "SET status = 'LEGACY_SUMMARY' "
        "WHERE status = 'READY' AND package_sha256 IS NULL"
    )


def downgrade():
    op.drop_column("t_internship_archive", "snapshot_version")
    op.drop_constraint("uk_ix_evpkg_target_version",
                       "t_internship_evidence_package", type_="unique")
    op.drop_index("ix_ix_evpkg_sha256",
                  table_name="t_internship_evidence_package")
    op.alter_column("t_internship_evidence_package", "status",
                    existing_type=sa.String(30), type_=sa.String(20),
                    existing_nullable=False)
    op.drop_column("t_internship_evidence_package", "invalidation_reason")
    op.drop_column("t_internship_evidence_package", "invalidated_by_name")
    op.drop_column("t_internship_evidence_package", "invalidated_at")
    op.drop_column("t_internship_evidence_package", "package_size_bytes")
    op.drop_column("t_internship_evidence_package", "package_sha256")
    op.drop_index("ix_audit_outbox_tenant_status_retry", table_name="t_audit_outbox")
    op.drop_table("t_audit_outbox")
