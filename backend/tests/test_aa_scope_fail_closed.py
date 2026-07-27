"""受限教务身份未配置范围时不得通过主动传 collegeId 扩大权限。"""
from types import SimpleNamespace

import pytest


def test_empty_restricted_scope_is_rejected():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_stats_facade as service

    scope = SimpleNamespace(all=False, college_ids=set(), class_ids=set(), blocked=True)
    with pytest.raises(AppException) as exc:
        service._validate_college_param(scope, 10)

    assert exc.value.http_status == 403


def test_outside_college_is_rejected():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_stats_facade as service

    scope = SimpleNamespace(all=False, college_ids={1, 2}, class_ids={11}, blocked=False)
    with pytest.raises(AppException):
        service._validate_college_param(scope, 99)


def test_allowed_college_passes():
    from app.modules.academic_affairs.services import academic_affairs_stats_facade as service

    scope = SimpleNamespace(all=False, college_ids={1, 2}, class_ids={11}, blocked=False)
    service._validate_college_param(scope, 2)


def test_tenant_all_passes_without_ranges():
    from app.modules.academic_affairs.services import academic_affairs_stats_facade as service

    scope = SimpleNamespace(all=True, college_ids=set(), class_ids=set(), blocked=False)
    service._validate_college_param(scope, 999)


def test_router_package_uses_fail_closed_stats_public_service():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_stats_service.__name__.endswith(
        "academic_affairs_stats_public_service"
    )


def test_teacher_workload_detail_is_self_only(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_stats_public_service as service

    monkeypatch.setattr(service, "_precheck", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service._legacy,
        "workload_detail",
        lambda _user, teacher_key, _college_id, _page, _page_size: ([teacher_key], 1),
    )
    user = {
        "currentRoleCode": "ACADEMIC_TEACHER",
        "loginName": "T001",
        "userId": "u_T001",
        "activeContextId": "ctx_T001",
    }

    with pytest.raises(AppException) as exc:
        service.workload_detail(user, "T002")
    assert exc.value.http_status == 403

    items, total = service.workload_detail(user, "T001")
    assert items == ["T001"]
    assert total == 1
