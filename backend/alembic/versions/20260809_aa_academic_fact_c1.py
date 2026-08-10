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
    """Fail closed when 0001 metadata.create_all pre-creates the current model table."""
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
    if "uk_aa_student_fact_version" not in unique_names and "uk_aa_student_fact_version" not in index_names:
        raise RuntimeError(f"{_TABLE} missing uk_aa_student_fact_version")


def _normalize_fresh_chain_bootstrap_artifacts(bind) -> None:
    """Normalize only facts manufactured by today's ORM while replaying old migrations.

    Revision 0001 imports *current* metadata and may therefore create this C1 table years
    earlier in a fresh-database replay. Historical ORM data migrations that insert a
    StudentProfile then trigger today's ``after_insert`` hook and create a PROFILE_CREATE
    fact before C1 officially exists. Later legacy migrations can legitimately finish
    filling that profile's org/grade, leaving the synthetic fact stale.

    Those rows never existed on a real pre-C1 production database. At the point C1 takes
    ownership we therefore collapse only the narrow synthetic shape
    ``PROFILE_CREATE + version 1 + current + one fact per student`` into the same
    INFERRED baseline a real production upgrade would receive. Any other pre-existing
    fact shape is unexpected real data and fails closed instead of being rewritten.
    """
    unexpected = bind.execute(sa.text("""
        SELECT COUNT(*)
          FROM t_aa_student_academic_fact f
         WHERE NOT (
               f.version_no = 1
           AND f.valid_to IS NULL
           AND f.source_type = 'PROFILE_CREATE'
           AND f.source_ref_id IS NULL
         )
    """)).scalar() or 0
    if int(unexpected) > 0:
        raise RuntimeError(
            "pre-created academic fact table contains non-bootstrap facts before C1; refusing normalization"
        )

    duplicate = bind.execute(sa.text("""
        SELECT COUNT(*)
          FROM (
                SELECT tenant_id, student_id
                  FROM t_aa_student_academic_fact
                 GROUP BY tenant_id, student_id
                HAVING COUNT(*) <> 1
          ) x
    """)).scalar() or 0
    if int(duplicate) > 0:
        raise RuntimeError(
            "pre-created academic fact table contains multi-row student history before C1; refusing normalization"
        )

    # For active profiles, align the synthetic v1 to the current projection and clearly
    # downgrade provenance from EXACT to the same INFERRED baseline used on real upgrades.
    bind.execute(sa.text("""
        UPDATE t_aa_student_academic_fact f
        JOIN t_student_profile p
          ON p.tenant_id = f.tenant_id
         AND p.id = f.student_id
           SET f.student_status = COALESCE(p.student_status, 'NORMAL'),
               f.college_id = p.college_id,
               f.major_id = p.major_id,
               f.class_id = p.class_id,
               f.grade = p.grade,
               f.valid_from = UTC_TIMESTAMP(),
               f.source_type = 'BASELINE_BACKFILL',
               f.source_quality = 'INFERRED',
               f.created_at = UTC_TIMESTAMP(),
               f.created_by = NULL
         WHERE p.is_deleted = 0
           AND f.version_no = 1
           AND f.valid_to IS NULL
           AND f.source_type = 'PROFILE_CREATE'
    """))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    precreated = inspector.has_table(_TABLE)
    if precreated:
        _validate_precreated_table(bind)
        _normalize_fresh_chain_bootstrap_artifacts(bind)
    else:
        _create_table()

    # Older migrations may have queried table readiness through the StudentProfile
    # after_insert hook before this revision existed. Once C1 has validated/created the
    # table, later data migrations in the same upgrade chain may bootstrap normally.
    bind.info["stage_c1_academic_fact_table_ready"] = True

    # Real production upgrades reach C1 with no fact table, while fresh replay may have
    # normalized synthetic rows above. Fill only students that still have no fact.
    op.execute(sa.text("""
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
    """))


def downgrade() -> None:
    op.drop_table(_TABLE)
