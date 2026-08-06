"""包 9：新增毕业设计不可变归档版本链。

Revision ID: 20260806_gd_pkg9_archive_ver
Revises: 20260804_aa_enrollment_program
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260806_gd_pkg9_archive_ver"
down_revision = "20260804_aa_enrollment_program"
branch_labels = None
depends_on = None

_TABLE = "t_gd_archive_version"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260806_gd_pkg9_archive_ver requires MySQL")


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    if _TABLE in set(inspect(bind).get_table_names()):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("archive_record_id", sa.BigInteger(), nullable=False),
        sa.Column("gd_student_id", sa.BigInteger(), nullable=False),
        sa.Column("archive_version", sa.Integer(), nullable=False),
        sa.Column("current_flag", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("previous_archive_id", sa.BigInteger(), nullable=True),
        sa.Column("invalidated_reason", sa.String(length=500), nullable=True),
        sa.Column("source_manifest_json", sa.JSON(), nullable=False),
        sa.Column("source_manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("archive_batch_no", sa.String(length=100), nullable=False),
        sa.Column("filed_at", sa.DateTime(), nullable=False),
        sa.Column("filed_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.PrimaryKeyConstraint("id", name="pk_t_gd_archive_version"),
        sa.UniqueConstraint(
            "tenant_id", "archive_record_id", "archive_version",
            name="uk_gd_archive_version_no",
        ),
    )
    op.create_index(
        "ix_gd_archive_current",
        _TABLE,
        ["tenant_id", "archive_record_id", "current_flag"],
        unique=False,
    )
    op.create_index(
        "ix_gd_archive_student_version",
        _TABLE,
        ["tenant_id", "gd_student_id", "archive_version"],
        unique=False,
    )


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    if _TABLE not in set(inspect(bind).get_table_names()):
        return
    op.drop_index("ix_gd_archive_student_version", table_name=_TABLE)
    op.drop_index("ix_gd_archive_current", table_name=_TABLE)
    op.drop_table(_TABLE)
