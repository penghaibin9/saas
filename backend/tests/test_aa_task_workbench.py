"""教学任务工作台状态机、阻断项与范围行为回归。"""
from types import SimpleNamespace


def _task(status, *, teacher_key="T001"):
    return SimpleNamespace(
        status=status, teacher_key=teacher_key,
        course_name="数据库原理", course_code="DB101",
    )


def test_assigned_waiting_teacher_is_a_batch_blocker():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _summary

    result = _summary([
        _task("PENDING_ASSIGN", teacher_key=""),
        _task("ASSIGNED"), _task("REJECTED_BY_TEACHER"),
        _task("TEACHER_CONFIRMED"),
    ])
    assert result["canAdvance"] is False
    assert result["unassignedCount"] == 1
    assert result["waitingTeacherCount"] == 1
    assert result["teacherRejectedCount"] == 1
    assert {"UNASSIGNED", "WAIT_TEACHER", "TEACHER_REJECTED"} <= {
        item["code"] for item in result["blockers"]
    }


def test_all_teacher_confirmed_tasks_can_advance_to_review():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _summary

    result = _summary([_task("TEACHER_CONFIRMED"), _task("TEACHER_CONFIRMED")])
    assert result["canAdvance"] is True
    assert result["teacherConfirmRate"] == 100.0
    assert result["blockers"] == []


def test_missing_stable_teacher_key_blocks_even_when_status_looks_confirmed():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _summary

    result = _summary([_task("TEACHER_CONFIRMED", teacher_key="")])
    assert result["canAdvance"] is False
    assert result["blockers"][0]["code"] == "TEACHER_KEY_MISSING"


def test_next_action_preserves_college_then_academic_review_chain():
    from app.modules.academic_affairs.services.academic_affairs_task_service import _batch_next_action, _summary

    ready = _summary([_task("TEACHER_CONFIRMED")])
    draft = _batch_next_action(SimpleNamespace(status="DRAFT"), ready)
    college_confirmed = _batch_next_action(SimpleNamespace(status="COLLEGE_CONFIRMED"), ready)
    assert draft["code"] == "COLLEGE_CONFIRM"
    assert "学院" in draft["label"]
    assert college_confirmed["code"] == "ACADEMIC_REVIEW"
    assert "教务终审" in college_confirmed["label"]


def test_empty_task_management_scope_is_fail_closed():
    from app.modules.academic_affairs.services.academic_affairs_task_service import TaskManageScope

    assert TaskManageScope(role="ACADEMIC_TEACHER").blocked is True
    assert TaskManageScope(class_ids={10}, role="COLLEGE_ADMIN").blocked is False
    assert TaskManageScope(all=True, role="ACADEMIC_ADMIN").blocked is False


def test_public_task_service_is_single_explicit_entry():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    assert service.get_batch_workbench.__module__.endswith("academic_affairs_task_service")
    assert service.submit_batch.__module__.endswith("academic_affairs_task_service")
    assert service.generate_batch.__module__.endswith("academic_affairs_task_service")
    assert "facade" not in service.submit_batch.__module__
