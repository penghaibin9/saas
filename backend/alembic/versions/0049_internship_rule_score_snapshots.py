"""Version rules and bind calculated scores to a configuration snapshot.

Revision ID: 0049_internship_rule_score_snapshots
Revises: 0048_internship_advisor_identity
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0049_internship_rule_score_snapshots"
down_revision = "0048_internship_advisor_identity"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    return ({x["name"] for x in inspector.get_columns(table)}
            if table in inspector.get_table_names() else set())


def upgrade() -> None:
    bind = op.get_bind()
    if "rules_version" not in _columns(bind, "t_internship_batch"):
        op.add_column("t_internship_batch", sa.Column("rules_version", sa.Integer(), nullable=False, server_default="1"))
    cols = _columns(bind, "t_internship_final_score")
    if "score_config_id" not in cols:
        op.add_column("t_internship_final_score", sa.Column("score_config_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_t_internship_final_score_score_config_id", "t_internship_final_score", ["score_config_id"])
    if "score_config_version" not in cols:
        op.add_column("t_internship_final_score", sa.Column("score_config_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, "t_internship_final_score")
    if "score_config_id" in cols:
        names = {x["name"] for x in inspect(bind).get_indexes("t_internship_final_score")}
        if "ix_t_internship_final_score_score_config_id" in names:
            op.drop_index("ix_t_internship_final_score_score_config_id", table_name="t_internship_final_score")
        op.drop_column("t_internship_final_score", "score_config_id")
    if "score_config_version" in _columns(bind, "t_internship_final_score"):
        op.drop_column("t_internship_final_score", "score_config_version")
    if "rules_version" in _columns(bind, "t_internship_batch"):
        op.drop_column("t_internship_batch", "rules_version")
