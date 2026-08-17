from __future__ import annotations

import inspect

import pytest

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name="school_admin01"):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _formal_user():
    return {
        "userId": "u_school_admin01",
        "loginName": "school_admin01",
        "tenantId": str(TID),
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "SCHOOL_ADMIN",
    }


def _set_context():
    from app.core.context import set_current_user, set_tenant

    user = _formal_user()
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    return user


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaClassroom,
        AaCourse,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
        Major,
        SchoolClass,
        StudentProfile,
    )

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=TID,
        year_code="2028-2029",
        term_no=1,
        term_name="C-W3正式打印学期",
        status="PUBLISHED",
        is_current=True,
    )
    db.add(term)
    db.flush()
    college = College(tenant_id=TID, college_name="C-W3学院", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="C-W3专业", status="ACTIVE")
    db.add(major)
    db.flush()
    klass = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name="C-W3-2801",
        grade="2028",
        status="ACTIVE",
    )
    db.add(klass)
    db.flush()
    course = AaCourse(
        tenant_id=TID,
        course_code="CW3_PRINT",
        course_name="C-W3正式打印课程",
        credit=2,
        version=1,
        status="ENABLED",
    )
    db.add(course)
    db.flush()
    classroom = AaClassroom(
        tenant_id=TID,
        building_code="CW3",
        building_name="C-W3楼",
        room_code="301",
        room_name="C-W3-301",
        capacity=30,
        status="AVAILABLE",
    )
    db.add(classroom)
    db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        batch_name="C-W3教学任务",
        college_id=college.id,
        status="ACTIVE",
    )
    db.add(task_batch)
    db.flush()
    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=task_batch.id,
        course_id=course.id,
        course_name=course.course_name,
        class_id=klass.id,
        teaching_class_name=klass.class_name,
        teacher_key="cw3_teacher",
        teacher_name="C-W3教师",
    )
    db.add(task)
    db.flush()
    student = StudentProfile(
        tenant_id=TID,
        student_no="CW328001",
        real_name="C-W3考生",
        college_id=college.id,
        major_id=major.id,
        class_id=klass.id,
        grade="2028",
        student_status="NORMAL",
        status="ACTIVE",
    )
    db.add(student)
    db.flush()
    ids = {
        "term": int(term.id),
        "task": int(task.id),
        "student": int(student.id),
        "classroom": int(classroom.id),
        "college": int(college.id),
        "major": int(major.id),
        "class": int(klass.id),
    }
    db.commit()
    db.close()
    return ids


def _arranged_room(client, admin, ids):
    bid = client.post(
        f"{BASE}/exam/batches",
        headers=admin,
        json={"batchName": "C-W3正式打印批次", "termId": str(ids["term"])},
    ).json()["data"]["batchId"]
    cid = client.post(
        f"{BASE}/exam/batches/{bid}/courses",
        headers=admin,
        json={"teachingTaskId": str(ids["task"])},
    ).json()["data"]["examCourseId"]
    confirmed = client.post(
        f"{BASE}/exam/courses/{cid}/confirm",
        headers=admin,
        json={"action": "CONFIRM"},
    )
    assert confirmed.status_code == 200, confirmed.text
    scheduled = client.put(
        f"{BASE}/exam/courses/{cid}/schedule",
        headers=admin,
        json={
            "examDate": "2029-01-12",
            "startTime": "09:00",
            "endTime": "11:00",
            "durationMinutes": 120,
        },
    )
    assert scheduled.status_code == 200, scheduled.text
    advanced = client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    assert advanced.status_code == 200, advanced.text
    room = client.post(
        f"{BASE}/exam/courses/{cid}/rooms",
        headers=admin,
        json={"classroomId": str(ids["classroom"]), "capacity": 30},
    )
    assert room.status_code == 200, room.text
    rid = room.json()["data"]["examRoomId"]
    inv = client.post(
        f"{BASE}/exam/rooms/{rid}/invigilators",
        headers=admin,
        json={"teacherKey": "cw3_invigilator", "teacherName": "C-W3监考"},
    )
    assert inv.status_code == 200, inv.text
    seats = client.post(
        f"{BASE}/exam/rooms/{rid}/seats",
        headers=admin,
        json={"studentIds": [str(ids["student"])]},
    )
    assert seats.status_code == 200, seats.text
    return int(bid), int(cid), int(rid)


def test_formal_print_provider_is_strictly_read_only_and_keeps_historical_roster_identity():
    from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service

    source = inspect.getsource(print_service.formal_room_print)
    for forbidden in (
        "db.add(",
        "db.flush(",
        "db.commit(",
        "resolve_versioned_roster",
        "require_consumer_snapshot_current",
        "freeze_consumer_snapshot",
    ):
        assert forbidden not in source
    assert 'get_consumer_snapshot(db, "EXAM_COURSE"' in source
    assert '"PUBLISHED", "FINISHED", "ARCHIVED"' in inspect.getsource(print_service)


