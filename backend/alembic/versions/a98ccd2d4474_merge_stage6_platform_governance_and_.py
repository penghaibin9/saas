"""merge stage6 platform governance and student affairs P39 heads

Revision ID: a98ccd2d4474
Revises: 0172_tenant_metering, 20260804_affairs_archive_async
Create Date: 2026-08-04 10:13:24.344963
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'a98ccd2d4474'
down_revision = ('0172_tenant_metering', '20260804_affairs_archive_async')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
