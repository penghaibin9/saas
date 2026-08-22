"""Merge employment destination submission and control-plane/teacher schema heads.

Revision ID: 20260821_merge_emp_dest_ctrl_teacher
Revises: 20260821_emp_dest_submission, 20260821_ctrl_teacher_merge

This is a topology-only migration. Both parent revisions own their schema changes;
this revision deliberately performs no DDL and establishes one deployable head.
"""
from __future__ import annotations

revision = "20260821_merge_emp_dest_ctrl_teacher"
down_revision = ("20260821_emp_dest_submission", "20260821_ctrl_teacher_merge")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
