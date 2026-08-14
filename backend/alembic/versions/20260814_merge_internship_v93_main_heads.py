"""Merge Internship V9.3 migrations with the latest main message-delivery head.

Revision ID: 20260814_merge_ix_v93_main
Revises: 20260814_ix_missing_idx, msg_channel_delivery_20260813

This is deliberately a no-op Alembic merge revision.  PR #115's internship
migrations were already shared and exercised before latest main introduced the
parallel ``msg_channel_delivery_20260813`` head.  Re-parenting an existing
migration would rewrite that published ancestry and could make a database that
already ran the old #115 head appear current while silently skipping the main
migration.  Keeping both histories intact and merging their heads is the
repository's established safe pattern.
"""
from __future__ import annotations

revision = "20260814_merge_ix_v93_main"
down_revision = ("20260814_ix_missing_idx", "msg_channel_delivery_20260813")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
