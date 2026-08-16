"""INT C-C1 proven legacy source backfill: exact evidence, dry-run, rollback, idempotency."""
from __future__ import annotations

from pathlib import Path

from app.db.session import get_sessionmaker
from app.models import AaAttendanceSession, AffairsAuditTrail
from app.modules.academic_affairs.services.academic_affairs_attendance_migration_inventory import (
    backfill_proven_legacy_admin_sources,
    inventory_legacy_attendance_sources,
)


def _attendance(*, tenant_id: int, date: str, slot: int, deleted: bool = False):
    return AaAttendanceSession(
        tenant_id=tenant_id,
        class_id=7101,
        teaching_task_id=None,
        occurrence_identity=None,
        source_type=None,
        source_reason="legacy-reason-sentinel",
        source_evidence="legacy-evidence-sentinel",
        course_name="INT C-C1 legacy",
        term_code="2026-1",
        teacher_key="INT-LEGACY-T1",
        session_date=date,
        slot_no=slot,
        session_type="常规",
        roster_json="[]",
        total_count=0,
        present_count=0,
        absent_count=0,
        status="DRAFT",
        is_deleted=deleted,
    )


def _audit(*, tenant_id: int, biz_id: int, detail: str):
    return AffairsAuditTrail(
        tenant_id=tenant_id,
        biz_type="AA_ATTENDANCE",
        biz_id=biz_id,
        action="CREATE",
        operator="legacy-writer",
        detail=detail,
    )


def test_backfill_dry_run_and_apply_do_not_hide_commit_or_guess_reason_evidence(db_mode):
    tenant = 1000000000000008931
    db = get_sessionmaker()()
    try:
        proven = _attendance(tenant_id=tenant, date="2026-04-11", slot=1)
        lookalike = _attendance(tenant_id=tenant, date="2026-04-12", slot=2)
        neighbor_only = _attendance(tenant_id=tenant, date="2026-04-13", slot=3)
        deleted = _attendance(tenant_id=tenant, date="2026-04-14", slot=4, deleted=True)
        db.add_all([proven, lookalike, neighbor_only, deleted])
        db.flush()
        db.add_all([
            _audit(
                tenant_id=tenant,
                biz_id=proven.id,
                detail="task=-;source=ADMIN_MANUAL;course=x;date=2026-04-11",
            ),
            _audit(
                tenant_id=tenant,
                biz_id=lookalike.id,
                detail="task=-;source=ADMIN_MANUAL_V2;course=x",
            ),
            _audit(
                tenant_id=tenant + 1,
                biz_id=neighbor_only.id,
                detail="task=-;source=ADMIN_MANUAL;course=x",
            ),
            _audit(
                tenant_id=tenant,
                biz_id=deleted.id,
                detail="source=ADMIN_MANUAL",
            ),
            _audit(
                tenant_id=tenant,
                biz_id=999999993,
                detail="source=ADMIN_MANUAL;course=orphan",
            ),
        ])
        db.commit()
        proven_id = int(proven.id)
        deleted_id = int(deleted.id)

        dry = backfill_proven_legacy_admin_sources(db, tenant, apply=False, sample_limit=20)
        assert dry["mode"] == "DRY_RUN"
        assert dry["provenCandidateRows"] == 2
        assert dry["mutationPerformed"] is False
        assert dry["commitPerformed"] is False
        assert sorted(dry["candidateSampleSessionIds"]) == sorted([proven_id, deleted_id])
        assert db.get(AaAttendanceSession, proven_id).source_type is None

        applied = backfill_proven_legacy_admin_sources(db, tenant, apply=True, sample_limit=20)
        assert applied["mode"] == "APPLY"
        assert applied["appliedRows"] == 2
        assert applied["mutationPerformed"] is True
        assert applied["commitPerformed"] is False
        assert applied["sourceReasonEvidenceMutated"] is False

        local = db.get(AaAttendanceSession, proven_id)
        assert local.source_type == "ADMIN_SPECIAL"
        assert local.source_reason == "legacy-reason-sentinel"
        assert local.source_evidence == "legacy-evidence-sentinel"

        # A second session must still see the committed pre-backfill state: helper never commits.
        observer = get_sessionmaker()()
        try:
            observed = observer.get(AaAttendanceSession, proven_id)
            assert observed.source_type is None
        finally:
            observer.close()

        db.rollback()
        db.expire_all()
        assert db.get(AaAttendanceSession, proven_id).source_type is None
        assert db.get(AaAttendanceSession, deleted_id).source_type is None
    finally:
        db.close()


