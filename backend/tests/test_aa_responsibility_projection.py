"""责任投影的优先级、失效和跨院事实规则；不连接数据库。"""
from datetime import datetime, timedelta
from types import SimpleNamespace as Row
from unittest.mock import MagicMock

from app.modules.academic_affairs.services import academic_affairs_responsibility_service as service

NOW = datetime(2026, 9, 26)


def assignment(uid=1, kind="SECRETARY", **changes):
    values = dict(user_id=uid, assignment_type=kind, status="ACTIVE", is_deleted=False,
                  effective_at=NOW - timedelta(days=2), expires_at=None)
    return Row(**(values | changes))


def user(uid, **changes):
    return Row(**(dict(id=uid, real_name=f"责任人{uid}", status="ACTIVE", is_deleted=False) | changes))


def test_flow_resolves_college_secretary_assignment():
    people, source, _ = service._choose_assignees([assignment()], [user(1), user(2)],
                                                ("SECRETARY", "LEADER"), 2, NOW)
    assert [row.id for row in people] == [1]
    assert source == "STAFF_ASSIGNMENT"


def test_flow_falls_back_to_college_secretary_projection():
    people, source, _ = service._choose_assignees([], [user(2)], ("SECRETARY",), 2, NOW)
    assert [row.id for row in people] == [2]
    assert source == "COLLEGE_SECRETARY"


def test_flow_assignment_expired_blocks():
    people, source, code = service._choose_assignees(
        [assignment(expires_at=NOW)], [user(1)], ("SECRETARY",), 1, NOW)
    assert people == [] and source == "UNRESOLVED" and code == "ASSIGNMENT_EXPIRED"


def test_revoked_deleted_or_disabled_assignment_cannot_be_revived_by_projection():
    for changes in ({"status": "REVOKED"}, {"is_deleted": True}, {"effective_at": NOW + timedelta(days=1)}):
        assert not service._choose_assignees([assignment(**changes)], [user(1)], ("SECRETARY",), 1, NOW)[0]
    assert not service._choose_assignees([assignment()], [user(1, status="DISABLED")], ("SECRETARY",), 1, NOW)[0]


def test_flow_major_leader_resolution():
    people, source, _ = service._choose_assignees([assignment(kind="LEADER")], [user(1)],
                                                ("LEADER", "SECRETARY"), None, NOW)
    assert [row.id for row in people] == [1] and source == "STAFF_ASSIGNMENT"


def test_flow_course_owner_not_student_college():
    assert service.offering_college_id(Row(owner_college_id=12), Row(college_id=34)) == 12
    candidate = service.offering_unit(Row(owner_college_id=None), Row(college_id=34))
    assert candidate["collegeId"] == "34" and candidate["source"] == "TASK_BATCH"
    assert candidate["blockers"][0]["code"] == "OFFERING_UNIT_UNRESOLVED"


def test_flow_task_batch_college_is_authoritative():
    assert service.offering_college_id(Row(owner_college_id=12), Row(college_id=34), teaching_task=True) == 34
    assert service.offering_college_id(Row(owner_college_id=12), Row(college_id=None), teaching_task=True) is None


def test_flow_unresolved_responsibility_fail_closed():
    assert service._choose_assignees([], [], ("SECRETARY",), None, NOW)[2] == "RESPONSIBILITY_UNRESOLVED"


