"""课堂考勤只能按稳定教师工号授权，姓名不得参与。"""
from types import SimpleNamespace

import pytest


def test_teacher_keys_exclude_real_name():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    keys = service._teacher_keys({
        "userId": "u_T001",
        "loginName": "T001",
        "realName": "张伟",
        "activeContextId": "ctx_T001",
    })

    assert "T001" in keys
    assert "张伟" not in keys


def test_same_name_teacher_cannot_open_other_session():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    attendance = SimpleNamespace(teacher_key="T002")
    user = {
        "currentRoleCode": "ACADEMIC_TEACHER",
        "userId": "u_T001",
        "loginName": "T001",
        "realName": "张伟",
    }

    with pytest.raises(AppException) as exc:
        service._check_owner(attendance, user)

    assert exc.value.http_status == 403


def test_missing_teacher_key_is_fail_closed_for_teacher():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    with pytest.raises(AppException) as exc:
        service._check_owner(
            SimpleNamespace(teacher_key=None),
            {"currentRoleCode": "ACADEMIC_TEACHER", "loginName": "T001"},
        )

    assert exc.value.http_status == 403
    assert "归属待教务处修复" in exc.value.message


def test_admin_can_repair_legacy_session_without_teacher_key():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    service._check_owner(
        SimpleNamespace(teacher_key=None),
        {"currentRoleCode": "ACADEMIC_ADMIN", "loginName": "aa_admin"},
    )


def test_primary_teacher_key_is_deterministic():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    user = {
        "userId": "u_T001",
        "loginName": "T001",
        "realName": "张伟",
        "activeContextId": "ctx_other",
    }
    assert service._primary_teacher_key(user) == "T001"
