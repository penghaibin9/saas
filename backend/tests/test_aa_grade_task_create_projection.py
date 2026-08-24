"""成绩任务创建响应必须复用 canonical read-side 权限投影。"""
from app.modules.academic_affairs.routers import grade_task_create_v2_router as router_mod


def test_created_task_response_uses_exact_canonical_projection(monkeypatch):
    created = {"gradeTaskId": "42", "status": "NOT_STARTED"}
    canonical = {
        "gradeTaskId": "42",
        "status": "NOT_STARTED",
        "teacherAuthorityReady": True,
        "allowedActions": ["VIEW", "INPUT", "IMPORT"],
    }

    monkeypatch.setattr(
        router_mod.grade_task_read_svc,
        "list_tasks",
        lambda user, page, page_size: ([canonical, {"gradeTaskId": "41"}], 2),
    )

    result = router_mod._canonical_created_projection(created, {"currentRoleCode": "TEACHER"})
    assert result is canonical
    assert result["teacherAuthorityReady"] is True
    assert "INPUT" in result["allowedActions"]


def test_created_task_projection_matches_id_not_page_position(monkeypatch):
    created = {"gradeTaskId": 42, "status": "NOT_STARTED"}
    other = {"gradeTaskId": "43", "teacherAuthorityReady": False, "allowedActions": ["VIEW"]}
    canonical = {"gradeTaskId": "42", "teacherAuthorityReady": True, "allowedActions": ["VIEW", "INPUT"]}

    monkeypatch.setattr(
        router_mod.grade_task_read_svc,
        "list_tasks",
        lambda user, page, page_size: ([other, canonical], 2),
    )

    assert router_mod._canonical_created_projection(created, {}) is canonical


def test_created_task_projection_falls_back_to_committed_create_dto(monkeypatch):
    created = {"gradeTaskId": "42", "status": "NOT_STARTED"}
    monkeypatch.setattr(
        router_mod.grade_task_read_svc,
        "list_tasks",
        lambda user, page, page_size: ([{"gradeTaskId": "99"}], 1),
    )

    # The create transaction has already committed. A defensive read miss must not report a false
    # create failure that could encourage a duplicate user retry.
    assert router_mod._canonical_created_projection(created, {}) is created