def test_formal_print_rejects_arranged_but_unpublished_room(client, db_mode):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service

    ids = _seed(db_mode)
    admin = _hdr(client)
    _bid, _cid, room_id = _arranged_room(client, admin, ids)
    user = _set_context()

    with pytest.raises(AppException) as exc:
        print_service.formal_room_print(user, room_id)
    assert exc.value.code == "DATA_CONFLICT"
    assert "尚未发布" in exc.value.message


def test_formal_print_returns_only_published_frozen_seat_facts(client, db_mode):
    from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service

    ids = _seed(db_mode)
    admin = _hdr(client)
    bid, cid, room_id = _arranged_room(client, admin, ids)
    published = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text

    user = _set_context()
    result = print_service.formal_room_print(user, room_id)
    assert result["documentKind"] == "EXAM_ROOM_SEATING"
    assert result["documentStatus"] == "OFFICIAL"
    assert result["batchStatus"] == "PUBLISHED"
    assert result["publishedAt"]
    assert result["examCourseId"] == str(cid)
    assert result["seatCount"] == 1
    assert result["rosterIdentity"]["memberCount"] == 1
    assert result["rosterIdentity"]["rosterVersionId"]
    assert result["rosterIdentity"]["rosterHash"]
    assert result["seats"] == [{
        "seatNo": 1,
        "admissionNo": f"{cid}0001",
        "studentNo": "CW328001",
        "studentName": "C-W3考生",
    }]
    assert "studentId" not in result["seats"][0]


def test_formal_print_fails_closed_when_published_seat_set_drifts(client, db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaExamRoomStudent
    from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service

    ids = _seed(db_mode)
    admin = _hdr(client)
    bid, _cid, room_id = _arranged_room(client, admin, ids)
    published = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text

    db = get_sessionmaker()()
    seat = db.query(AaExamRoomStudent).filter(
        AaExamRoomStudent.tenant_id == TID,
        AaExamRoomStudent.exam_room_id == room_id,
        AaExamRoomStudent.is_deleted.is_(False),
    ).one()
    seat.is_deleted = True
    db.commit()
    db.close()

    user = _set_context()
    with pytest.raises(AppException) as exc:
        print_service.formal_room_print(user, room_id)
    assert exc.value.code == "DATA_CONFLICT"
    assert "没有可打印座位数据" in exc.value.message


def test_formal_print_accepts_one_frozen_roster_split_across_multiple_rooms(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaClassroom, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_exam_print_service as print_service

    ids = _seed(db_mode)
    db = get_sessionmaker()()
    second_student = StudentProfile(
        tenant_id=TID,
        student_no="CW328002",
        real_name="C-W3第二考生",
        college_id=ids["college"],
        major_id=ids["major"],
        class_id=ids["class"],
        grade="2028",
        student_status="NORMAL",
        status="ACTIVE",
    )
    second_classroom = AaClassroom(
        tenant_id=TID,
        building_code="CW3",
        building_name="C-W3楼",
        room_code="302",
        room_name="C-W3-302",
        capacity=30,
        status="AVAILABLE",
    )
    db.add_all([second_student, second_classroom])
    db.flush()
    second_student_id = int(second_student.id)
    second_classroom_id = int(second_classroom.id)
    db.commit()
    db.close()

    admin = _hdr(client)
    bid, cid, first_room_id = _arranged_room(client, admin, ids)
    second_room = client.post(
        f"{BASE}/exam/courses/{cid}/rooms",
        headers=admin,
        json={"classroomId": str(second_classroom_id), "capacity": 30},
    )
    assert second_room.status_code == 200, second_room.text
    second_room_id = int(second_room.json()["data"]["examRoomId"])
    second_invigilator = client.post(
        f"{BASE}/exam/rooms/{second_room_id}/invigilators",
        headers=admin,
        json={"teacherKey": "cw3_invigilator_02", "teacherName": "C-W3第二监考"},
    )
    assert second_invigilator.status_code == 200, second_invigilator.text
    second_seat = client.post(
        f"{BASE}/exam/rooms/{second_room_id}/seats",
        headers=admin,
        json={"studentIds": [str(second_student_id)]},
    )
    assert second_seat.status_code == 200, second_seat.text

    published = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text

    user = _set_context()
    first_print = print_service.formal_room_print(user, first_room_id)
    second_print = print_service.formal_room_print(user, second_room_id)
    assert first_print["rosterIdentity"]["memberCount"] == 2
    assert second_print["rosterIdentity"]["memberCount"] == 2
    assert first_print["seatCount"] == 1
    assert second_print["seatCount"] == 1
    assert first_print["seats"][0]["studentNo"] == "CW328001"
    assert second_print["seats"][0]["studentNo"] == "CW328002"
