"""Persist exact retake grade and enrollment roster sources; no legacy guessing."""
from alembic import op
import sqlalchemy as sa

revision = "20260909_aa_retake_origin"
down_revision = "20260908_aa_classroom_rules"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("t_aa_retake_apply", sa.Column("origin_grade_id", sa.BigInteger(), nullable=True,
                  comment="申请时精确正式成绩ID；历史未证明来源不得猜配"))
    op.add_column("t_aa_retake_apply", sa.Column("enrollment_roster_version_id", sa.BigInteger(), nullable=True,
                  comment="编班事务实际采用的正式名单版本；不以当前名单回填"))
    op.create_index("ix_aa_retake_origin", "t_aa_retake_apply", ["tenant_id", "origin_grade_id"])


def downgrade():
    op.drop_index("ix_aa_retake_origin", table_name="t_aa_retake_apply")
    op.drop_column("t_aa_retake_apply", "enrollment_roster_version_id")
    op.drop_column("t_aa_retake_apply", "origin_grade_id")
