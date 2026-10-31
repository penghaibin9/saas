"""补考、清考按开课学院记录审核事实；不回填历史审核。"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_aa_makeup_review"
down_revision = "20261029_ix_tender_integration"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("t_aa_makeup_batch", sa.Column("score_version", sa.Integer(), nullable=False, server_default="0", comment="录分及学院审核版本"))
    op.add_column("t_acad_makeup", sa.Column("review_college_id", sa.BigInteger(), nullable=True, comment="冻结的课程开课学院"))
    op.add_column("t_acad_makeup", sa.Column("college_reviewed_by", sa.String(100), nullable=True, comment="学院审核账号稳定标识"))
    op.add_column("t_acad_makeup", sa.Column("college_reviewed_at", sa.DateTime(), nullable=True, comment="学院审核时间"))


def downgrade():
    raise RuntimeError("审核事实必须保留，请采用兼容代码回退，不删除审核列。")
