"""Merge Student Affairs RC and Graduation archive migration heads.

Revision ID: 20260827_affairs_gd_merge
Revises: 20260824_affairs_aid_audit_ns_rc, 20260824_gd_arch_audit_cols

This is a topology-only Alembic merge revision. Both parent migrations remain
independently reversible and keep their original schema operations; this file
only restores the repository invariant that Alembic has a single head after
R0 semantic integration of latest main into the Student Affairs final RC.
"""
from __future__ import annotations

revision = "20260827_affairs_gd_merge"
down_revision = (
    "20260824_affairs_aid_audit_ns_rc",
    "20260824_gd_arch_audit_cols",
)
branch_labels = None
depends_on = None

assert len(revision) <= 32


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
