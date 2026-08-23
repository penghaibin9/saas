"""Seed only prerequisite facts for the Academic C grade Browser-First acceptance journey.

The grade business writes themselves MUST be performed by Playwright through the real UI.
This wrapper deliberately reuses the already-proven C-W2 authoritative teaching-task / teaching-class /
LOCKED-roster fixture and swaps only the isolated academic-affairs E2E identities.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

import e2e_seed_academic_c_teacher_today as base

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_c_grade_browser_state.local.json"
FIXTURE_PATH = ROOT / "e2e" / "academic-c-grade-browser-fixture.json"

TENANT = "sandbox-school"
PASSWORD = "E2eTest@2026"
TEACHER = "e2e_aa_teacher_a"
OTHER_TEACHER = "e2e_aa_teacher_b"
COLLEGE_REVIEWER = "e2e_aa_college_a"
GRADE_ADMIN = "e2e_aa_grade"
STUDENTS = ("E2EAA20260001", "E2EAA20260002")


def _resolve_formal_roster(state: dict) -> dict:
    """Resolve the canonical teaching-class/LOCKED-roster facts created by the base seed.

    The Teacher-Today fixture intentionally exposes only the fields that its own browser journey consumes.
    Grade acceptance must not depend on that private JSON surface growing new keys. Instead, derive the
    formal roster from the database by the stable tenant + teaching_task identity and fail closed unless
    exactly one ACTIVE teaching class owns a LOCKED current roster with the expected two students.
    """
    tenant_id = int(state.get("tenantId") or 0)
    task_id = int(state.get("teachingTaskId") or 0)
    if not tenant_id or not task_id:
        raise SystemExit("grade browser cannot resolve formal roster without tenantId + teachingTaskId")

    db = base.get_sessionmaker()()
    try:
        teaching_classes = db.scalars(select(base.AaTeachingClass).where(
            base.AaTeachingClass.tenant_id == tenant_id,
            base.AaTeachingClass.teaching_task_id == task_id,
            base.AaTeachingClass.is_deleted.is_(False),
            base.AaTeachingClass.status == "ACTIVE",
        )).all()
        if len(teaching_classes) != 1:
            raise SystemExit(
                f"grade browser requires exactly one ACTIVE teaching class for task {task_id}; "
                f"got {len(teaching_classes)}"
            )
        teaching_class = teaching_classes[0]
        roster_version_id = int(teaching_class.current_roster_version_id or 0)
        if teaching_class.roster_status != "LOCKED" or not roster_version_id:
            raise SystemExit("grade browser formal teaching class does not own a LOCKED current roster")
        roster_version = db.get(base.AaTeachingClassRosterVersion, roster_version_id)
        if (
            not roster_version
            or roster_version.tenant_id != tenant_id
            or int(roster_version.teaching_class_id) != int(teaching_class.id)
            or roster_version.status != "LOCKED"
        ):
            raise SystemExit("grade browser current roster version is missing, cross-tenant, or not LOCKED")
        members = db.scalars(select(base.AaTeachingClassMember).where(
            base.AaTeachingClassMember.tenant_id == tenant_id,
            base.AaTeachingClassMember.teaching_class_id == teaching_class.id,
            base.AaTeachingClassMember.roster_version_id == roster_version_id,
            base.AaTeachingClassMember.status == "ACTIVE",
            base.AaTeachingClassMember.is_deleted.is_(False),
        ).order_by(base.AaTeachingClassMember.student_id)).all()
        member_ids = [int(row.student_id) for row in members]
        if len(member_ids) != len(STUDENTS) or int(roster_version.member_count or 0) != len(member_ids):
            raise SystemExit(
                "grade browser LOCKED roster member count mismatch: "
                f"version={roster_version.member_count} rows={len(member_ids)} expected={len(STUDENTS)}"
            )
        return {
            "teachingClassId": int(teaching_class.id),
            "rosterVersionId": roster_version_id,
            "studentIds": member_ids,
            "rosterHash": roster_version.roster_hash,
        }
    finally:
        db.close()


def main() -> int:
    # Reuse the production-shaped prerequisite seed; never create a GradeTask here.
    base.TEACHER_LOGIN = TEACHER
    base.OTHER_TEACHER_LOGIN = OTHER_TEACHER
    base.STUDENT_NOS = STUDENTS
    base.STATE_PATH = STATE_PATH
    rc = base.seed()
    if rc:
        return int(rc)

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.update(_resolve_formal_roster(state))
    required = (
        "tenantId",
        "termId",
        "teachingTaskId",
        "teachingClassId",
        "rosterVersionId",
        "courseName",
    )
    missing = [key for key in required if not state.get(key)]
    if missing:
        raise SystemExit(f"grade browser prerequisite state missing: {missing}")

    fixture = {
        "tenant": TENANT,
        "password": PASSWORD,
        "teacher": TEACHER,
        "otherTeacher": OTHER_TEACHER,
        "collegeReviewer": COLLEGE_REVIEWER,
        "gradeAdmin": GRADE_ADMIN,
        "students": list(STUDENTS),
        "tenantId": state["tenantId"],
        "termId": state["termId"],
        "teachingTaskId": state["teachingTaskId"],
        "teachingClassId": state["teachingClassId"],
        "courseName": state["courseName"],
        "teacherName": state.get("teacherName"),
        "studentIds": state.get("studentIds") or [],
        "rosterVersionId": state.get("rosterVersionId"),
        "rosterHash": state.get("rosterHash"),
        "runKey": state.get("runKey"),
    }
    FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(fixture, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
