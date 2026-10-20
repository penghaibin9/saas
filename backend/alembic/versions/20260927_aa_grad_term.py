"""Give new graduation audits an explicit semester; preserve historical rows."""
from alembic import op
import sqlalchemy as sa

revision = "20260927_aa_grad_term"
down_revision = "20260914_aa_opt_candidates"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("This migration requires MySQL")
    op.add_column("t_aa_graduation_audit_batch", sa.Column(
        "term_id", sa.BigInteger(), nullable=True, comment="所属学期；历史批次未自动回填"))
    op.create_index("ix_aa_grad_batch_tenant_term", "t_aa_graduation_audit_batch", ["tenant_id", "term_id"])


def downgrade():
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM t_aa_graduation_audit_batch WHERE term_id IS NOT NULL LIMIT 1"
    )).first():
        raise RuntimeError("Graduation semester links exist; preserve the column and roll back application code only")
    op.drop_index("ix_aa_grad_batch_tenant_term", table_name="t_aa_graduation_audit_batch")
    op.drop_column("t_aa_graduation_audit_batch", "term_id")
