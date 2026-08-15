"""Control Plane I3: normalized identity import staging rows.

Revision ID: 20260815_ctrl_identity_staging
Revises: 20260815_ctrl_role_gov
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_ctrl_identity_staging"
down_revision = "20260815_ctrl_role_gov"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_ctrl_identity_staging requires MySQL")


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())
    if insp.has_table("t_identity_import_staging_row"):
        return
    op.create_table(
        "t_identity_import_staging_row",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("import_job_id", sa.BigInteger(), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("natural_key", sa.String(160), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_student_id", sa.BigInteger()),
        sa.Column("resolved_user_id", sa.BigInteger()),
        sa.Column("row_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "import_job_id", "row_no", name="uk_identity_staging_job_row"),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_t_identity_import_staging_row_tenant_id", "t_identity_import_staging_row", ["tenant_id"])
    op.create_index("ix_t_identity_import_staging_row_import_job_id", "t_identity_import_staging_row", ["import_job_id"])
    op.create_index("ix_t_identity_import_staging_row_resolved_student_id", "t_identity_import_staging_row", ["resolved_student_id"])
    op.create_index("ix_t_identity_import_staging_row_resolved_user_id", "t_identity_import_staging_row", ["resolved_user_id"])
    op.create_index(
        "ix_identity_staging_job_status_row", "t_identity_import_staging_row",
        ["tenant_id", "import_job_id", "validation_status", "row_no"],
    )
    op.create_index(
        "ix_identity_staging_job_entity_key", "t_identity_import_staging_row",
        ["tenant_id", "import_job_id", "entity_type", "natural_key"],
    )


def downgrade() -> None:
    _require_mysql()
    if inspect(op.get_bind()).has_table("t_identity_import_staging_row"):
        op.drop_table("t_identity_import_staging_row")