def test_backfill_apply_is_idempotent_exact_token_scoped_audited_and_changes_read_truth(db_mode):
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as public
    from app.modules.academic_affairs.services import academic_affairs_warning_service as warning

    tenant = 1000000000000008941
    db = get_sessionmaker()()
    try:
        proven = _attendance(tenant_id=tenant, date="2026-05-11", slot=1)
        unresolved = _attendance(tenant_id=tenant, date="2026-05-12", slot=2)
        false_token = _attendance(tenant_id=tenant, date="2026-05-13", slot=3)
        db.add_all([proven, unresolved, false_token])
        db.flush()
        db.add_all([
            _audit(
                tenant_id=tenant,
                biz_id=proven.id,
                detail="task=-;source=ADMIN_MANUAL;course=legacy",
            ),
            _audit(
                tenant_id=tenant,
                biz_id=false_token.id,
                detail="task=-;source=ADMIN_MANUAL_IMPORT;course=not-proof",
            ),
        ])
        db.commit()
        proven_id = int(proven.id)
        unresolved_id = int(unresolved.id)
        false_id = int(false_token.id)

        before = inventory_legacy_attendance_sources(db, tenant, sample_limit=20)
        assert before["legacyRows"] == 3
        assert before["manualAuditMatchedRows"] == 1
        assert before["unresolvedRows"] == 2

        first = backfill_proven_legacy_admin_sources(
            db,
            tenant,
            apply=True,
            sample_limit=20,
            operator="int-c1-test",
        )
        assert first["appliedRows"] == 1
        assert first["after"]["legacyRows"] == 2
        assert first["after"]["manualAuditMatchedRows"] == 0
        assert first["after"]["unresolvedRows"] == 2
        db.commit()

        db.expire_all()
        stored = db.get(AaAttendanceSession, proven_id)
        assert stored.source_type == "ADMIN_SPECIAL"
        assert stored.session_type == "常规"
        assert stored.source_reason == "legacy-reason-sentinel"
        assert stored.source_evidence == "legacy-evidence-sentinel"
        assert db.get(AaAttendanceSession, unresolved_id).source_type is None
        assert db.get(AaAttendanceSession, false_id).source_type is None

        # Persisted source Authority wins immediately over the old session_type marker:
        # backfilled special rows leave normal classroom statistics/warnings and enter the
        # explicit ADMIN_SPECIAL view without rewriting historical session_type.
        default_ids = {
            int(row.id)
            for row in db.query(AaAttendanceSession).filter(
                AaAttendanceSession.tenant_id == tenant,
                public._stats_session_type_condition(AaAttendanceSession),
            ).all()
        }
        special_ids = {
            int(row.id)
            for row in db.query(AaAttendanceSession).filter(
                AaAttendanceSession.tenant_id == tenant,
                public._stats_session_type_condition(AaAttendanceSession, "ADMIN_SPECIAL"),
            ).all()
        }
        warning_ids = {
            int(row.id)
            for row in db.query(AaAttendanceSession).filter(
                AaAttendanceSession.tenant_id == tenant,
                warning._formal_attendance_session_condition(AaAttendanceSession),
            ).all()
        }
        assert proven_id not in default_ids
        assert proven_id in special_ids
        assert proven_id not in warning_ids
        assert unresolved_id in default_ids
        assert false_id in default_ids

        audit = (
            db.query(AffairsAuditTrail)
            .filter(
                AffairsAuditTrail.tenant_id == tenant,
                AffairsAuditTrail.biz_type == "AA_ATTENDANCE_MIGRATION",
                AffairsAuditTrail.action == "BACKFILL_SOURCE_TYPE",
            )
            .one()
        )
        assert audit.operator == "int-c1-test"
        assert "updated=1" in str(audit.detail or "")
        assert "source_reason=UNCHANGED" in str(audit.detail or "")
        assert "source_evidence=UNCHANGED" in str(audit.detail or "")

        second = backfill_proven_legacy_admin_sources(db, tenant, apply=True, sample_limit=20)
        assert second["appliedRows"] == 0
        assert second["mutationPerformed"] is False
        db.rollback()

        script = Path("scripts/academic_int_c1_attendance_backfill.py").read_text(encoding="utf-8")
        assert 'parser.add_argument("--apply", action="store_true")' in script
        assert "apply=bool(args.apply)" in script
        assert "db.commit()" in script
        assert "if args.apply:" in script
    finally:
        db.close()
