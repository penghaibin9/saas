"""B-W6-1 Selection FCFS peak-load contracts on real MySQL.

Only the canonical student_enroll command is exercised.  The tests deliberately keep the
production SQLAlchemy pool and nested authority reads unchanged so lock/pool starvation is
visible instead of hidden by a test-only oversized pool.

Contracts:
- 128 application contenders race for one FCFS seat: exactly one succeeds, no oversell,
  selected_count and active SelectionRecord agree exactly.
- 1000 enroll requests burst across 20 independent offerings (50 seats each): no lost or
  duplicate writes and every per-course counter reconciles with persisted records.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Barrier, Event
from time import monotonic
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as selection_final


TID = 1000000000000000001


def _activate_student(student_id: int, student_no: str) -> dict:
    set_tenant({"tenantId": str(TID), "tenantCode": "academic-b-w6"})
    user = {
        "studentId": str(student_id),
        "studentNo": student_no,
        "loginName": student_no,
        "realName": student_no,
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
    }
    set_current_user(user)
    return user


def _clear_context() -> None:
    set_current_user(None)
    set_tenant(None)


def _seed_peak_fixture(*, label: str, student_count: int, course_count: int, capacity: int):
    """Seed only authoritative facts needed by canonical Selection; no test-only bypass rows."""
    from app.models import (
        AaCourse,
        AaSelectionBatch,
        AaSelectionCourse,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
        Major,
        SchoolClass,
        StudentProfile,
    )

    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name=f"W6-{label}-学院", status="ACTIVE")
        db.add(college)
        db.flush()
        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name=f"W6-{label}-专业",
            status="ACTIVE",
        )
        db.add(major)
        db.flush()
        klass = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name=f"W6-{label}-班",
            grade="2026",
            status="ACTIVE",
        )
        db.add(klass)
        db.flush()
        term = AaTerm(
            tenant_id=TID,
            year_code=f"219{label}-219{label}",
            term_no=1,
            term_name=f"W6-{label}-高峰学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name=f"W6-{label}-教学任务批次",
            college_id=college.id,
            status="APPROVED",
        )
        db.add(task_batch)
        db.flush()
        selection_batch = AaSelectionBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name=f"W6-{label}-选课批次",
            status="OPEN",
        )
        db.add(selection_batch)
        db.flush()

        students = []
        for index in range(student_count):
            student = StudentProfile(
                tenant_id=TID,
                student_no=f"W6{label}{index:04d}",
                real_name=f"W6{label}学生{index:04d}",
                college_id=college.id,
                major_id=major.id,
                class_id=klass.id,
                grade="2026",
                current_stage="ON_CAMPUS",
                student_status="NORMAL",
                status="ACTIVE",
            )
            students.append(student)
        db.add_all(students)
        db.flush()

        selection_course_ids = []
        for index in range(course_count):
            catalog = AaCourse(
                tenant_id=TID,
                course_code=f"W6-{label}-C{index:02d}",
                course_name=f"W6-{label}-高峰课程{index:02d}",
                credit=1,
                status="ENABLED",
            )
            db.add(catalog)
            db.flush()
            task = AaTeachingTask(
                tenant_id=TID,
                batch_id=task_batch.id,
                course_id=catalog.id,
                course_code=catalog.course_code,
                course_name=catalog.course_name,
                class_id=klass.id,
                teaching_class_name=klass.class_name,
                teacher_key=f"w6_{label}_teacher_{index}",
                teacher_name=f"W6教师{index}",
                status="READY",
                weekly_hours=2,
                total_hours=36,
                start_week=1,
                end_week=18,
            )
            db.add(task)
            db.flush()
            supply = AaSelectionCourse(
                tenant_id=TID,
                batch_id=selection_batch.id,
                course_id=catalog.id,
                course_name=catalog.course_name,
                teaching_task_id=task.id,
                teacher_key=task.teacher_key,
                teacher_name=task.teacher_name,
                credit=1,
                capacity=capacity,
                min_capacity=0,
                selected_count=0,
                status="OPEN",
            )
            db.add(supply)
            db.flush()
            selection_course_ids.append(int(supply.id))

        student_refs = [(int(row.id), str(row.student_no)) for row in students]
        batch_id = int(selection_batch.id)
        db.commit()
        return {
            "batchId": batch_id,
            "studentRefs": student_refs,
            "selectionCourseIds": selection_course_ids,
        }
    finally:
        db.close()


def _enroll(student_ref, selection_course_id: int, *, start_gate=None):
    student_id, student_no = student_ref
    if start_gate is not None:
        start_gate.wait()
    user = _activate_student(student_id, student_no)
    started = monotonic()
    try:
        result = selection_final.student_enroll(
            user,
            SimpleNamespace(selectionCourseId=str(selection_course_id)),
        )
        return {
            "ok": True,
            "studentId": student_id,
            "selectionCourseId": int(selection_course_id),
            "status": str(result.get("status") or ""),
            "elapsed": monotonic() - started,
        }
    except AppException as exc:
        return {
            "ok": False,
            "business": True,
            "studentId": student_id,
            "selectionCourseId": int(selection_course_id),
            "code": str(getattr(exc, "code", "") or ""),
            "message": str(getattr(exc, "message", "") or str(exc)),
            "httpStatus": int(getattr(exc, "http_status", 0) or 0),
            "elapsed": monotonic() - started,
        }
    except OperationalError as exc:
        return {
            "ok": False,
            "business": False,
            "studentId": student_id,
            "selectionCourseId": int(selection_course_id),
            "rawOperationalError": repr(exc),
            "elapsed": monotonic() - started,
        }
    finally:
        _clear_context()


def _active_records(batch_id: int):
    from app.models import AaSelectionRecord

    db = get_sessionmaker()()
    try:
        return db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == TID,
            AaSelectionRecord.batch_id == int(batch_id),
            AaSelectionRecord.status == "SELECTED",
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_w6_last_seat_128_contenders_never_oversell():
    fixture = _seed_peak_fixture(
        label="128",
        student_count=128,
        course_count=1,
        capacity=1,
    )
    course_id = fixture["selectionCourseIds"][0]
    barrier = Barrier(128)

    with ThreadPoolExecutor(max_workers=128) as pool:
        futures = [
            pool.submit(_enroll, student, course_id, start_gate=barrier)
            for student in fixture["studentRefs"]
        ]
        results = [future.result() for future in futures]

    successes = [row for row in results if row["ok"]]
    rejects = [row for row in results if not row["ok"]]
    assert len(successes) == 1, results
    assert successes[0]["status"] == "SELECTED"
    assert len(rejects) == 127, results
    assert all(row.get("business") is True for row in rejects), rejects
    assert all("容量已满" in row.get("message", "") for row in rejects), rejects

    from app.models import AaSelectionCourse, AaSelectionRecord

    db = get_sessionmaker()()
    try:
        course = db.get(AaSelectionCourse, int(course_id))
        assert course is not None
        assert int(course.selected_count or 0) == 1
        rows = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == TID,
            AaSelectionRecord.selection_course_id == int(course_id),
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        active = [row for row in rows if row.status == "SELECTED"]
        assert len(active) == 1
        assert len({int(row.student_id) for row in active}) == 1
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_w6_1000_enroll_burst_has_no_lost_or_duplicate_writes():
    fixture = _seed_peak_fixture(
        label="1K",
        student_count=1000,
        course_count=20,
        capacity=50,
    )
    start_gate = Event()
    assignments = [
        (student, fixture["selectionCourseIds"][index % 20])
        for index, student in enumerate(fixture["studentRefs"])
    ]

    started = monotonic()
    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = [
            pool.submit(_enroll, student, course_id, start_gate=start_gate)
            for student, course_id in assignments
        ]
        start_gate.set()
        results = [future.result() for future in as_completed(futures)]
    duration = monotonic() - started

    failures = [row for row in results if not row["ok"]]
    assert not failures, failures[:20]
    assert len(results) == 1000
    assert len({int(row["studentId"]) for row in results}) == 1000

    from app.models import AaSelectionCourse, AaSelectionRecord

    db = get_sessionmaker()()
    try:
        supplies = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == TID,
            AaSelectionCourse.id.in_(fixture["selectionCourseIds"]),
            AaSelectionCourse.is_deleted.is_(False),
        ).all()
        assert len(supplies) == 20
        assert all(int(row.selected_count or 0) == 50 for row in supplies)
        assert sum(int(row.selected_count or 0) for row in supplies) == 1000

        records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == TID,
            AaSelectionRecord.batch_id == int(fixture["batchId"]),
            AaSelectionRecord.status == "SELECTED",
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        assert len(records) == 1000
        assert len({int(row.student_id) for row in records}) == 1000
        by_course = {}
        for row in records:
            by_course[int(row.selection_course_id)] = by_course.get(int(row.selection_course_id), 0) + 1
        assert set(by_course) == set(fixture["selectionCourseIds"])
        assert all(by_course[course_id] == 50 for course_id in fixture["selectionCourseIds"])
    finally:
        db.close()

    print(f"W6 1000-enroll burst completed in {duration:.3f}s with 1000/1000 persisted")
