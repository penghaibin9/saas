from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001


def _set_tenant():
    from app.core.context import set_tenant

    set_tenant({"tenantId": str(TID)})


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaDeferredExam,
        AaExamBatch,
        AaExamCourse,
        AaExamRoom,
        AaExamRoomStudent,
        StudentProfile,
    )

    _set_tenant()
    db = get_sessionmaker()()
    student = StudentProfile(
        tenant_id=TID,
        student_no="CW3-DEFER-001",
        real_name="C-W3缓考学生",
        grade="2026",
        student_status="NORMAL",
        status="ACTIVE",
    )
    db.add(student)
    db.flush()

    batch = AaExamBatch(
        tenant_id=TID,
        batch_name="C-W3缓考选项边界",
        status="PUBLISHED",
        published_at=datetime.utcnow(),
    )
    db.add(batch)
    db.flush()

    specs = [
        ("已开考课程", "2000-01-01", "09:00"),
        ("日期损坏课程", "not-a-date", "09:00"),
        ("未来可申请课程", "2099-01-10", "09:00"),
        ("未来申请中课程", "2099-01-11", "09:00"),
    ]
    courses = []
    for index, (name, exam_date, start_time) in enumerate(specs, start=1):
        course = AaExamCourse(
            tenant_id=TID,
            batch_id=batch.id,
            course_name=name,
            exam_date=exam_date,
            start_time=start_time,
            end_time="11:00",
            status="CONFIRMED",
        )
        db.add(course)
        db.flush()
        room = AaExamRoom(
            tenant_id=TID,
            exam_course_id=course.id,
            room_seq=1,
            classroom_text=f"CW3-D{index:02d}",
            capacity=30,
            planned_count=1,
            seat_mode="SEQUENTIAL",
            source="MANUAL",
            status="ACTIVE",
        )
        db.add(room)
        db.flush()
        db.add(AaExamRoomStudent(
            tenant_id=TID,
            exam_room_id=room.id,
            exam_course_id=course.id,
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.real_name,
            seat_no=1,
            admission_no=f"CW3D{index:02d}",
            attendance_status="NOT_STARTED",
        ))
        courses.append(course)

    db.flush()
    active_course = courses[3]
    db.add(AaDeferredExam(
        tenant_id=TID,
        student_id=student.id,
        student_no=student.student_no,
        student_name=student.real_name,
        exam_course_id=active_course.id,
        course_name=active_course.course_name,
        reason_type="SICK",
        reason="C-W3进行中的缓考申请",
        apply_at=datetime.utcnow(),
        current_node="COUNSELOR",
        status="SUBMITTED",
    ))
    db.commit()
    result = {
        "student_id": int(student.id),
        "past_id": int(courses[0].id),
        "malformed_id": int(courses[1].id),
        "future_id": int(courses[2].id),
        "active_id": int(courses[3].id),
    }
    db.close()
    return result


def test_deferrable_courses_omits_started_or_ambiguous_exam_and_keeps_server_action_truth(db_mode):
    from app.modules.academic_affairs.services import student_exam_read_service as service

    ids = _seed(db_mode)
    user = {
        "tenantId": str(TID),
        "userType": "STUDENT",
        "studentId": str(ids["student_id"]),
        "studentNo": "CW3-DEFER-001",
        "realName": "C-W3缓考学生",
    }

    result = service.deferrable_courses(user)
    items = result["items"]
    by_id = {int(item["examCourseId"]): item for item in items}

    assert result["timezone"] == "Asia/Shanghai"
    assert result["total"] == 2
    assert ids["past_id"] not in by_id
    assert ids["malformed_id"] not in by_id

    available = by_id[ids["future_id"]]
    assert available["started"] is False
    assert available["hasActiveDefer"] is False
    assert available["canApply"] is True

    active = by_id[ids["active_id"]]
    assert active["started"] is False
    assert active["hasActiveDefer"] is True
    assert active["canApply"] is False
