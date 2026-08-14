"""V3 M2 canonical additive prerequisite for A01-10.

Revision ID: 20260815_internship_e_position_campaign
Revises: 20260815_internship_e_m4

It follows M4 only to preserve the already-pushed single branch lineage. Historical positions get
source_type=SCHOOL while campaign_id stays NULL; no historical campaign is guessed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_internship_e_position_campaign"
down_revision = "20260815_internship_e_m4"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_internship_e_position_campaign requires MySQL")


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    columns = {column["name"] for column in insp.get_columns("t_internship_position")}
    if "campaign_id" not in columns:
        op.add_column("t_internship_position", sa.Column("campaign_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_t_internship_position_campaign_id", "t_internship_position", ["campaign_id"])
    if "source_type" not in columns:
        op.add_column("t_internship_position", sa.Column("source_type", sa.String(30), nullable=True))
        op.execute("UPDATE t_internship_position SET source_type='SCHOOL' WHERE source_type IS NULL")
        op.alter_column("t_internship_position", "source_type", existing_type=sa.String(30), nullable=False)
    insp = inspect(bind)
    index_names = {index["name"] for index in insp.get_indexes("t_internship_position")}
    if "ix_intern_position_campaign_catalog" not in index_names:
        op.create_index(
            "ix_intern_position_campaign_catalog",
            "t_internship_position",
            ["tenant_id", "campaign_id", "status", "company_id", "is_deleted"],
        )


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    columns = {column["name"] for column in insp.get_columns("t_internship_position")}
    index_names = {index["name"] for index in insp.get_indexes("t_internship_position")}
    if "ix_intern_position_campaign_catalog" in index_names:
        op.drop_index("ix_intern_position_campaign_catalog", table_name="t_internship_position")
    if "source_type" in columns:
        op.drop_column("t_internship_position", "source_type")
    if "campaign_id" in columns:
        if "ix_t_internship_position_campaign_id" in index_names:
            op.drop_index("ix_t_internship_position_campaign_id", table_name="t_internship_position")
        op.drop_column("t_internship_position", "campaign_id")
