"""Seed only prerequisite facts for the Academic C grade Browser-First acceptance journey.

The grade business writes themselves MUST be performed by Playwright through the real UI.
This wrapper deliberately reuses the already-proven C-W2 authoritative teaching-task / teaching-class /
LOCKED-roster fixture and swaps only the isolated academic-affairs E2E identities.
"""
from __future__ import annotations

import json
from pathlib import Path

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
    required = ("tenantId", "termId", "teachingTaskId", "teachingClassId", "courseName")
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
        "runKey": state.get("runKey"),
    }
    FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(fixture, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
