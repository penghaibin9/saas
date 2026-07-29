"""merge academic affairs final with main

Revision ID: aa_final_20260729
Revises: 0134_aa_makeup_source_identity, 0144_affairs_leave_identity_cutover
Create Date: 2026-07-29 03:02:03.697329
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'aa_final_20260729'
down_revision = ('0134_aa_makeup_source_identity', '0144_affairs_leave_identity_cutover')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
