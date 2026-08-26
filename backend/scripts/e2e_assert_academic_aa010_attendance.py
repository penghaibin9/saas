"""Direct-MySQL final seal for AA-010 classroom attendance Gold Deep.

Audit-only verification: never mutates business rows.
"""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import AaAttendanceSession, AcademicWarning, AffairsAuditTrail, StudentProfile

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "backend" / "tmp" / "e2e_academic_c_teacher_today_state.local.json"
OUTCOME_PATH = ROOT / "e2e" / "academic-aa010-browser-outcome.json"
SEAL_PATH = ROOT / "e2e" / "academic-aa010-mysql-seal.json"
DEBUG_PATH = ROOT / "e2e" / "runtime-logs" / "aa010-mysql-debug.json"


def _load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"missing AA-010 evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_debug(payload: dict) -> None:
    """Persist read-only DB observations before assertions so failed seals remain diagnosable."""
    DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEBUG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    state = _load(STATE_PATH)
    outcome = _load(OUTCOME_PATH)
    tenant_id = int(state["tenantId"])
    task_id = int(state["teachingTaskId"])
    session_ids = [int(value) for value in outcome.get("sessionIds") or []]
    dates = list(outcome.get("sessionDates") or [])
    _assert(len(session_ids) == 3 and len(set(session_ids)) == 3,
            "AA-010 must seal exactly three distinct browser-created sessions")
    _assert(len(dates) == 3 and len(set(dates)) == 3,
            "AA-010 must seal three distinct formal dates")

    debug = {
        "tenantId": str(tenant_id),
        "teachingTaskId": str(task_id),
        "sessionIds": [str(value) for value in session_ids],
        "sessionDates": dates,
        "browserOutcome": {
            "firstScan": outcome.get("firstScan") or {},
            "secondScan": outcome.get("secondScan") or {},
            "warningCloseNote": outcome.get("warningCloseNote"),
        },
    }
    _write_debug(debug)

    db = get_sessionmaker()()
    try:
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.student_no == state["studentNo"],
            StudentProfile.is_deleted.is_(False),
        )).first()
        debug["student"] = (
            {"id": str(student.id), "studentNo": student.student_no, "realName": student.real_name}
            if student is not None else None
        )
        _write_debug(debug)
        _assert(student is not None, "AA-010 target student missing")

        sessions = db.scalars(select(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == tenant_id,
            AaAttendanceSession.id.in_(session_ids),
            AaAttendanceSession.is_deleted.is_(False),
        ).order_by(AaAttendanceSession.id)).all()
        debug["sessions"] = [{
            "sessionId": str(row.id),
            "status": row.status,
            "teachingTaskId": str(row.teaching_task_id or ""),
            "sourceType": row.source_type,
            "occurrenceIdentity": row.occurrence_identity,
            "sessionDate": row.session_date,
            "absentCount": int(row.absent_count or 0),
            "totalCount": int(row.total_count or 0),
            "rosterJson": row.roster_json,
        } for row in sessions]
        _write_debug(debug)
        _assert(len(sessions) == 3, f"AA-010 expected 3 attendance rows, got {len(sessions)}")

        occurrences = set()
        sealed_sessions = []
        for row in sessions:
            _assert(row.status == "SUBMITTED", f"session {row.id} not SUBMITTED: {row.status}")
            _assert(int(row.teaching_task_id or 0) == task_id,
                    f"session {row.id} lost teaching_task provenance")
            _assert(str(row.source_type or "").upper() == "FORMAL_TEACHING",
                    f"session {row.id} source is not FORMAL_TEACHING")
            _assert(row.occurrence_identity, f"session {row.id} missing occurrence_identity")
            _assert(row.session_date in dates, f"session {row.id} unexpected date {row.session_date}")
            occurrences.add(str(row.occurrence_identity))

            roster = json.loads(row.roster_json or "[]")
            target = next(
                (item for item in roster if str(item.get("studentNo") or "") == state["studentNo"]),
                None,
            )
            _assert(target is not None, f"session {row.id} roster lost target student")
            _assert(str(target.get("status") or "").upper() == "ABSENT",
                    f"session {row.id} target final status is not ABSENT")
            _assert(int(row.absent_count or 0) == 1,
                    f"session {row.id} absent_count != 1")
            _assert(int(row.total_count or 0) >= 2,
                    f"session {row.id} did not use the locked formal roster")
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
        _assert(len(occurrences) == 3,
                "AA-010 occurrence identities are not unique across the three formal dates")

        attendance_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type == "AA_ATTENDANCE",
            AffairsAuditTrail.biz_id.in_(session_ids),
        ).order_by(AffairsAuditTrail.id)).all()
        creates = [row for row in attendance_audits if str(row.action or "").upper() == "CREATE"]
        marks = [row for row in attendance_audits if str(row.action or "").upper() == "MARK"]
        submits = [row for row in attendance_audits if str(row.action or "").upper() == "SUBMIT"]
        debug["attendanceAudits"] = [{
            "id": str(row.id),
            "bizId": str(row.biz_id or ""),
            "action": row.action,
            "operator": row.operator,
            "detail": row.detail,
        } for row in attendance_audits]
        debug["attendanceAuditCounts"] = {
            "create": len(creates), "mark": len(marks), "submit": len(submits),
        }
        _write_debug(debug)
        _assert(len(creates) == 3, f"AA-010 attendance CREATE audit count != 3: {len(creates)}")
        _assert(len(submits) == 3, f"AA-010 attendance SUBMIT audit count != 3: {len(submits)}")
        for audit in creates:
            detail = str(audit.detail or "")
            _assert("source=" in detail and "occurrence=" in detail and "rosterVersion=" in detail,
                    f"AA-010 attendance CREATE audit {audit.id} lacks provenance detail")

        # Gold Deep requires point-status correction before/after history, not only final roster truth.
        _assert(len(marks) == 5,
                f"AA-010 expected 5 real MARK audit rows (3 correction clicks + 2 absences), got {len(marks)}")
        first_marks = [row for row in marks if int(row.biz_id or 0) == session_ids[0]]
        debug["firstSessionMarkCount"] = len(first_marks)
        _write_debug(debug)
        _assert(len(first_marks) == 3,
                f"AA-010 first session correction history must have 3 MARK rows, got {len(first_marks)}")
        expected_transitions = [
            ("before=PRESENT", "after=ABSENT"),
            ("before=ABSENT", "after=PRESENT"),
            ("before=PRESENT", "after=ABSENT"),
        ]
        for audit, (before, after) in zip(first_marks, expected_transitions):
            detail = str(audit.detail or "")
            _assert(f"student={student.id}" in detail and before in detail and after in detail,
                    f"AA-010 correction audit {audit.id} lacks student/before/after: {detail}")

        warnings = db.scalars(select(AcademicWarning).where(
            AcademicWarning.tenant_id == tenant_id,
            AcademicWarning.source_code == "ATTENDANCE_ABSENT",
            AcademicWarning.is_deleted.is_(False),
        )).all()
        debug["warnings"] = [{
            "id": str(row.id),
            "acadStudentId": str(row.acad_student_id or ""),
            "sourceCode": row.source_code,
            "ruleCode": row.rule_code,
            "reason": row.reason,
            "status": row.status,
            "closeResult": row.close_result,
        } for row in warnings]
        _write_debug(debug)
        _assert(len(warnings) == 1,
                f"AA-010 warning dedup failed: expected 1 ATTENDANCE_ABSENT, got {len(warnings)}")
        warning = warnings[0]
        _assert(str(warning.rule_code or "") == "ABSENT_EXCESS",
                f"AA-010 wrong attendance warning rule: {warning.rule_code}")
        _assert("旷课 3 次" in str(warning.reason or ""),
                f"AA-010 wrong warning reason: {warning.reason}")
        _assert(str(warning.status or "").upper() == "CLOSED",
                f"AA-010 teacher follow-up did not close warning: {warning.status}")
        _assert(outcome.get("warningCloseNote") in str(warning.close_result or ""),
                "AA-010 warning close result did not persist")

        # submit_session auto-scans after each real submit; Staff PC then scans twice to prove idempotency.
        scan_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type == "ACAD_WARNING_SCAN",
            AffairsAuditTrail.action == "SCAN_ATTENDANCE_ABSENT",
        ).order_by(AffairsAuditTrail.id)).all()
        debug["scanAudits"] = [{
            "id": str(row.id),
            "bizId": str(row.biz_id or ""),
            "action": row.action,
            "operator": row.operator,
            "detail": row.detail,
        } for row in scan_audits]
        debug["scanAuditCount"] = len(scan_audits)
        _write_debug(debug)
        _assert(len(scan_audits) >= 5,
                f"AA-010 expected 3 submit auto-scans + 2 Staff scans, got {len(scan_audits)}")
        _assert(any("created=1" in str(row.detail or "") for row in scan_audits),
                "AA-010 automatic submit scan never recorded created=1 at threshold")

        warning_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type == "ACAD_WARNING",
            AffairsAuditTrail.biz_id == int(warning.id),
        ).order_by(AffairsAuditTrail.id)).all()
        debug["warningAudits"] = [{
            "id": str(row.id),
            "bizId": str(row.biz_id or ""),
            "action": row.action,
            "operator": row.operator,
            "detail": row.detail,
        } for row in warning_audits]
        _write_debug(debug)
        _assert(any(str(row.action or "").upper() == "CLOSE" for row in warning_audits),
                "AA-010 warning close action missing from audit trail")

        first_scan = outcome.get("firstScan") or {}
        second_scan = outcome.get("secondScan") or {}
        _assert(int(first_scan.get("threshold") or 0) == 3,
                "AA-010 Staff scan threshold was not 3")
        _assert(int(first_scan.get("created") or 0) == 0,
                "AA-010 Staff first scan created a duplicate warning")
        _assert(int(second_scan.get("created") or 0) == 0,
                "AA-010 Staff repeated scan created a duplicate warning")

        seal = {
            "tenantId": str(tenant_id),
            "teachingTaskId": str(task_id),
            "studentNo": state["studentNo"],
            "sessions": sealed_sessions,
            "attendanceAudit": {
                "create": len(creates),
                "mark": len(marks),
                "submit": len(submits),
                "firstSessionCorrectionMarks": len(first_marks),
            },
            "warning": {
                "warningId": str(warning.id),
                "sourceCode": warning.source_code,
                "ruleCode": warning.rule_code,
                "reason": warning.reason,
                "status": warning.status,
                "closeResult": warning.close_result,
                "scanAuditCount": len(scan_audits),
                "autoScanCreatedOne": any("created=1" in str(row.detail or "") for row in scan_audits),
                "warningAuditCount": len(warning_audits),
            },
            "dedup": {
                "staffFirstCreated": int(first_scan.get("created") or 0),
                "staffSecondCreated": int(second_scan.get("created") or 0),
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
