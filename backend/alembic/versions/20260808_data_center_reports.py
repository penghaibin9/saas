"""A4 / P0-06：数据驾驶舱专题报表配置 + append-only 发布版本。

Revision ID: 20260808_dc_report
Revises: 20260808_aa_gpa_policy
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260808_dc_report"
down_revision = "20260808_aa_gpa_policy"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_REPORT = "t_data_center_report"
_VERSION = "t_data_center_report_version"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, _REPORT):
        op.create_table(
            _REPORT,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("report_no", sa.String(60), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(40), nullable=False, server_default="ACADEMIC"),
            sa.Column("cycle", sa.String(30), nullable=False, server_default="MONTHLY"),
            sa.Column("scope_name", sa.String(300), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("caliber_code", sa.String(40), nullable=False, server_default="REGISTERED"),
            sa.Column("query_json", sa.JSON(), nullable=True),
            sa.Column("layout_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("owner_id", sa.String(100), nullable=True),
            sa.Column("owner_name", sa.String(100), nullable=True),
            sa.Column("published_version_no", sa.Integer(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
            sa.Column("void_reason", sa.String(500), nullable=True),
            sa.Column("voided_at", sa.DateTime(), nullable=True),
            sa.Column("voided_by_name", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "report_no", name="uk_dc_report_no"),
        )
        op.create_index("ix_t_data_center_report_tenant_id", _REPORT, ["tenant_id"])
        op.create_index("ix_dc_report_tenant_status_updated", _REPORT, ["tenant_id", "status", "updated_at"])

    if not _has_table(bind, _VERSION):
        op.create_table(
            _VERSION,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("report_id", sa.BigInteger(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("snapshot_json", sa.JSON(), nullable=False),
            sa.Column("metrics_json", sa.JSON(), nullable=True),
            sa.Column("trend_json", sa.JSON(), nullable=True),
            sa.Column("as_of", sa.DateTime(), nullable=False),
            sa.Column("caliber_code", sa.String(40), nullable=False),
            sa.Column("scope_json", sa.JSON(), nullable=True),
            sa.Column("source_json", sa.JSON(), nullable=True),
            sa.Column("quality_flags_json", sa.JSON(), nullable=True),
            sa.Column("published_by_id", sa.String(100), nullable=True),
            sa.Column("published_by_name", sa.String(100), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.UniqueConstraint("tenant_id", "report_id", "version_no", name="uk_dc_report_version"),
        )
        op.create_index("ix_t_data_center_report_version_tenant_id", _VERSION, ["tenant_id"])
        op.create_index("ix_t_data_center_report_version_report_id", _VERSION, ["report_id"])
        op.create_index("ix_dc_report_ver_tenant_report", _VERSION, ["tenant_id", "report_id", "version_no"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _VERSION):
        op.drop_table(_VERSION)
    if _has_table(bind, _REPORT):
        op.drop_table(_REPORT)
