from types import SimpleNamespace

import pytest


def test_public_service_exposes_draft_void_command():
    from app.modules.academic_affairs.services import academic_affairs_task_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_task_service as public

    assert public.void_draft_task is core.void_draft_task


def test_unassigned_draft_without_downstream_rows_is_voidable():
    from app.modules.academic_affairs.services.academic_affairs_task_core_service import _validate_draft_task_voidable

    task = SimpleNamespace(status="PENDING_ASSIGN", teacher_key="", teacher_id=None)
    batch = SimpleNamespace(status="DRAFT")
    _validate_draft_task_voidable(task, batch, {
        "schedule": 0, "teachingClass": 0, "selection": 0, "grade": 0,
        "scheduleChange": 0, "examCourse": 0, "textbookSelection": 0,
        "evaluationTask": 0, "evaluationResult": 0, "attendanceSession": 0,
    })


def test_untouched_initial_auto_teaching_class_can_be_archived_with_roster_preserved():
    from app.modules.academic_affairs.services.academic_affairs_task_core_service import _validate_auto_draft_teaching_class

    task = SimpleNamespace(id=4, class_id=44)
    teaching_class = SimpleNamespace(
        id=40, status="ACTIVE", class_type="ADMIN", source_type="TEACHING_TASK", source_id=4,
        roster_status="LOCKED", current_roster_version_id=400, current_roster_version_no=1,
    )
    version = SimpleNamespace(
        id=400, version_no=1, source_type="ADMIN_CLASS", source_id=44, status="LOCKED",
        member_count=2, is_deleted=False,
    )
    members = [
        SimpleNamespace(status="ACTIVE", roster_version_id=400, source_type="ADMIN_CLASS", is_deleted=False)
        for _ in range(2)
    ]
    _validate_auto_draft_teaching_class(task, teaching_class, [version], members, 0, 0)


@pytest.mark.parametrize(
    "teacher_count,consumer_count,version_count,version_no,expected",
    [
        (1, 0, 1, 1, "已分配教师"),
        (0, 1, 1, 1, "已分配教师"),
        (0, 0, 2, 1, "名单已有后续版本"),
        (0, 0, 1, 2, "名单已被调整"),
    ],
)
def test_auto_teaching_class_void_rejects_teacher_consumption_or_roster_changes(
    teacher_count, consumer_count, version_count, version_no, expected,
):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services.academic_affairs_task_core_service import _validate_auto_draft_teaching_class

    task = SimpleNamespace(id=4, class_id=44)
    teaching_class = SimpleNamespace(
        id=40, status="ACTIVE", class_type="ADMIN", source_type="TEACHING_TASK", source_id=4,
        roster_status="LOCKED", current_roster_version_id=400, current_roster_version_no=version_no,
    )
    version = SimpleNamespace(
        id=400, version_no=1, source_type="ADMIN_CLASS", source_id=44, status="LOCKED",
        member_count=2, is_deleted=False,
    )
    versions = [version] * version_count
    members = [
        SimpleNamespace(status="ACTIVE", roster_version_id=400, source_type="ADMIN_CLASS", is_deleted=False)
        for _ in range(2)
    ]
    with pytest.raises(AppException) as error:
        _validate_auto_draft_teaching_class(task, teaching_class, versions, members, teacher_count, consumer_count)
    assert expected in error.value.message


@pytest.mark.parametrize(
    "task,batch,counts,expected",
    [
        (SimpleNamespace(status="ASSIGNED", teacher_key="teacher-b", teacher_id=2), SimpleNamespace(status="DRAFT"), {}, "已分配"),
        (SimpleNamespace(status="PENDING_ASSIGN", teacher_key="", teacher_id=None), SimpleNamespace(status="APPROVED"), {}, "仅草稿批次"),
        *[(SimpleNamespace(status="PENDING_ASSIGN", teacher_key="", teacher_id=None),
           SimpleNamespace(status="DRAFT"), {reference: 1}, "已有业务引用")
          for reference in ("schedule", "teachingClass", "selection", "grade", "scheduleChange",
                            "examCourse", "textbookSelection", "evaluationTask", "evaluationResult",
                            "attendanceSession")],
    ],
)
def test_draft_void_rejects_work_in_progress_or_any_downstream_reference(task, batch, counts, expected):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services.academic_affairs_task_core_service import _validate_draft_task_voidable

    with pytest.raises(AppException) as error:
        _validate_draft_task_voidable(task, batch, counts)
    assert error.value.code == "DATA_CONFLICT"
    assert expected in error.value.message
