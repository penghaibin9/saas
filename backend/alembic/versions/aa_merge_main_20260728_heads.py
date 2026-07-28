"""Merge the academic-affairs delivery head with the current main application head.

Revision ID: aa_merge_main_20260728
Revises: 0134_aa_makeup_source_identity, 0142_gd_excellent_delay

Graph-only merge. No DDL is executed here: each parent branch keeps its own ordered,
idempotent migrations while ``alembic upgrade head`` returns to one deterministic head.
"""

revision = "aa_merge_main_20260728"
down_revision = (
    "0134_aa_makeup_source_identity",
    "0142_gd_excellent_delay",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
