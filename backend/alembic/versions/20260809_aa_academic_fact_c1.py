"""Stage C1: StudentAcademicFact temporal ledger and baseline backfill.

Revision ID: 20260809_aa_fact_c1
Revises: 20260808_dc_report
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260809_aa_fact_c1"
down_revision = "20260808_dc_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_aa_student_academic_fact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("student_status", sa.String(length=50), nullable=False),
        sa.Column("college_id", sa.BigInteger(), nullable=True),
        sa.Column("major_id", sa.BigInteger(), nullable=True),
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        sa.Column("grade", sa.String(length=20), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_ref_id", sa.BigInteger(), nullable=True),
        sa.Column("source_quality", sa.String(length=20), nullable=False, comment="EXACT/DERIVED/INFERRED/UNKNOWN"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "student_id", "version_no", name="uk_aa_student_fact_version"),
    )
    op.create_index("ix_t_aa_student_academic_fact_tenant_id", "t_aa_student_academic_fact", ["tenant_id"], unique=False)
    op.create_index("ix_t_aa_student_academic_fact_student_id", "t_aa_student_academic_fact", ["student_id"], unique=False)
    op.create_index(
        "ix_aa_student_fact_asof",
        "t_aa_student_academic_fact",
        ["tenant_id", "student_id", "valid_from", "valid_to"],
        unique=False,
    )
    op.create_index(
        "ix_aa_student_fact_active",
        "t_aa_student_academic_fact",
        ["tenant_id", "student_id", "valid_to"],
        unique=False,
    )

    # Existing data has a trustworthy *current* projection but no universally reliable
    # historical start date. Do not invent one: establish a migration-time baseline and
    # mark its provenance INFERRED. Later reconciliation/backfill may add older evidence.
    op.execute(
        sa.text(
            """
            INSERT INTO t_aa_student_academic_fact
                (tenant_id, student_id, version_no, valid_from, valid_to,
                 student_status, college_id, major_id, class_id, grade,
                 source_type, source_ref_id, source_quality, created_at, created_by)
            SELECT tenant_id, id, 1, UTC_TIMESTAMP(), NULL,
                   COALESCE(student_status, 'NORMAL'), college_id, major_id, class_id, grade,
                   'BASELINE_BACKFILL', NULL, 'INFERRED', UTC_TIMESTAMP(), NULL
              FROM t_student_profile
             WHERE is_deleted = 0
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_aa_student_fact_active", table_name="t_aa_student_academic_fact")
    op.drop_index("ix_aa_student_fact_asof", table_name="t_aa_student_academic_fact")
    op.drop_index("ix_t_aa_student_academic_fact_student_id", table_name="t_aa_student_academic_fact")
    op.drop_index("ix_t_aa_student_academic_fact_tenant_id", table_name="t_aa_student_academic_fact")
    op.drop_table("t_aa_student_academic_fact")
