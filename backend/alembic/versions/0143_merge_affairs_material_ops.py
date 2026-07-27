"""Merge latest main with student-affairs material operations branch.

Revision ID: 0143_merge_affairs_material_ops
Revises: 0142_gd_excellent_delay, 0127_affairs_material_batch_ops
"""

revision = "0143_merge_affairs_material_ops"
down_revision = (
    "0142_gd_excellent_delay",
    "0127_affairs_material_batch_ops",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
