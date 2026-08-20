"""INT C-C1 Attendance expand schema and repeatable legacy inventory."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from app.db.session import get_sessionmaker
from app.models import AaAttendanceSession, AffairsAuditTrail
from app.modules.academic_affairs.services.academic_affairs_attendance_migration_inventory import (
    inventory_legacy_attendance_sources,
)


def _attendance(*, tenant_id: int, date: str, slot: int, source_type=None, occurrence=None, deleted=False):
    return AaAttendanceSession(
        tenant_id=tenant_id,
        class_id=7001,
        teaching_task_id=8001 if source_type == "FORMAL_TEACHING" else None,
        occurrence_identity=occurrence,
        source_type=source_type,
        source_reason="管理员补录证据齐全" if source_type == "ADMIN_SPECIAL" else None,
        source_evidence="ticket:INT-C1" if source_type == "ADMIN_SPECIAL" else None,
        course_name="INT C-C1",
        term_code="2026-1",
        teacher_key="INT-T1",
        session_date=date,
        slot_no=slot,
        roster_json="[]",
        total_count=0,
        present_count=0,
        absent_count=0,
        status="DRAFT",
        is_deleted=deleted,
    )


def test_int_c1_expand_contract_has_nullable_columns_and_no_premature_tightening():
    columns = AaAttendanceSession.__table__.c
    for name in (
        "teaching_task_id",
        "occurrence_identity",
        "source_type",
        "source_reason",
        "source_evidence",
    ):
        assert columns[name].nullable is True
    assert columns["occurrence_identity"].type.length == 255
    assert columns["source_type"].type.length == 30

    constraint_names = {c.name for c in AaAttendanceSession.__table__.constraints if c.name}
    assert "uk_aa_attendance_occurrence" not in constraint_names
    assert "ck_aa_attendance_source_type" not in constraint_names
    index_names = {idx.name for idx in AaAttendanceSession.__table__.indexes}
    assert {
        "ix_aa_attendance_task",
        "ix_aa_attendance_source",
        "ix_aa_attendance_occurrence",
    }.issubset(index_names)

    source = Path("alembic/versions/20260816_academic_int_c1_attendance.py").read_text(encoding="utf-8")
    upper = source.upper()
    assert 'down_revision = "20260816_acad_int_ac4"' in source
    assert "CREATE_UNIQUE_CONSTRAINT" not in upper
    assert "CREATE_CHECK_CONSTRAINT" not in upper
    assert "UPDATE T_AA_ATTENDANCE_SESSION" not in upper
    assert "DELETE FROM T_AA_ATTENDANCE_SESSION" not in upper
    assert "NULLABLE=FALSE" not in upper


def test_int_c1_expand_schema_is_real_mysql_and_deliberately_not_contract_tightened(db_mode):
    db = get_sessionmaker()()
    try:
        inspector = inspect(db.bind)
        columns = {c["name"]: c for c in inspector.get_columns("t_aa_attendance_session")}
        for name in (
            "teaching_task_id",
            "occurrence_identity",
            "source_type",
            "source_reason",
            "source_evidence",
        ):
            assert columns[name]["nullable"] is True

        indexes = {idx["name"]: tuple(idx["column_names"]) for idx in inspector.get_indexes("t_aa_attendance_session")}
        assert indexes["ix_aa_attendance_task"] == ("tenant_id", "teaching_task_id")
        assert indexes["ix_aa_attendance_source"] == ("tenant_id", "source_type")
        assert indexes["ix_aa_attendance_occurrence"] == ("tenant_id", "occurrence_identity")
        uniques = {u["name"] for u in inspector.get_unique_constraints("t_aa_attendance_session")}
        checks = {c["name"] for c in inspector.get_check_constraints("t_aa_attendance_session")}
        assert "uk_aa_attendance_occurrence" not in uniques
        assert "ck_aa_attendance_source_type" not in checks

        tenant = 1000000000000008911
        identity = "V1:TASK:8001:ITEM:9001:DATE:2026-03-02:SLOT:2"
        db.add_all(
            [
                _attendance(
                    tenant_id=tenant,
                    date="2026-03-02",
                    slot=2,
                    source_type="FORMAL_TEACHING",
                    occurrence=identity,
                ),
                _attendance(
                    tenant_id=tenant,
                    date="2026-03-02",
                    slot=2,
                    source_type="FORMAL_TEACHING",
                    occurrence=identity,
                ),
                _attendance(
                    tenant_id=tenant,
                    date="2026-03-03",
                    slot=3,
                    source_type="ADMIN_MANUAL",
                    occurrence=None,
                ),
            ]
        )
        db.commit()
        # Expand phase intentionally does not claim DB single-winner/source vocabulary yet.
        # C-W1 app guards remain the live protection until INT writer dual-write and dirty-data
        # reconciliation justify the later contract migration.
        count = db.query(AaAttendanceSession).filter(AaAttendanceSession.tenant_id == tenant).count()
        assert count == 3
    finally:
        db.close()


def test_int_c1_legacy_inventory_is_same_tenant_read_only_and_repeatable(db_mode):
    db = get_sessionmaker()()
    try:
        tenant = 1000000000000008921
        matched = _attendance(tenant_id=tenant, date="2026-04-01", slot=1)
        unresolved = _attendance(tenant_id=tenant, date="2026-04-02", slot=2)
        deleted = _attendance(tenant_id=tenant, date="2026-04-03", slot=3, deleted=True)
        modern = _attendance(
            tenant_id=tenant,
            date="2026-04-04",
            slot=4,
            source_type="FORMAL_TEACHING",
            occurrence="V1:MODERN:8921",
        )
        db.add_all([matched, unresolved, deleted, modern])
        db.flush()
        db.add_all(
            [
                AffairsAuditTrail(
                    tenant_id=tenant,
                    biz_type="AA_ATTENDANCE",
                    biz_id=matched.id,
                    action="CREATE",
                    operator="int",
                    detail="task=-;source=ADMIN_MANUAL;course=x",
                ),
                AffairsAuditTrail(
                    tenant_id=tenant + 1,
                    biz_type="AA_ATTENDANCE",
                    biz_id=unresolved.id,
                    action="CREATE",
                    operator="neighbor",
                    detail="source=ADMIN_MANUAL",
                ),
                AffairsAuditTrail(
                    tenant_id=tenant,
                    biz_type="AA_ATTENDANCE",
                    biz_id=999999991,
                    action="CREATE",
                    operator="orphan",
                    detail="source=ADMIN_MANUAL",
                ),
            ]
        )
        db.commit()

        before = db.query(AaAttendanceSession).filter(AaAttendanceSession.tenant_id == tenant).count()
        first = inventory_legacy_attendance_sources(db, tenant, sample_limit=10)
        second = inventory_legacy_attendance_sources(db, tenant, sample_limit=10)
        after = db.query(AaAttendanceSession).filter(AaAttendanceSession.tenant_id == tenant).count()

        assert first == second
        assert before == after == 4
        assert first["legacyRows"] == 3
        assert first["activeLegacyRows"] == 2
        assert first["deletedLegacyRows"] == 1
        assert first["manualAuditMatchedRows"] == 1
        assert first["unresolvedRows"] == 2
        assert first["orphanManualAuditRows"] == 1
        assert unresolved.id in first["unresolvedSampleSessionIds"]
        assert matched.id not in first["unresolvedSampleSessionIds"]
        assert first["mutationPerformed"] is False
    finally:
        db.close()
