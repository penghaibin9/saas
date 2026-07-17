"""merge internship-aa/feedback/portal heads

Revision ID: a1198e75cb72
Revises: 0054_merge_internship_aa_heads, 4c722c7c33fa, portal_r3_sign_record
Create Date: 2026-07-17 21:50:45.798853
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'a1198e75cb72'
down_revision = ('0054_merge_internship_aa_heads', '4c722c7c33fa', 'portal_r3_sign_record')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
