from __future__ import annotations

from datetime import datetime
import inspect

import pytest

TID = 1000000000000000001


def _user(login_name: str, *, role: str = "ACADEMIC_TEACHER", user_type: str = "TEACHER") -> dict:
    return {
        "userId": f"u_{login_name}",
        "loginName": login_name,
        "tenantId": str(TID),
        "currentRoleCode": role,
        "userType": user_type,
        "activeContextId": f"ctx_{login_name}",
    }


def _set_context(user: dict) -> dict:
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    return user


def _seed_assignment(
    db_mode,
    teacher_key: str,
    *,
    batch_status: str = "PUBLISHED",
    course_status: str = "CONFIRMED",
    room_status: str = "ACTIVE",
    published: bool = True,
    exam_date: str = "2029-01-12",
):
    del db_mode
    from app.db.session import get_sessionmaker
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    db = get_sessionmaker()()
    batch = AaExamBatch(
        tenant_id=TID,
        batch_name=f"C-W3监考-{teacher_key}-{batch_status}",
        exam_type="FINAL",
        published_at=datetime(2029, 1, 1, 8, 0, 0) if published else None,
        status=batch_status,
    )
    db.add(batch)
    db.flush()
    course = AaExamCourse(
        tenant_id=TID,
        batch_id=batch.id,
        course_name=f"C-W3监考课程-{teacher_key}",
        class_name="C-W3-2801",
        exam_date=exam_date,
        start_time="09:00",
        end_time="11:00",
        duration_minutes=120,
        status=course_status,
    )
    db.add(course)
    db.flush()
    room = AaExamRoom(
        tenant_id=TID,
        exam_course_id=course.id,
        room_seq=1,
        classroom_text=f"C-W3-{course.id}-301",
        capacity=30,
        planned_count=1,
        seat_mode="SEQUENTIAL",
        source="MANUAL",
        status=room_status,
    )
    db.add(room)
    db.flush()
    invigilator = AaExamInvigilator(
        tenant_id=TID,
        exam_room_id=room.id,
        teacher_key=teacher_key,
        teacher_name=f"监考-{teacher_key}",
        role="CHIEF",
        confirm_status="CONFIRMED",
    )
    db.add(invigilator)
    db.flush()
    ids = {
        "batchId": int(batch.id),
        "courseId": int(course.id),
        "roomId": int(room.id),
        "invigilatorId": int(invigilator.id),
    }
    db.commit()
    db.close()
    return ids


def test_invigilation_workbench_is_read_only_and_uses_only_canonical_assignment_rows():
    from app.modules.academic_affairs.services import academic_affairs_invigilation_workbench_service as svc

    source = inspect.getsource(svc)
    for forbidden in (
        "db.add(",
        "db.flush(",
        "db.commit(",
        "AaExamInvigilator(",
        "freeze_consumer_snapshot",
        "UnifiedTodo",
    ):
        assert forbidden not in source
    assert 'AaExamBatch.status.in_(_FORMAL_BATCH_STATES)' in source
    assert '_FORMAL_BATCH_STATES = ("PUBLISHED", "FINISHED")' in source
    assert 'AaExamRoom.status == "ACTIVE"' in source
    assert 'AaExamCourse.status == "CONFIRMED"' in source
    assert '"scope": "SELF"' in source


