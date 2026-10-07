"""Append task source handoffs without rewriting original execution or history."""
from alembic import op
import sqlalchemy as sa

revision = "20261005_aa_task_source_handoff"
down_revision = "20261005_aa_formation_proof"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("This migration requires MySQL")
    op.create_table(
        "t_aa_teaching_task_source_handoff",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("term_id", sa.BigInteger(), nullable=False),
        sa.Column("execution_task_id", sa.BigInteger(), nullable=False),
        sa.Column("successor_task_id", sa.BigInteger(), nullable=False),
        sa.Column("execution_source_id", sa.BigInteger(), nullable=False),
        sa.Column("successor_source_id", sa.BigInteger(), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("confirmed_by", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("tenant_id", "successor_task_id", name="uk_aa_task_handoff_successor"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_aa_task_handoff_idem"),
        sa.CheckConstraint("execution_task_id <> successor_task_id", name="ck_aa_task_handoff_distinct"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_t_aa_teaching_task_source_handoff_tenant_id", "t_aa_teaching_task_source_handoff", ["tenant_id"])
    op.create_index("ix_aa_task_handoff_execution", "t_aa_teaching_task_source_handoff", ["tenant_id", "term_id", "execution_task_id"])


def downgrade():
    raise RuntimeError("Task handoffs and business history must be preserved; roll back application code only")
