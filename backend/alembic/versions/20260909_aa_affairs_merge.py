"""Merge additive academic evidence with the current student-affairs lineage.

This revision changes only the migration graph. Both parent upgrades must finish
before this head is stamped; no historical revision or business row is rewritten.
"""

revision = "20260909_aa_affairs_merge"
down_revision = ("20260909_aa_adjust_expand", "20260906_fee_reduction_four_end")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
