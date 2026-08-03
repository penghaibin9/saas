"""merge_sys14_workflow_and_internship_hardening

Revision ID: 73e91b9e47af
Revises: 0165_workflow_security_policy, 20260803_internship_hardening
Create Date: 2026-08-04 04:09:51.078631
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '73e91b9e47af'
down_revision = ('0165_workflow_security_policy', '20260803_internship_hardening')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
