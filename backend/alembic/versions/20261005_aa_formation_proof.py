"""Append historical ProgramCourse formation evidence; no semantic backfill."""
from alembic import op
import sqlalchemy as sa

revision = "20261005_aa_formation_proof"
down_revision = "20260927_aa_grad_term"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("This migration requires MySQL")
    op.create_table(
        "t_aa_program_course_formation_proof",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("program_course_id", sa.BigInteger(), nullable=False),
        sa.Column("program_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("open_term_no", sa.Integer(), nullable=False),
        sa.Column("credit_snapshot", sa.Numeric(4, 1), nullable=False),
        sa.Column("original_formation_mode", sa.String(20), nullable=True),
        sa.Column("formation_mode", sa.String(20), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("evidence_file_id", sa.BigInteger(), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_locator", sa.String(300), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("confirmed_by", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("tenant_id", "program_course_id", name="uk_aa_formation_proof_source"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uk_aa_formation_proof_idem"),
        sa.CheckConstraint("formation_mode IN ('ADMIN_FIXED','SELECTABLE','MERGED','RETAKE','LAYERED')", name="ck_aa_formation_proof_mode"),
        sa.CheckConstraint("open_term_no > 0 AND credit_snapshot >= 0", name="ck_aa_formation_proof_requirements"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_t_aa_program_course_formation_proof_tenant_id", "t_aa_program_course_formation_proof", ["tenant_id"])
    op.create_index("ix_aa_formation_proof_program", "t_aa_program_course_formation_proof", ["tenant_id", "program_id", "program_course_id"])
    op.create_index("ix_aa_task_formation_source", "t_aa_teaching_task", ["tenant_id", "source_program_course_id", "id"])


def downgrade():
    raise RuntimeError("Formation proof and audit history must be preserved; roll back application code only")
