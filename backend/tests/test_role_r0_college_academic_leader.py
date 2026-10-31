"""文档 2 R0 第①步：新增学院教务（COLLEGE_ACADEMIC）、收窄校领导（LEADER）。

纯单元：只读代码默认权限与权限目录，不连库。发布模板一致性见
test_role_r0_template_publish_mysql.py。
"""
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.services.saas_role_templates import ROLE_TEMPLATE_BY_CODE, resolve_role_code
from app.services.system_role_shadow_service import (
    active_tenant_permission_codes,
    expected_system_role_permissions,
)

_HIGH_RISK_TOKENS = (
    "review", "Review", "approve", "publish", "archive", "export", "import",
    "delete", "final", "restore", "return", "lock", "viewSensitive",
)


def _user(role):
    return {"userId": "u-r0", "tenantId": "t-r0", "currentRoleCode": role, "userType": "TEACHER"}


def test_college_academic_is_a_college_scoped_preset_role():
    template = ROLE_TEMPLATE_BY_CODE["COLLEGE_ACADEMIC"]
    assert template["roleName"] == "学院教务"
    assert template["defaultScope"] == "COLLEGE"
    assert resolve_role_code("学院教务") == "COLLEGE_ACADEMIC"


def test_college_academic_template_snapshot_has_no_review_or_publish_power():
    codes = set(expected_system_role_permissions("COLLEGE_ACADEMIC"))
    academic = {code for code in codes if code.startswith("academicAffairs.")}
    assert len(academic) == 39
    assert {
        "academicAffairs.teachingTask.assign", "academicAffairs.program.manage",
        "academicAffairs.program.submit", "academicAffairs.statusChange.apply",
        "academicAffairs.warning.handle", "student.profile.create", "student.profile.update",
    } <= codes
    risky = sorted(code for code in academic if any(token in code for token in _HIGH_RISK_TOKENS))
    assert risky == []
    assert "student.profile.restore" not in codes
    assert "academicAffairs.grade.scheme.manage" in codes
    assert "academicAffairs.grade.policy.manage" not in codes
    assert "academicAffairs.exam.arrange" not in codes
    for code in ("academicAffairs.term.manage", "academicAffairs.schedule.edit", "academicAffairs.grade.input"):
        assert code not in codes


@pytest.mark.parametrize("code", [
    "academicAffairs.grade.collegeReview", "academicAffairs.grade.publish",
    "academicAffairs.scheduleChange.collegeReview", "academicAffairs.statusChange.collegeReview",
    "academicAffairs.program.publish", "academicAffairs.graduation.collegeReview",
    "academicAffairs.roster.export", "student.profile.restore",
])
def test_college_academic_is_denied_review_publish_and_export(code):
    assert has_permission(_user("COLLEGE_ACADEMIC"), code) is False


def test_leader_keeps_only_dashboard_and_stats_in_academic_affairs():
    codes = set(expected_system_role_permissions("LEADER"))
    academic = {code for code in codes if code.startswith("academicAffairs.")}
    assert academic == {
        "academicAffairs.dashboard.view", "academicAffairs.stats.view",
        "academicAffairs.stats.snapshot.view",
    }


def test_leader_non_academic_part_stays_read_only_and_unchanged_in_shape():
    universe = set(active_tenant_permission_codes())
    old_read = {
        code for code in universe
        if (code.endswith(".view") or code.endswith(".stat")) and not code.startswith("academicAffairs.")
    }
    codes = set(expected_system_role_permissions("LEADER"))
    non_academic = {code for code in codes if not code.startswith("academicAffairs.")}
    assert non_academic - old_read <= {"workbench.home.view", "approval.todo.view", "workbench.message.view"}
    assert old_read <= non_academic
    assert not any(code.split(".")[-1] in {"manage", "create", "handle", "approve"} for code in non_academic)


@pytest.mark.parametrize("code", [
    "academicAffairs.roster.view", "academicAffairs.registration.view",
    "academicAffairs.term.view", "academicAffairs.grade.view", "academicAffairs.statusChange.view",
])
def test_leader_cannot_open_academic_business_pages(code):
    assert has_permission(_user("LEADER"), code) is False


def _college_ctx(monkeypatch, college_ids, scope="COLLEGE"):
    ctx = SimpleNamespace(scope_type=scope, college_ids=set(college_ids))
    monkeypatch.setattr("app.core.affairs_security.build_affairs_context", lambda user, db=None: ctx)


def test_college_academic_course_write_is_limited_to_own_college(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_course_service as course

    _college_ctx(monkeypatch, {11})
    course._check_college_scope(None, _user("COLLEGE_ACADEMIC"), 11)
    with pytest.raises(AppException):
        course._check_college_scope(None, _user("COLLEGE_ACADEMIC"), 22)


def test_college_role_without_college_scope_is_denied_course_write(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_course_service as course

    _college_ctx(monkeypatch, set(), scope="NONE")
    with pytest.raises(AppException):
        course._check_college_scope(None, _user("COLLEGE_ACADEMIC"), 11)


def test_graduation_reads_follow_live_scope_guard_for_college_academic(monkeypatch):
    """毕业资格读侧在运行时由 graduation_scope_guard 按数据范围收敛（不看角色名）。"""
    import app.main  # noqa: F401  安装运行时守卫
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as graduation

    monkeypatch.setattr(
        "app.modules.academic_affairs.services.academic_affairs_graduation_scope_guard.build_affairs_context",
        lambda user, db=None: SimpleNamespace(scope_type="COLLEGE", college_ids={11}),
    )
    assert graduation._college_scope_ids(None, _user("COLLEGE_ACADEMIC")) == {11}


@pytest.mark.parametrize("role", ["COLLEGE_ACADEMIC", "COLLEGE_ADMIN"])
def test_teacher_schedule_college_scope_uses_trusted_context(monkeypatch, role):
    from app.modules.academic_affairs.services import academic_affairs_schedule_teacher_relation_guard as guard

    _college_ctx(monkeypatch, {11})
    user = {**_user(role), "collegeIds": [22], "dataScope": "SCHOOL"}
    assert guard._college_ids(None, user) == {11}


@pytest.mark.parametrize("role", ["COLLEGE_ACADEMIC", "COLLEGE_ADMIN"])
@pytest.mark.parametrize("scope,ids", [("NONE", set()), ("COLLEGE", set()), ("TENANT_ALL", {11})])
def test_teacher_schedule_college_scope_never_falls_back_to_school(monkeypatch, role, scope, ids):
    from app.modules.academic_affairs.services import academic_affairs_schedule_teacher_relation_guard as guard

    _college_ctx(monkeypatch, ids, scope)
    with pytest.raises(AppException) as exc:
        guard._college_ids(None, _user(role))
    assert exc.value.code == "NO_DATA_SCOPE"


@pytest.mark.parametrize("role", ["ACADEMIC_ADMIN", "SCHOOL_ADMIN", "ACADEMIC_TEACHER"])
def test_teacher_schedule_retains_other_roles_query_rules(role):
    from app.modules.academic_affairs.services import academic_affairs_schedule_teacher_relation_guard as guard

    assert guard._college_ids(None, _user(role)) is None
    if role == "ACADEMIC_TEACHER":
        guard._check_query_scope(_user(role), "u-r0")
        with pytest.raises(AppException):
            guard._check_query_scope(_user(role), "another-teacher")
    else:
        guard._check_query_scope(_user(role), "another-teacher")


def test_school_admin_permission_universe_is_unchanged():
    assert set(expected_system_role_permissions("SCHOOL_ADMIN")) == set(active_tenant_permission_codes())
