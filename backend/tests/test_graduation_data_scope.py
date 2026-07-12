"""毕业设计业务关系数据范围单测（不连数据库）。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.context import set_current_user
from app.core.exceptions import AppException
from app.models import GraduationDefenseGroup, GraduationStudent
from app.services.graduation_scope_service import accessible_student_ids, assert_student_access, can_access_student


class FakeDb:
    def __init__(self, *, scalar_result=None, group=None, students=None):
        self.scalar_result = scalar_result
        self.group = group
        self.students = students or []

    def scalar(self, _statement):
        return self.scalar_result

    def get(self, _model, _identity):
        return self.group

    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: self.students)


@pytest.fixture(autouse=True)
def _clear_user_context():
    set_current_user(None)
    yield
    set_current_user(None)


def _student(**values):
    defaults = dict(id=101, tenant_id=1001, name="学生甲", advisor_name="导师甲",
                    defense_group_id=None, is_deleted=False)
    defaults.update(values)
    return GraduationStudent(**defaults)


def _login(role, real_name):
    set_current_user({"currentRoleCode": role, "userType": "TEACHER", "realName": real_name})


def test_school_and_graduation_admin_have_tenant_scope():
    for role in ("SCHOOL_ADMIN", "GRADUATION_ADMIN"):
        _login(role, "管理员")
        assert can_access_student(FakeDb(), _student())


def test_mentor_only_sees_owned_students():
    _login("GD_MENTOR", "导师甲")
    assert can_access_student(FakeDb(), _student(advisor_name="导师甲"))
    assert not can_access_student(FakeDb(), _student(advisor_name="导师乙"))


def test_reviewer_requires_assigned_review_relation():
    _login("GD_REVIEWER", "评阅甲")
    assert can_access_student(FakeDb(scalar_result=9001), _student())
    assert not can_access_student(FakeDb(scalar_result=None), _student())


def test_defense_roles_are_limited_to_their_group_relation():
    group = GraduationDefenseGroup(id=8, tenant_id=1001, group_name="第一组", secretary="秘书甲",
                                    chair="主席甲", members_json=["专家甲", "专家乙"],
                                    student_count=1, published=False, is_deleted=False)
    student = _student(defense_group_id=8)

    _login("GD_DEFENSE_SECRETARY", "秘书甲")
    assert can_access_student(FakeDb(group=group), student)
    _login("GD_DEFENSE_SECRETARY", "秘书乙")
    assert not can_access_student(FakeDb(group=group), student)

    _login("GD_DEFENSE_EXPERT", "专家甲")
    assert can_access_student(FakeDb(group=group), student)
    _login("GD_DEFENSE_EXPERT", "组外专家")
    assert not can_access_student(FakeDb(group=group), student)


def test_missing_organization_scope_fails_closed():
    _login("GD_COLLEGE_ADMIN", "学院负责人")
    assert not can_access_student(FakeDb(), _student())
    with pytest.raises(AppException) as exc:
        assert_student_access(FakeDb(), _student(), "student.detail")
    assert exc.value.http_status == 403


def test_list_and_stats_share_the_same_accessible_student_ids():
    students = [
        _student(id=1, advisor_name="导师甲"),
        _student(id=2, advisor_name="导师乙"),
        _student(id=3, advisor_name="导师甲"),
    ]
    _login("GD_MENTOR", "导师甲")
    assert accessible_student_ids(FakeDb(students=students), 1001) == [1, 3]

    _login("GD_COLLEGE_ADMIN", "范围缺失的学院负责人")
    assert accessible_student_ids(FakeDb(students=students), 1001) == []
