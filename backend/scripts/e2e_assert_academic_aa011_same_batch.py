"""Direct-MySQL seal for the exact Staff-created AA-011 browser batch."""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord, StudentProfile

E2E_DIR = Path(__file__).resolve().parents[2] / "e2e"
STAFF_FIXTURE = E2E_DIR / "academic-aa011-staff-browser-fixture.json"
STUDENT_OUTCOME = E2E_DIR / "academic-aa011-student-browser-outcome.json"
SEED_FIXTURE = E2E_DIR / "academic-b-w5-fixture.json"
SEAL_OUTPUT = E2E_DIR / "academic-aa011-same-batch-mysql-seal.json"
EXPECTED_TENANT_ID = 1000000000000000007


def _load(path: Path) -> dict:
    if not path.is_file():
        raise AssertionError(f"required AA-011 evidence file missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    staff = _load(STAFF_FIXTURE)
    browser = _load(STUDENT_OUTCOME)
    seed = _load(SEED_FIXTURE)

    batch_id = int(staff["batchId"])
    pc_selection_course_id = int(staff["pcSelectionCourseId"])
    mini_selection_course_id = int(staff["miniSelectionCourseId"])
    student_no = str(seed["mainStudentNo"])

    assert str(browser["batchId"]) == str(batch_id), "Student browser did not finish on the Staff-created batch"
    assert str(browser["pcSelectionCourseId"]) == str(pc_selection_course_id)
    assert str(browser["miniSelectionCourseId"]) == str(mini_selection_course_id)
    assert browser["pcFinalStatus"] == "DROPPED"
    assert browser["miniFinalStatus"] == "SELECTED"

    db = get_sessionmaker()()
    try:
        bind = db.get_bind()
        assert bind.dialect.name == "mysql", f"AA-011 release seal requires MySQL, got {bind.dialect.name}"

        batch = db.scalar(select(AaSelectionBatch).where(AaSelectionBatch.id == batch_id))
        assert batch is not None, f"Staff-created batch {batch_id} missing from MySQL"
        assert int(batch.tenant_id) == EXPECTED_TENANT_ID
        assert str(batch.batch_name) == str(staff["batchName"])
        assert str(batch.term_id) == str(staff["termId"])
        assert str(batch.status) == "OPEN", f"expected same browser batch OPEN, got {batch.status}"

        courses = db.scalars(
            select(AaSelectionCourse).where(
                AaSelectionCourse.tenant_id == EXPECTED_TENANT_ID,
                AaSelectionCourse.batch_id == batch_id,
                AaSelectionCourse.id.in_([pc_selection_course_id, mini_selection_course_id]),
                AaSelectionCourse.is_deleted.is_(False),
            )
        ).all()
        by_course_id = {int(row.id): row for row in courses}
        assert set(by_course_id) == {pc_selection_course_id, mini_selection_course_id}, (
            "Staff-created selectionCourseIds do not both belong to the same MySQL batch"
        )
        pc_course = by_course_id[pc_selection_course_id]
        mini_course = by_course_id[mini_selection_course_id]
        assert int(pc_course.batch_id) == batch_id and int(mini_course.batch_id) == batch_id
        assert str(pc_course.status) == "OPEN" and str(mini_course.status) == "OPEN"

        student = db.scalar(
            select(StudentProfile).where(
                StudentProfile.tenant_id == EXPECTED_TENANT_ID,
                StudentProfile.student_no == student_no,
                StudentProfile.is_deleted.is_(False),
            )
        )
        assert student is not None, f"official E2E student {student_no} missing"

        records = db.scalars(
            select(AaSelectionRecord).where(
                AaSelectionRecord.tenant_id == EXPECTED_TENANT_ID,
                AaSelectionRecord.batch_id == batch_id,
                AaSelectionRecord.student_id == int(student.id),
                AaSelectionRecord.selection_course_id.in_([pc_selection_course_id, mini_selection_course_id]),
                AaSelectionRecord.is_deleted.is_(False),
            )
        ).all()
        by_selection_course_id = {int(row.selection_course_id): row for row in records}
        assert set(by_selection_course_id) == {pc_selection_course_id, mini_selection_course_id}, (
            "same-batch Student PC/Mini records are incomplete in MySQL"
        )
        pc_record = by_selection_course_id[pc_selection_course_id]
        mini_record = by_selection_course_id[mini_selection_course_id]
        assert str(pc_record.status) == "DROPPED", f"PC course final record must be DROPPED, got {pc_record.status}"
        assert str(mini_record.status) == "SELECTED", f"Mini course final record must be SELECTED, got {mini_record.status}"
        assert str(pc_record.student_no) == student_no
        assert str(mini_record.student_no) == student_no
        assert int(pc_course.selected_count) == 0, f"dropped PC course selected_count must be 0, got {pc_course.selected_count}"
        assert int(mini_course.selected_count) == 1, f"selected Mini course selected_count must be 1, got {mini_course.selected_count}"

        seal = {
            "dialect": bind.dialect.name,
            "tenantId": str(EXPECTED_TENANT_ID),
            "batchId": str(batch_id),
            "batchName": str(batch.batch_name),
            "termId": str(batch.term_id),
            "batchStatus": str(batch.status),
            "studentNo": student_no,
            "pcSelectionCourseId": str(pc_selection_course_id),
            "pcRecordStatus": str(pc_record.status),
            "pcSelectedCount": int(pc_course.selected_count),
            "miniSelectionCourseId": str(mini_selection_course_id),
            "miniRecordStatus": str(mini_record.status),
            "miniSelectedCount": int(mini_course.selected_count),
        }
        SEAL_OUTPUT.write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[AA-011 same-batch MySQL seal] PASS", json.dumps(seal, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
