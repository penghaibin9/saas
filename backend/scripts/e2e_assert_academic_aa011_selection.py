"""Read-only MySQL truth seal for AA-011 Selection concurrency acceptance."""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.models import (
    AaSelectionBatch,
    AaSelectionCourse,
    AaSelectionRecord,
    AffairsAuditTrail,
    StudentProfile,
)
from app.modules.academic_affairs.services.academic_affairs_teaching_roster_service import (
    resolve_teaching_task_roster,
)

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "e2e" / "academic-aa011-runtime.json"
OUT = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_aa011_db_evidence.json"


def main() -> int:
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    tenant_id = int(runtime["tenantId"])
    set_tenant({"tenantId": str(tenant_id)})
    db = get_sessionmaker()()
    try:
        batch = db.scalars(select(AaSelectionBatch).where(
            AaSelectionBatch.id == int(runtime["batchId"]),
            AaSelectionBatch.tenant_id == tenant_id,
            AaSelectionBatch.is_deleted.is_(False),
        )).first()
        assert batch, "AA-011 browser-created batch missing"
        assert batch.status == "LOCKED", f"batch must be LOCKED, got {batch.status}"
        assert batch.locked_at is not None, "LOCKED batch missing locked_at"

        race = db.scalars(select(AaSelectionCourse).where(
            AaSelectionCourse.id == int(runtime["raceSelectionCourseId"]),
            AaSelectionCourse.tenant_id == tenant_id,
            AaSelectionCourse.is_deleted.is_(False),
        )).first()
        conflict = db.scalars(select(AaSelectionCourse).where(
            AaSelectionCourse.id == int(runtime["conflictSelectionCourseId"]),
            AaSelectionCourse.tenant_id == tenant_id,
            AaSelectionCourse.is_deleted.is_(False),
        )).first()
        assert race and conflict, "AA-011 browser-created course offerings missing"
        assert int(race.capacity) == 1, f"race capacity must be 1, got {race.capacity}"
        assert int(race.selected_count or 0) == 1, f"last-seat race oversold/drifted: {race.selected_count}"
        assert race.status == "OPEN", f"winning course must remain OPEN, got {race.status}"
        assert conflict.status == "COURSE_CANCELLED", f"negative conflict course must be cancelled before lock, got {conflict.status}"
        assert int(conflict.selected_count or 0) == 0, "time-conflict course unexpectedly consumed capacity"

        profiles = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.student_no.in_([runtime["mainStudentNo"], runtime["fillerStudentNo"]]),
            StudentProfile.is_deleted.is_(False),
        )).all()
        by_no = {str(row.student_no): row for row in profiles}
        main_student = by_no.get(runtime["mainStudentNo"])
        filler_student = by_no.get(runtime["fillerStudentNo"])
        assert main_student and filler_student, "AA-011 student profiles missing"

        records = db.scalars(select(AaSelectionRecord).where(
            AaSelectionRecord.tenant_id == tenant_id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.selection_course_id == race.id,
            AaSelectionRecord.student_id.in_([main_student.id, filler_student.id]),
            AaSelectionRecord.is_deleted.is_(False),
        ).order_by(AaSelectionRecord.student_id.asc())).all()
        assert len(records) == 2, f"expected two unique race records, got {len(records)}"
        by_student = {int(row.student_id): row for row in records}
        assert len(by_student) == 2, "duplicate selection record escaped unique business key"
        main_record = by_student[int(main_student.id)]
        filler_record = by_student[int(filler_student.id)]
        assert main_record.status == "LOCKED", f"main final record must be LOCKED, got {main_record.status}"
        assert filler_record.status == "DROPPED", f"filler final record must be DROPPED, got {filler_record.status}"
        assert main_record.enrolled_at is not None, "main LOCKED record missing enrolled_at"
        assert filler_record.dropped_at is not None, "filler DROPPED record missing dropped_at"

        roster = resolve_teaching_task_roster(db, int(runtime["raceTaskId"]))
        assert roster.get("ready") is True, roster
        assert roster.get("source") == "SELECTION_LOCKED", roster
        roster_ids = sorted(int(value) for value in roster.get("studentIds") or [])
        assert roster_ids == [int(main_student.id)], f"formal teaching roster drift: {roster_ids}"

        audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tenant_id,
            AffairsAuditTrail.biz_type == "AA_SELECTION",
            AffairsAuditTrail.is_deleted.is_(False),
        ).order_by(AffairsAuditTrail.id.asc())).all()
        actions = [str(row.action or "") for row in audits]
        assert "SELECTION_ENROLL" in actions, f"selection enroll audit missing: {actions}"
        assert "SELECTION_DROP" in actions, f"selection drop audit missing: {actions}"
        assert "SELECTION_LOCK" in actions, f"selection lock audit missing: {actions}"

        evidence = {
            "sealStatus": "PASS",
            "productSha": runtime.get("productSha"),
            "tenantId": tenant_id,
            "batch": {
                "id": int(batch.id),
                "name": batch.batch_name,
                "status": batch.status,
                "lockedAt": batch.locked_at,
            },
            "raceCourse": {
                "id": int(race.id),
                "courseName": race.course_name,
                "capacity": int(race.capacity),
                "selectedCount": int(race.selected_count or 0),
                "status": race.status,
            },
            "conflictCourse": {
                "id": int(conflict.id),
                "courseName": conflict.course_name,
                "selectedCount": int(conflict.selected_count or 0),
                "status": conflict.status,
            },
            "records": [
                {
                    "studentNo": row.student_no,
                    "studentId": int(row.student_id),
                    "status": row.status,
                    "reEnroll": bool(row.re_enroll),
                    "enrolledAt": row.enrolled_at,
                    "droppedAt": row.dropped_at,
                }
                for row in records
            ],
            "initialWinner": runtime.get("initialWinner"),
            "teachingRoster": {
                "ready": roster.get("ready"),
                "source": roster.get("source"),
                "studentIds": roster_ids,
                "batchIds": roster.get("batchIds"),
                "note": roster.get("note"),
            },
            "auditActions": actions,
            "foreignSelectionCourseId": runtime.get("foreignSelectionCourseId"),
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        db.close()
        set_tenant(None)


if __name__ == "__main__":
    raise SystemExit(main())
