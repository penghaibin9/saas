"""merge affairs and sandbox reset migration heads

Revision ID: 20260829_affairs_sandbox_merge
Revises: 20260827_affairs_gd_merge, 20260828_sandbox_reset_guards
Create Date: 2026-08-29
"""

revision = "20260829_affairs_sandbox_merge"
down_revision = (
    "20260827_affairs_gd_merge",
    "20260828_sandbox_reset_guards",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