def test_teacher_resolver_prefers_formal_relation_and_never_revives_removed_teacher(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as authority
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard

    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(authority, "class_authority_weeks", lambda db, classes: {50: 4})
    monkeypatch.setattr(guard, "_runtime_permission_holder_ids", lambda db, permission: [2])
    db = MagicMock()
    teacher = user(2)
    teacher.login_name = "new_teacher"
    db.scalars.return_value.all.side_effect = [
        [Row(id=50, teaching_task_id=10, status="ACTIVE")],
        [Row(teaching_class_id=50, teacher_key="new_teacher", start_week=1, end_week=8)],
        [teacher],
    ]
    result = service.resolve_teacher(db, Row(id=10, teacher_key="old_teacher"))
    assert result["assigneeUserIds"] == ["2"]
    assert result["source"] == "TEACHING_CLASS_TEACHER"
    db.scalars.return_value.all.side_effect = [[Row(id=50, teaching_task_id=10, status="ACTIVE")], []]
    assert not service.resolve_teacher(db, Row(id=10, teacher_key="old_teacher"))["resolved"]


def test_revoked_teacher_permission_blocks_active_account(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(guard, "_runtime_permission_holder_ids", lambda db, permission: [])
    person = user(1)
    person.login_name = "teacher"
    db = MagicMock()
    db.scalars.return_value.all.side_effect = [[], [person]]
    assert not service.resolve_teacher(db, Row(id=10, teacher_key="teacher"))["resolved"]


def test_batch_teacher_resolution_shares_queries_and_keeps_formal_authority(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as authority
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(authority, "class_authority_weeks", lambda db, classes: {50: 4, 51: 4})
    holders = MagicMock(return_value=[2, 3])
    monkeypatch.setattr(guard, "_runtime_permission_holder_ids", holders)
    a, b = user(2), user(3)
    a.login_name, b.login_name = "formal", "legacy"
    db = MagicMock()
    db.scalars.return_value.all.side_effect = [
        [Row(id=50, teaching_task_id=10, status="ACTIVE"), Row(id=51, teaching_task_id=11, status="ACTIVE")],
        [Row(teaching_class_id=50, teacher_key="formal", start_week=1, end_week=8)], [a, b]]
    result = service.resolve_teachers(db, [Row(id=10, teacher_key="legacy"),
        Row(id=11, teacher_key="legacy"), Row(id=12, teacher_key="legacy")])
    assert result[10]["assigneeUserIds"] == ["2"]
    assert not result[11]["resolved"]  # 正式关系撤销不回退旧主讲教师。
    assert result[12]["assigneeUserIds"] == ["3"]
    assert db.scalars.call_count == 3 and holders.call_count == 1


def test_batch_teacher_resolution_rejects_ambiguous_login_without_poisoning_other_tasks(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(guard, "_runtime_permission_holder_ids", lambda db, permission: [2, 3, 4])
    a, b, c = user(2), user(3), user(4)
    a.login_name, b.login_name, c.login_name = "ambiguous", "ambiguous", "valid"
    db = MagicMock()
    db.scalars.return_value.all.side_effect = [[], [a, b, c]]
    result = service.resolve_teachers(db, [Row(id=10, teacher_key="ambiguous"), Row(id=11, teacher_key="valid")])
    assert not result[10]["resolved"]
    assert result[11]["assigneeUserIds"] == ["4"]


def test_organization_resolver_rejects_assignment_with_other_college_authority(monkeypatch):
    from app.core import affairs_security
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard

    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(guard, "_runtime_permission_holder_ids", lambda db, permission: [1])
    monkeypatch.setattr(affairs_security, "build_affairs_context", lambda user, db: Row(
        scope_type="COLLEGE", college_ids={99}, permission_codes={"academicAffairs.program.review"}))
    person = user(1)
    person.login_name, person.user_type = "secretary", "TEACHER"
    db = MagicMock()
    db.scalar.return_value = Row(id=12, college_name="目标学院", secretary_id=1)
    db.scalars.return_value.all.side_effect = [[assignment()], [person]]
    db.execute.return_value.all.return_value = [(1, Row(id=4, role_code="COLLEGE_ADMIN"))]
    result = service.resolve_organization(db, "COLLEGE", 12, permission_code="academicAffairs.program.review")
    assert not result["resolved"]


def test_explicit_read_cache_reuses_context_only_within_same_request_and_tenant(monkeypatch):
    from app.core import affairs_security
    tenant = [1]
    monkeypatch.setattr(service, "_tid", lambda: tenant[0])
    allowed = Row(scope_type="COLLEGE", college_ids={12},
        permission_codes={"academicAffairs.program.review", "academicAffairs.grade.collegeReview"})
    revoked = Row(scope_type="COLLEGE", college_ids={99}, permission_codes=set())
    build = MagicMock(side_effect=[allowed, revoked, revoked])
    monkeypatch.setattr(affairs_security, "build_affairs_context", build)
    person = user(1)
    person.login_name, person.user_type = "secretary", "TEACHER"
    db = MagicMock()
    db.execute.return_value.all.return_value = [(1, Row(id=4, role_code="COLLEGE_ADMIN"))]
    org, cache = Row(id=12), {}
    assert service._scoped_holders(db, [person], "COLLEGE", org, "academicAffairs.program.review", cache=cache) == [person]
    assert service._scoped_holders(db, [person], "COLLEGE", org, "academicAffairs.grade.collegeReview", cache=cache) == [person]
    assert build.call_count == 1
    # 下一次请求即时看到撤权；即便误复用同一字典，跨学校也不能复用身份事实。
    assert not service._scoped_holders(db, [person], "COLLEGE", org, "academicAffairs.program.review", cache={})
    tenant[0] = 2
    assert not service._scoped_holders(db, [person], "COLLEGE", org, "academicAffairs.program.review", cache=cache)
    assert build.call_count == 3


def test_scoped_holders_reuses_guard_role_pairs_without_skipping_scope_or_fresh_reads(monkeypatch):
    from app.core import affairs_security
    from app.services import system_role_shadow_service as shadow
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard

    tenant = [1]
    permission = "academicAffairs.program.review"
    monkeypatch.setattr(service, "_tid", lambda: tenant[0])
    monkeypatch.setattr(guard._core, "_tid", lambda: tenant[0])
    monkeypatch.setattr(shadow, "published_system_role_permissions", lambda db, code: {permission})
    monkeypatch.setattr(affairs_security, "build_affairs_context", lambda actor, db: Row(
        scope_type="COLLEGE", college_ids={12} if actor["userId"] == "1" else {99},
        permission_codes={permission}))
    first, second = user(1), user(2)
    first.login_name = "first"
    second.login_name = "second"
    first.user_type = second.user_type = "TEACHER"
    role = Row(id=4, role_code="COLLEGE_ADMIN", role_type="SYSTEM")
    db = MagicMock()
    db.execute.return_value.all.return_value = [(1, role), (2, role)]
    cache = {}
    assert guard._runtime_permission_holder_ids(db, permission, cache=cache) == [1, 2]
    assert service._scoped_holders(db, [first], "COLLEGE", Row(id=12), permission, cache=cache) == [first]
    assert service._scoped_holders(db, [second], "COLLEGE", Row(id=12), permission, cache=cache) == []
    assert service._scoped_holders(db, [first, second], "COLLEGE", Row(id=12), permission, cache=cache) == [first]
    assert service._scoped_holders(db, [first], "COLLEGE", Row(id=12), "other.permission", cache=cache) == []
    assert db.execute.call_count == 1  # 不同候选集合不再重复读取同租户角色关系。

    db.execute.return_value.all.return_value = []  # 新请求已撤销角色，不能沿用旧请求结果。
    fresh_cache = {}
    assert guard._runtime_permission_holder_ids(db, permission, cache=fresh_cache) == []
    assert service._scoped_holders(db, [first], "COLLEGE", Row(id=12), permission, cache=fresh_cache) == []
    assert db.execute.call_count == 2
    service._scoped_holders(db, [first], "COLLEGE", Row(id=12), permission, cache={})
    service._scoped_holders(db, [first], "COLLEGE", Row(id=12), permission)
    assert db.execute.call_count == 4  # 缺少显式角色缓存及默认无缓存均沿原查询。

    tenant[0] = 2
    db.execute.return_value.all.return_value = []
    assert service._scoped_holders(db, [first], "COLLEGE", Row(id=12), permission, cache=cache) == []
    assert db.execute.call_count == 5  # 旧租户缓存不可跨校使用。


def test_permission_holders_request_cache_preserves_roles_permissions_and_tenants(monkeypatch):
    from app.core import permissions
    from app.services import system_role_shadow_service as shadow
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard

    tenant = [1]
    monkeypatch.setattr(guard._core, "_tid", lambda: tenant[0])
    monkeypatch.setattr(permissions, "ROLE_PERMISSIONS", {})
    published = MagicMock(side_effect=lambda db, role: {"read.a"} if role == "FIRST" else {"read.b"})
    monkeypatch.setattr(shadow, "published_system_role_permissions", published)
    match = MagicMock(wraps=permissions._match)
    monkeypatch.setattr(permissions, "_match", match)
    first = Row(id=10, role_code="FIRST", role_type="SYSTEM")
    second = Row(id=11, role_code="SECOND", role_type="SYSTEM")
    custom = Row(id=12, role_code="CUSTOM_LOCAL", role_type="CUSTOM")
    db = MagicMock()
    db.execute.return_value.all.return_value = [(1, first), (2, first), (3, second), (4, custom)]
    db.execute.return_value.__iter__.return_value = iter([(12, "read.b")])
    cache = {}
    result = guard._runtime_permission_holder_ids(db, "read.a", cache=cache)
    assert result == [1, 2]
    assert match.call_count == 3  # Two users of the same role share only the permission match.
    result.append(999)
    assert guard._runtime_permission_holder_ids(db, "read.a", cache=cache) == [1, 2]
    assert match.call_count == 3 and published.call_count == 2
    assert guard._runtime_permission_holder_ids(db, "read.b", cache=cache) == [3, 4]
    assert match.call_count == 6 and published.call_count == 2
    assert db.execute.call_count == 2
    # Reusing a dictionary across tenants must never reuse another school's holders.
    tenant[0] = 2
    db.execute.return_value.all.return_value = [(8, second)]
    assert guard._runtime_permission_holder_ids(db, "read.a", cache=cache) == []
    assert guard._runtime_permission_holder_ids(db, "read.b", cache=cache) == [8]
    assert published.call_count == 3


def test_permission_holders_new_requests_and_uncached_commands_see_revocation(monkeypatch):
    from app.services import system_role_shadow_service as shadow
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard

    monkeypatch.setattr(guard._core, "_tid", lambda: 1)
    published = MagicMock(side_effect=[{"read.a"}, set(), {"read.a"}, set()])
    monkeypatch.setattr(shadow, "published_system_role_permissions", published)
    db = MagicMock()
    db.execute.return_value.all.return_value = [(1, Row(id=10, role_code="FIRST", role_type="SYSTEM"))]
    assert guard._runtime_permission_holder_ids(db, "read.a", cache={}) == [1]
    assert guard._runtime_permission_holder_ids(db, "read.a", cache={}) == []
    assert guard._runtime_permission_holder_ids(db, "read.a") == [1]
    assert guard._runtime_permission_holder_ids(db, "read.a") == []
    assert published.call_count == 4 and db.execute.call_count == 4
