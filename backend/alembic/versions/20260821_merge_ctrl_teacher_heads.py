"""Merge control-plane P0 and Teacher V3 schema heads.

Revision ID: 20260821_ctrl_teacher_merge
Revises: 20260820_ctrl_offboarding, 20260820_teacher_emp_reco

This is a topology-only migration. Both parent revisions own their schema changes;
this revision deliberately performs no DDL and establishes one deployable head.
"""
from __future__ import annotations

revision = "20260821_ctrl_teacher_merge"
down_revision = ("20260820_ctrl_offboarding", "20260820_teacher_emp_reco")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