def test_invigilation_workbench_filters_to_self_and_only_formal_chain(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamBatch
    from app.modules.academic_affairs.services import academic_affairs_invigilation_workbench_service as svc

    _set_context(_user("cw3_inv_a"))
    valid = _seed_assignment(db_mode, "cw3_inv_a")
    _seed_assignment(db_mode, "cw3_inv_a", batch_status="COURSE_CONFIRMED", published=False)
    _seed_assignment(db_mode, "cw3_inv_a", course_status="PENDING_CONFIRM")
    _seed_assignment(db_mode, "cw3_inv_a", room_status="VOIDED")
    _seed_assignment(db_mode, "cw3_inv_other")

    result = svc.my_invigilation_workbench(_user("cw3_inv_a"), from_date="2029-01-01")
    assert result["scope"] == "SELF"
    assert result["total"] == 1
    assert result["upcomingCount"] == 1
    assert result["finishedCount"] == 0
    assert result["items"][0]["invigilatorId"] == str(valid["invigilatorId"])
    assert result["items"][0]["batchStatus"] == "PUBLISHED"
    assert result["items"][0]["workStatus"] == "UPCOMING"
    assert result["items"][0]["source"] == "AA_EXAM_INVIGILATOR"

    assert svc.my_invigilation_workbench(_user("cw3_unassigned"), from_date="2029-01-01")["items"] == []

    db = get_sessionmaker()()
    batch = db.get(AaExamBatch, valid["batchId"])
    batch.status = "FINISHED"
    db.commit()
    db.close()

    finished = svc.my_invigilation_workbench(_user("cw3_inv_a"), from_date="2029-01-01")
    assert finished["total"] == 1
    assert finished["upcomingCount"] == 0
    assert finished["finishedCount"] == 1
    assert finished["items"][0]["batchStatus"] == "FINISHED"
    assert finished["items"][0]["workStatus"] == "FINISHED"


def test_invigilation_workbench_tracks_canonical_reassignment_without_second_assignment(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamInvigilator
    from app.modules.academic_affairs.services import academic_affairs_exam_facade as exam
    from app.modules.academic_affairs.services import academic_affairs_invigilation_workbench_service as svc

    ids = _seed_assignment(db_mode, "cw3_old_invigilator")
    _set_context(_user("school_admin01", role="SCHOOL_ADMIN", user_type="STAFF"))

    before = svc.my_invigilation_workbench(_user("cw3_old_invigilator"), from_date="2029-01-01")
    assert [item["invigilatorId"] for item in before["items"]] == [str(ids["invigilatorId"])]

    changed = exam.change_invigilator(
        _user("school_admin01", role="SCHOOL_ADMIN", user_type="STAFF"),
        ids["roomId"],
        "cw3_old_invigilator",
        "cw3_new_invigilator",
        "C-W3新监考",
        "教师临时公务冲突需要调整",
        "ASSISTANT",
    )
    assert changed["invigilatorId"] == str(ids["invigilatorId"])
    assert changed["teacherKey"] == "cw3_new_invigilator"

    old_view = svc.my_invigilation_workbench(_user("cw3_old_invigilator"), from_date="2029-01-01")
    new_view = svc.my_invigilation_workbench(_user("cw3_new_invigilator"), from_date="2029-01-01")
    assert old_view["items"] == []
    assert len(new_view["items"]) == 1
    assert new_view["items"][0]["invigilatorId"] == str(ids["invigilatorId"])
    assert new_view["items"][0]["teacherKey"] == "cw3_new_invigilator"
    assert new_view["items"][0]["role"] == "ASSISTANT"
    assert new_view["items"][0]["confirmStatus"] == "ASSIGNED"

    db = get_sessionmaker()()
    rows = db.query(AaExamInvigilator).filter(
        AaExamInvigilator.tenant_id == TID,
        AaExamInvigilator.exam_room_id == ids["roomId"],
        AaExamInvigilator.is_deleted.is_(False),
    ).all()
    db.close()
    assert len(rows) == 1
    assert int(rows[0].id) == ids["invigilatorId"]
    assert rows[0].teacher_key == "cw3_new_invigilator"


def test_invigilation_workbench_rejects_student_role_even_if_login_matches_assignment(db_mode):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_invigilation_workbench_service as svc

    _seed_assignment(db_mode, "cw3_student_collision")
    _set_context(_user("cw3_student_collision", role="STUDENT", user_type="STUDENT"))
    with pytest.raises(AppException) as exc:
        svc.my_invigilation_workbench(
            _user("cw3_student_collision", role="STUDENT", user_type="STUDENT"),
            from_date="2029-01-01",
        )
    assert exc.value.code == "NO_PERMISSION"
