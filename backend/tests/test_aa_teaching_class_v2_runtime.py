"""V2-02 教学班运行时兼容与合拆班名单投影回归。"""
from types import SimpleNamespace


def test_runtime_guard_supplies_missing_task_class_name_without_fake_model_column():
    from app.models import AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_runtime_guard as guard

    assert "class_name" not in AaTeachingTask.__mapper__.attrs.keys()
    task = SimpleNamespace(course_name="软件测试", teaching_class_name="软件测试(软工1班)")
    safe = guard._TeachingTaskCompat(task)

    assert safe.class_name == ""
    assert safe.course_name == "软件测试"
    assert guard._base._task_snapshot is guard._task_snapshot
    assert guard._query._class_dto is guard._class_dto
    assert guard._admin._preview_rows is guard._preview_rows


def test_merge_tasks_refreshes_survivor_roster_version(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_task_teaching_class_facade as service

    calls = []
    monkeypatch.setattr(service, "_original_merge_tasks", lambda _body, _user: {"taskId": "11", "status": "PENDING_ASSIGN"})
    monkeypatch.setattr(service, "_sync_task", lambda task_id: {"ok": True, "teachingTaskId": str(task_id)})
    monkeypatch.setattr(
        service,
        "_refresh_administrative_roster",
        lambda task_id, reason: calls.append((task_id, reason)) or {
            "ok": True, "teachingTaskId": str(task_id), "rosterVersionNo": 2,
        },
    )

    result = service.merge_tasks(SimpleNamespace(taskIds=[11, 12]), {"userId": "u1"})

    assert [row["teachingTaskId"] for row in result["teachingClassProjections"]] == ["11", "12"]
    assert calls == [(11, "教学任务合班后重建行政班成员并集")]
    assert result["rosterProjection"]["rosterVersionNo"] == 2


def test_refresh_roster_error_is_explicit_and_does_not_hide_task_result(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_task_teaching_class_facade as service

    monkeypatch.setattr(service, "_original_merge_tasks", lambda _body, _user: {"taskId": "21", "status": "PENDING_ASSIGN"})
    monkeypatch.setattr(service, "_sync_task", lambda task_id: {"ok": True, "teachingTaskId": str(task_id)})
    monkeypatch.setattr(
        service,
        "_refresh_administrative_roster",
        lambda task_id, reason: {"ok": False, "teachingTaskId": str(task_id), "error": "已进入选课流程"},
    )

    result = service.merge_tasks(SimpleNamespace(taskIds=[21, 22]), {})

    assert result["status"] == "PENDING_ASSIGN"
    assert result["rosterProjection"] == {
        "ok": False, "teachingTaskId": "21", "error": "已进入选课流程",
    }
