"""教材实收退款流水，不修改历史收款。"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_textbook_refund"
down_revision = "20261029_aa_sel_replacement"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("t_aa_textbook_refund",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("fee_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(8, 2), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("operator", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("tenant_id", "fee_id", name="uk_aa_tb_refund_fee"))
    op.create_index("ix_t_aa_textbook_refund_tenant_id", "t_aa_textbook_refund", ["tenant_id"])


def downgrade():
    raise RuntimeError("教材退款流水不可删除；请使用前滚迁移处理")
