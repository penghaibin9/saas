"""教师确认消费正式任课关系，管理角色不能冒充历史教师快照。"""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("role,key,allowed", [
    ("ACADEMIC_TEACHER", None, False),
    ("ACADEMIC_TEACHER", "teacher02", False),
    ("ACADEMIC_TEACHER", "teacher01", True),
    ("ACADEMIC_ADMIN", None, False),
    ("SCHOOL_ADMIN", "teacher02", False),
    ("COLLEGE_ADMIN", "teacher02", False),
    ("ACADEMIC_ADMIN", "teacher01", True),
])
def test_teacher_command_never_grants_role_based_proxy(monkeypatch, role, key, allowed):
    from app.core.context import set_tenant
    from app.core.exceptions import AppException
    from app.models import AaTeachingTask, AaTeachingClass
    from app.modules.academic_affairs.services import academic_affairs_task_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_task_service as public
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive

    set_tenant(1000000000000000001)
    task = AaTeachingTask(id=1, tenant_id=1000000000000000001, batch_id=2, course_id=3,
                          teacher_key=key, status="ASSIGNED", is_deleted=False)
    query = SimpleNamespace()
    query.filter = lambda *args: query
    query.with_for_update = lambda: query
    query.populate_existing = lambda: query
    query.first = lambda: task
    empty = SimpleNamespace(filter=lambda *args: empty, with_for_update=lambda: empty,
                            populate_existing=lambda: empty, first=lambda: None)
    commits = []
    db = SimpleNamespace(query=lambda model: empty if model is AaTeachingClass else query,
                         commit=lambda: commits.append(True), refresh=lambda row: None)
    monkeypatch.setattr(core, "session", lambda: nullcontext(db))
    monkeypatch.setattr(core, "_term_id_of", lambda *args: 4)
    monkeypatch.setattr(core, "_audit", lambda *args: None)
    monkeypatch.setattr(archive, "guard_term_writable", lambda *args: None)
    user = {"userId": "db-101", "loginName": "teacher01", "currentRoleCode": role, "userType": "TEACHER"}
    if allowed:
        assert public.teacher_act(1, user, "CONFIRM")["status"] == "TEACHER_CONFIRMED"
        assert commits == [True]
    else:
        with pytest.raises(AppException) as error:
            public.teacher_act(1, user, "CONFIRM")
        assert error.value.http_status == 403
        assert task.status == "ASSIGNED" and not commits


@pytest.mark.parametrize("counts,missing,ready", [
    ({}, 0, False), ({"UNKNOWN": 1}, 0, False),
    ({"TEACHER_CONFIRMED": 1}, 1, False), ({"TEACHER_CONFIRMED": 1}, 0, True),
])
def test_batch_confirm_and_final_share_the_full_workbench_gate(monkeypatch, counts, missing, ready):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    rows = [SimpleNamespace(status=state, teacher_key="teacher01") for state, count in counts.items() for _ in range(count)]
    for row in rows[:missing]:
        row.teacher_key = None
    db = SimpleNamespace(execute=lambda query: SimpleNamespace(all=lambda: rows))
    if ready:
        service._require_batch_ready(db, 7)
    else:
        with pytest.raises(AppException) as error:
            service._require_batch_ready(db, 7)
        assert error.value.http_status == 409


@pytest.mark.parametrize("all_scope,colleges,requested,expected", [
    (True, set(), None, "VALIDATION_ERROR"),
    (True, set(), "invalid", "VALIDATION_ERROR"),
    (False, {11, 12}, None, "VALIDATION_ERROR"),
    (False, {11}, None, 11),
    (False, {11}, 12, "NO_DATA_SCOPE"),
    (True, set(), 12, 12),
])
def test_generation_requires_one_authorized_offering_college(monkeypatch, all_scope, colleges, requested, expected):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    scope = service.TaskManageScope(all=all_scope, college_ids=colleges)
    monkeypatch.setattr(service, "_scope", lambda *args: scope)
    if isinstance(expected, int):
        assert service._generation_college(None, {}, requested) == (expected, scope)
    else:
        with pytest.raises(AppException) as error:
            service._generation_college(None, {}, requested)
        assert error.value.code == expected


@pytest.mark.parametrize("action", ["manage", "adjust", "merge"])
@pytest.mark.parametrize("scope,college,permission,actor,allowed", [
    ("TENANT_ALL", 11, True, "101", False),
    ("COLLEGE", 12, True, "101", False),
    ("COLLEGE", 11, False, "101", False),
    ("COLLEGE", 11, True, "102", False),
    ("COLLEGE", 11, True, "101", True),
])
def test_college_task_writes_require_current_scope_permission_and_assignee(monkeypatch, action, scope, college, permission, actor, allowed):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as owners
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive
    code = "academicAffairs.teachingTask." + action
    context = SimpleNamespace(scope_type=scope, college_ids={college}, permission_codes={code} if permission else set())
    monkeypatch.setattr(service, "build_affairs_context", lambda *args: context)
    monkeypatch.setattr(service, "tenant_get", lambda *args, **kwargs: SimpleNamespace(college_id=11, term_id=4, status="DRAFT", is_deleted=False))
    monkeypatch.setattr(identity, "_current_user_id", lambda *args: actor)
    calls = []
    def resolve(*args, **kwargs):
        assert kwargs["permission_code"] == code
        return {"resolved": True, "assigneeUserIds": ["101"]}
    monkeypatch.setattr(owners, "resolve_organization", resolve)
    monkeypatch.setattr(archive, "guard_term_writable", lambda *args: calls.append("archive_guard"))
    if allowed:
        service._require_college_task_action(SimpleNamespace(refresh=lambda *args, **kwargs: None), SimpleNamespace(batch_id=7), {}, action)
        assert calls == ["archive_guard"]
    else:
        with pytest.raises(AppException) as error:
            service._require_college_task_action(SimpleNamespace(refresh=lambda *args, **kwargs: None), SimpleNamespace(batch_id=7), {}, action)
        assert error.value.http_status == 403 and not calls
