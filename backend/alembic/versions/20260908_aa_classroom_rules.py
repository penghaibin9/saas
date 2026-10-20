"""Independent classroom use rules; preserve existing rows and actual exam seats."""
from alembic import op
import sqlalchemy as sa

revision = "20260908_aa_classroom_rules"
down_revision = "20260908_aa_grade_effect_job"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy rooms previously allowed all three uses, subject to status/exclusive gates.
    # New create commands explicitly default borrow to false; never rewrite old rules.
    for name, label in (("allow_schedule", "允许排课"), ("allow_exam", "允许排考"), ("allow_borrow", "开放借用")):
        op.add_column("t_aa_classroom", sa.Column(name, sa.Boolean(), nullable=False,
            server_default=sa.true(), comment=label))


def downgrade():
    for name in ("allow_borrow", "allow_exam", "allow_schedule"):
        op.drop_column("t_aa_classroom", name)
