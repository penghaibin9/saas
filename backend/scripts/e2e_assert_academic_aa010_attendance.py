"""Direct-MySQL final seal for AA-010 classroom attendance Gold Deep.

This is audit-only verification. It never mutates business rows.
"""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaAttendanceSession,
    AcademicWarning,
    AffairsAuditTrail,
    StudentProfile,
)

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "backend" / "tmp" / "e2e_academic_c_teacher_today_state.local.json"
OUTCOME_PATH = ROOT / "e2e" / "academic-aa010-browser-outcome.json"
SEAL_PATH = ROOT / "e2e" / "academic-aa010-mysql-seal.json"


def _load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"missing AA-010 evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    state = _load(STATE_PATH)
    outcome = _load(OUTCOME_PATH)
    tenant_id = int(state["tenantId"])
    task_id = int(state["teachingTaskId"])
    session_ids = [int(value) for value in outcome.get("sessionIds") or []]
    dates = list(outcome.get("sessionDates") or [])
    _assert(len(session_ids) == 3 and len(set(session_ids)) == 3, "AA-010 must seal exactly three distinct browser-created sessions")
    _assert(len(dates) == 3 and len(set(dates)) == 3, "AA-010 must seal three distinct formal dates")

    db = get_sessionmaker()()
    try:
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.student_no == state["studentNo"],
            StudentProfile.is_deleted.is_(False),
        )).first()
        _assert(student is not None, "AA-010 target student missing")

        sessions = db.scalars(select(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == tenant_id,
            AaAttendanceSession.id.in_(session_ids),
            AaAttendanceSession.is_deleted.is_(False),
        ).order_by(AaAttendanceSession.id)).all()
        _assert(len(sessions) == 3, f"AA-010 expected 3 attendance rows, got {len(sessions)}")

        occurrences = set()
        sealed_sessions = []
        for row in sessions:
            _assert(row.status == "SUBMITTED", f"session {row.id} not SUBMITTED: {row.status}")
            _assert(int(row.teaching_task_id or 0) == task_id, f"session {row.id} lost teaching_task provenance")
            _assert(str(row.source_type or "").upper() == "FORMAL_TEACHING", f"session {row.id} source is not FORMAL_TEACHING")
            _assert(row.occurrence_identity, f"session {row.id} missing occurrence_identity")
            _assert(row.session_date in dates, f"session {row.id} unexpected date {row.session_date}")
            occurrences.add(str(row.occurrence_identity))
            roster = json.loads(row.roster_json or "[]")
            target = next((item for item in roster if str(item.get("studentNo") or "") == state["studentNo"]), None)
            _assert(target is not None, f"session {row.id} roster lost target student")
            _assert(str(target.get("status") or "").upper() == "ABSENT", f"session {row.id} target final status is not ABSENT")
            _assert(int(row.absent_count or 0) == 1, f"session {row.id} absent_count != 1")
            _assert(int(row.total_count or 0) >= 2, f"session {row.id} did not use the locked formal roster")
            sealed_sessions.append({
                "sessionId": str(row.id),
                "date": row.session_date,
                "status": row.status,
                "sourceType": row.source_type,
                "occurrenceIdentity": row.occurrence_identity,
                "absentCount": int(row.absent_count or 0),
                "totalCount": int(row.total_count or 0),
                "targetStudentStatus": target.get("status"),
            })
        _assert(len(occurrences) == 3, "AA-010 occurrence identities are not unique across the three formal dates")

        attendance_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type == "AA_ATTENDANCE",
            AffairsAuditTrail.biz_id.in_(session_ids),
        )).all()
        creates = [a for a in attendance_audits if str(a.action or "").upper() == "CREATE"]
        submits = [a for a in attendance_audits if str(a.action or "").upper() == "SUBMIT"]
        _assert(len(creates) == 3, f"AA-010 attendance CREATE audit count != 3: {len(creates)}")
        _assert(len(submits) == 3, f"AA-010 attendance SUBMIT audit count != 3: {len(submits)}")
        for audit in creates:
            detail = str(audit.detail or "")
            _assert("source=" in detail and "occurrence=" in detail and "rosterVersion=" in detail,
                    f"AA-010 attendance CREATE audit {audit.id} lacks provenance detail")

        warnings = db.scalars(select(AcademicWarning).where(
            AcademicWarning.tenant_id == tenant_id,
            AcademicWarning.source_code == "ATTENDANCE_ABSENT",
            AcademicWarning.is_deleted.is_(False),
        )).all()
        _assert(len(warnings) == 1, f"AA-010 warning dedup failed: expected 1 ATTENDANCE_ABSENT, got {len(warnings)}")
        warning = warnings[0]
        _assert(str(warning.rule_code or "") == "ABSENT_EXCESS", f"AA-010 wrong attendance warning rule: {warning.rule_code}")
        _assert("旷课 3 次" in str(warning.reason or ""), f"AA-010 wrong warning reason: {warning.reason}")
        _assert(str(warning.status or "").upper() == "CLOSED", f"AA-010 teacher follow-up did not close warning: {warning.status}")
        _assert(outcome.get("warningCloseNote") in str(warning.close_result or ""), "AA-010 warning close result did not persist")

        scan_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type == "ACAD_WARNING_SCAN",
            AffairsAuditTrail.action == "SCAN_ATTENDANCE_ABSENT",
        )).all()
        _assert(len(scan_audits) >= 2, f"AA-010 expected two idempotency scan audits, got {len(scan_audits)}")
        warning_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type == "ACAD_WARNING",
            AffairsAuditTrail.biz_id == int(warning.id),
        )).all()
        _assert(any(str(a.action or "").upper() in {"CLOSE", "CLOSED"} for a in warning_audits),
                "AA-010 warning close action missing from audit trail")

        first_scan = outcome.get("firstScan") or {}
        second_scan = outcome.get("secondScan") or {}
        _assert(int(first_scan.get("threshold") or 0) == 3, "AA-010 first scan threshold was not 3")
        _assert(int(first_scan.get("created") or 0) == 1, "AA-010 first scan did not create exactly one warning")
        _assert(int(second_scan.get("created") or 0) == 0, "AA-010 repeated scan created a duplicate warning")

        seal = {
            "tenantId": str(tenant_id),
            "teachingTaskId": str(task_id),
            "studentNo": state["studentNo"],
            "sessions": sealed_sessions,
            "attendanceAudit": {"create": len(creates), "submit": len(submits)},
            "warning": {
                "warningId": str(warning.id),
                "sourceCode": warning.source_code,
                "ruleCode": warning.rule_code,
                "reason": warning.reason,
                "status": warning.status,
                "closeResult": warning.close_result,
                "scanAuditCount": len(scan_audits),
                "warningAuditCount": len(warning_audits),
            },
            "dedup": {
                "firstCreated": int(first_scan.get("created") or 0),
                "secondCreated": int(second_scan.get("created") or 0),
                "warningRows": len(warnings),
            },
        }
        SEAL_PATH.write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(seal, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
