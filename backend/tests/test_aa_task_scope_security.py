"""教学任务教师写操作必须使用稳定 teacher_key，历史缺失归属不得 fail-open。"""
from types import SimpleNamespace

import pytest


def _task(key):
    return SimpleNamespace(teacher_key=key)


def _teacher(login="teacher01", uid="db-101", role="ACADEMIC_TEACHER"):
    return {
        "userId": uid,
        "loginName": login,
        "currentRoleCode": role,
        "userType": "TEACHER",
    }


def test_unbound_historical_task_is_closed_to_normal_teacher():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    with pytest.raises(Exception) as exc:
        service._check_teacher_scope(_task(None), _teacher())

    assert "稳定教师工号" in str(exc.value)


def test_other_teacher_task_is_closed():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    with pytest.raises(Exception) as exc:
        service._check_teacher_scope(_task("teacher02"), _teacher("teacher01"))

    assert "不在您的授课范围" in str(exc.value)


def test_own_task_is_allowed():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    service._check_teacher_scope(_task("teacher01"), _teacher("teacher01"))


def test_academic_admin_can_repair_unbound_historical_task():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    service._check_teacher_scope(_task(None), _teacher(role="ACADEMIC_ADMIN"))
