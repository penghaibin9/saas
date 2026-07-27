"""V2-02 教学班运行时字段与合拆班投影回归。"""
from types import SimpleNamespace


def test_safe_snapshot_does_not_invent_task_model_column():
    from app.models import AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service

    assert "class_name" not in AaTeachingTask.__mapper__.attrs.keys()
    task = SimpleNamespace(
        id=8, batch_id=2, course_id=3, course_code="ST101", course_name="软件测试",
        class_id=6, teaching_class_name="软件测试(软工1班)",
        is_merged=False, merged_into_id=None,
    )
    batch = SimpleNamespace(id=2, term_id=1)
    snapshot = service._safe_task_snapshot(task, batch)
    assert '"administrativeClassName": ""' in snapshot
    assert '"courseName": "软件测试"' in snapshot
    assert service._safe_class_name(task) == "软件测试(软工1班)"


def test_public_merge_flow_returns_projection_result_without_hiding_task_result(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    class _Session:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(service, "session", lambda: _Session())
    monkeypatch.setattr(service, "_ensure_task_visible", lambda _db, task_id, _user: (SimpleNamespace(id=task_id), None))
    monkeypatch.setattr(service._core, "merge_tasks", lambda _body, _user: {"taskId": "11", "status": "PENDING_ASSIGN"})
    monkeypatch.setattr(service, "_sync_task", lambda task_id: {"ok": True, "teachingTaskId": str(task_id)})
    monkeypatch.setattr(
        service, "_refresh_administrative_roster",
        lambda task_id, reason: {"ok": False, "teachingTaskId": str(task_id), "error": "已进入选课流程"},
    )

    result = service.merge_tasks(SimpleNamespace(taskIds=[11, 12]), {})
    assert result["status"] == "PENDING_ASSIGN"
    assert [row["teachingTaskId"] for row in result["teachingClassProjections"]] == ["11", "12"]
    assert result["rosterProjection"] == {
        "ok": False, "teachingTaskId": "11", "error": "已进入选课流程",
    }


def test_no_runtime_guard_or_facade_is_required_by_public_flow():
    from app.modules.academic_affairs.services import (
        academic_affairs_task_service as task_service,
        academic_affairs_teaching_class_service as class_service,
    )

    assert task_service.merge_tasks.__module__.endswith("academic_affairs_task_service")
    assert class_service.ensure_teaching_class_for_task.__module__.endswith(
        "academic_affairs_teaching_class_service"
    )
    assert "facade" not in task_service.merge_tasks.__module__
    assert "runtime_guard" not in class_service.ensure_teaching_class_for_task.__module__
