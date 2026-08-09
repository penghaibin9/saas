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

_TABLE = "t_aa_student_academic_fact"
_REQUIRED_COLUMNS = {
    "id", "tenant_id", "created_at", "created_by", "student_id", "version_no",
    "valid_from", "valid_to", "student_status", "college_id", "major_id", "class_id",
    "grade", "source_type", "source_ref_id", "source_quality",
}
_REQUIRED_INDEXES = {
    "ix_t_aa_student_academic_fact_tenant_id",
    "ix_t_aa_student_academic_fact_student_id",
    "ix_aa_student_fact_asof",
    "ix_aa_student_fact_active",
}


def _create_table() -> None:
    op.create_table(
        _TABLE,
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
    op.create_index("ix_t_aa_student_academic_fact_tenant_id", _TABLE, ["tenant_id"], unique=False)
    op.create_index("ix_t_aa_student_academic_fact_student_id", _TABLE, ["student_id"], unique=False)
    op.create_index(
        "ix_aa_student_fact_asof", _TABLE,
        ["tenant_id", "student_id", "valid_from", "valid_to"], unique=False,
    )
    op.create_index(
        "ix_aa_student_fact_active", _TABLE,
        ["tenant_id", "student_id", "valid_to"], unique=False,
    )


def _validate_precreated_table(bind) -> None:
    """Fail closed when 0001 metadata.create_all pre-creates the current model table.

    Fresh-database upgrades import today's full metadata in revision 0001, so a table
    introduced by this later revision may already exist before this revision executes.
    Production databases that already ran 0001 historically will not have it, so the
    normal path still creates the table here. Existing-but-wrong schema must never be
    silently accepted.
    """
    inspector = sa.inspect(bind)
    columns = {str(col["name"]) for col in inspector.get_columns(_TABLE)}
    missing_columns = sorted(_REQUIRED_COLUMNS - columns)
    if missing_columns:
        raise RuntimeError(
            f"{_TABLE} was pre-created with incomplete schema; missing columns={missing_columns}"
        )

    index_names = {str(idx.get("name") or "") for idx in inspector.get_indexes(_TABLE)}
    missing_indexes = sorted(_REQUIRED_INDEXES - index_names)
    if missing_indexes:
        raise RuntimeError(
            f"{_TABLE} was pre-created without required indexes; missing indexes={missing_indexes}"
        )

    unique_names = {str(item.get("name") or "") for item in inspector.get_unique_constraints(_TABLE)}
    # MySQL may expose a UNIQUE constraint as an index only. Accept either representation,
    # but require the exact stable name so model/migration parity remains deterministic.
    if "uk_aa_student_fact_version" not in unique_names and "uk_aa_student_fact_version" not in index_names:
        raise RuntimeError(f"{_TABLE} missing uk_aa_student_fact_version")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_TABLE):
        _validate_precreated_table(bind)
    else:
        _create_table()

    # Existing data has a trustworthy *current* projection but no universally reliable
    # historical start date. Do not invent one: establish a migration-time baseline and
    # mark its provenance INFERRED. NOT EXISTS keeps this safe when 0001 created the table
    # early and an ORM data migration already bootstrapped an EXACT fact for a row.
    op.execute(
        sa.text(
            """
            INSERT INTO t_aa_student_academic_fact
                (tenant_id, student_id, version_no, valid_from, valid_to,
                 student_status, college_id, major_id, class_id, grade,
                 source_type, source_ref_id, source_quality, created_at, created_by)
            SELECT p.tenant_id, p.id, 1, UTC_TIMESTAMP(), NULL,
                   COALESCE(p.student_status, 'NORMAL'), p.college_id, p.major_id, p.class_id, p.grade,
                   'BASELINE_BACKFILL', NULL, 'INFERRED', UTC_TIMESTAMP(), NULL
              FROM t_student_profile p
             WHERE p.is_deleted = 0
               AND NOT EXISTS (
                    SELECT 1
                      FROM t_aa_student_academic_fact f
                     WHERE f.tenant_id = p.tenant_id
                       AND f.student_id = p.id
               )
            """
        )
    )


def downgrade() -> None:
    # This revision owns the logical introduction of the table even when a fresh-database
    # 0001 metadata.create_all happened to materialize it earlier in the same upgrade chain.
    op.drop_table(_TABLE)
