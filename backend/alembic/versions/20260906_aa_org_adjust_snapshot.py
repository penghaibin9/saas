"""Compatibility anchor for the unmerged academic adjustment delivery.

The draft's in-place VARCHAR widening was never released on main.  Preserve this
revision identifier, but perform the additive expansion in 20260909_aa_adjust_expand.
No legacy column, constraint or historical receipt is altered here.
"""
revision = '20260906_aa_org_adjust_snapshot'
down_revision = '20260901_orientation_self_activate_o6'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
