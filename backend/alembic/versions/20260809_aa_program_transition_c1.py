"""Stage C1: program transition assessment evidence ledger.

Revision ID: 20260809_aa_prog_transition_c1
Revises: 20260809_aa_fact_c1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260809_aa_prog_transition_c1"
down_revision = "20260809_aa_fact_c1"
branch_labels = None
depends_on = None

_TABLE = "t_aa_program_transition_assessment"
_REQUIRED_COLUMNS = {
    "id", "tenant_id", "created_at", "created_by", "student_id", "source_fact_id",
    "source_fact_version", "applied_fact_id", "source_type", "source_ref_id",
    "from_major_id", "to_major_id", "target_class_id", "grade", "from_program_id",
    "target_program_id", "decision", "assessment_status", "evidence_json", "assessed_at",
}
_REQUIRED_INDEXES = {
    "ix_t_aa_program_transition_assessment_tenant_id",
    "ix_t_aa_program_transition_assessment_student_id",
    "ix_aa_program_transition_student",
    "ix_aa_program_transition_status",
}


def _create_table() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("source_fact_id", sa.BigInteger(), nullable=False),
        sa.Column("source_fact_version", sa.Integer(), nullable=False),
        sa.Column("applied_fact_id", sa.BigInteger(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_ref_id", sa.BigInteger(), nullable=True),
        sa.Column("from_major_id", sa.BigInteger(), nullable=True),
        sa.Column("to_major_id", sa.BigInteger(), nullable=False),
        sa.Column("target_class_id", sa.BigInteger(), nullable=True),
        sa.Column("grade", sa.String(length=20), nullable=True),
        sa.Column("from_program_id", sa.BigInteger(), nullable=True),
        sa.Column("target_program_id", sa.BigInteger(), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=False,
                  comment="SWITCH_TARGET/MANUAL_REVIEW"),
        sa.Column("assessment_status", sa.String(length=40), nullable=False,
                  comment="READY/NO_TARGET_BINDING/AMBIGUOUS_TARGET/APPLIED/APPLIED_REVIEW_REQUIRED"),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "student_id", "source_type", "source_ref_id", "source_fact_version",
            name="uk_aa_program_transition_source",
        ),
    )
    op.create_index(
        "ix_t_aa_program_transition_assessment_tenant_id", _TABLE, ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_t_aa_program_transition_assessment_student_id", _TABLE, ["student_id"], unique=False
    )
    op.create_index(
        "ix_aa_program_transition_student", _TABLE,
        ["tenant_id", "student_id", "assessed_at"], unique=False,
    )
    op.create_index(
        "ix_aa_program_transition_status", _TABLE,
        ["tenant_id", "assessment_status"], unique=False,
    )


def _validate_precreated_table(bind) -> None:
    inspector = sa.inspect(bind)
    columns = {str(item["name"]) for item in inspector.get_columns(_TABLE)}
    missing_columns = sorted(_REQUIRED_COLUMNS - columns)
    if missing_columns:
        raise RuntimeError(f"{_TABLE} pre-created with incomplete schema: {missing_columns}")

    indexes = {str(item.get("name") or "") for item in inspector.get_indexes(_TABLE)}
    missing_indexes = sorted(_REQUIRED_INDEXES - indexes)
    if missing_indexes:
        raise RuntimeError(f"{_TABLE} pre-created without required indexes: {missing_indexes}")

    uniques = {str(item.get("name") or "") for item in inspector.get_unique_constraints(_TABLE)}
    if "uk_aa_program_transition_source" not in uniques and "uk_aa_program_transition_source" not in indexes:
        raise RuntimeError(f"{_TABLE} missing uk_aa_program_transition_source")


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        _validate_precreated_table(bind)
    else:
        _create_table()


def downgrade() -> None:
    op.drop_table(_TABLE)
