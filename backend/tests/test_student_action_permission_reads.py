import pytest

from app.services import student_service


@pytest.mark.parametrize('grants,expected', [
    ({'*'}, ['CREATE', 'EDIT_IDENTITY', 'EXPORT', 'RESTORE', 'VIEW', 'VOID']),
    (set(), []),
    ({'student.profile.view'}, ['VIEW']),
    ({'student.profile.manage'}, ['CREATE', 'EDIT_IDENTITY', 'VOID']),
    ({'student.profile.update'}, ['EDIT_IDENTITY', 'VOID']),
    ({'student.profile.create'}, ['CREATE']),
    ({'student.profile.restore'}, ['RESTORE']),
    ({'student.export'}, ['EXPORT']),
    ({'student.profile.view', 'student.export'}, ['EXPORT', 'VIEW']),
])
def test_student_actions_reuse_only_the_current_response_base_check(monkeypatch, grants, expected):
    calls = []
    user = {'tenantId': 'school-a', 'userId': 'teacher-a'}
    monkeypatch.setattr(student_service, 'get_current_user_ctx', lambda: user)

    def permission(actual_user, code):
        assert actual_user is user
        calls.append(code)
        return code in grants

    monkeypatch.setattr(student_service, 'has_permission', permission)
    assert student_service._supported_actions() == expected
    assert calls.count('*') == 1
    grants.clear()
    assert student_service._supported_actions() == []
    assert calls.count('*') == 2, '下一次读取必须重新校验撤权后的权限'
