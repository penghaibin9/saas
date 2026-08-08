from __future__ import annotations

import inspect

from app.core.affairs_security import _derive_keys
from app.services.affairs_mental_service import psy_scope_ids


def test_same_real_name_does_not_create_same_staff_identity_keys():
    left = {
        "userId": "u_teacher_a",
        "loginName": "teacher_a",
        "activeContextId": "ctx_teacher_a",
        "realName": "同名老师",
    }
    right = {
        "userId": "u_teacher_b",
        "loginName": "teacher_b",
        "activeContextId": "ctx_teacher_b",
        "realName": "同名老师",
    }

    left_keys = _derive_keys(left)
    right_keys = _derive_keys(right)

    assert "同名老师" not in left_keys
    assert "同名老师" not in right_keys
    assert left_keys.isdisjoint(right_keys)


def test_psychology_scope_queries_stable_teacher_key_only():
    source = inspect.getsource(psy_scope_ids)

    assert "TeacherStudentScope.teacher_key.in_(keys)" in source
    assert "TeacherStudentScope.teacher_name.in_(keys)" not in source
    assert 'u.get("realName")' not in source
    assert "if not keys:" in source
    assert "return set()" in source
