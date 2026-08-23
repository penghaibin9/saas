"""Separate difficulty-recognition batch audits from application audits.

Revision ID: 20260823_affairs_aid_audit_ns
Revises: 20260822_pr190_main_merge

Historical BATCH_* rows used biz_type=AID, so a batch and an application with
the same numeric id shared one audit key. Move those rows to AID_BATCH; new
writes are routed to the same namespace by affairs_data_integrity_guard.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260823_affairs_aid_audit_ns"
down_revision = "20260822_pr190_main_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE t_affairs_audit_trail "
        "SET biz_type = 'AID_BATCH' "
        "WHERE biz_type = 'AID' AND action LIKE 'BATCH\\_%' ESCAPE '\\\\'"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE t_affairs_audit_trail "
        "SET biz_type = 'AID' "
        "WHERE biz_type = 'AID_BATCH' AND action LIKE 'BATCH\\_%' ESCAPE '\\\\'"
    ))
