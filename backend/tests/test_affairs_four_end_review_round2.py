"""学工中心四端第二轮独立盲审门禁。

只覆盖本分支四端契约与安全边界；数据库用例继续使用仓库统一 MySQL db_mode。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_all_teacher_affairs_mobile_writes_have_explicit_permission(client):
    """新增教师学工写路由未登记 permissionCode 时必须在测试阶段失败。"""
    from app.services import affairs_four_end_contract as contract

    directly_guarded_prefixes = (
        "/api/v1/mobile/teacher/affairs/appeals/",
        "/api/v1/mobile/teacher/affairs/activities/",
    )
    failures = []
    for route in client.app.routes:
        path = getattr(route, "path", "") or ""
        methods = set(getattr(route, "methods", set()) or set())
        if not path.startswith("/api/v1/mobile/teacher/affairs"):
            continue
        for method in methods - {"GET", "HEAD", "OPTIONS"}:
            if path.startswith(directly_guarded_prefixes):
                continue
            codes = contract._teacher_permissions(path, method)
            if (
                not codes
                or codes == ("studentAffairs.dashboard.view",)
                or "__AFFAIRS_MOBILE_WRITE_NOT_REGISTERED__" in codes
            ):
                failures.append(f"{method} {path}: {codes}")
    assert failures == []


def test_mental_statistics_permission_cannot_open_individual_detail():
    from app.services import affairs_four_end_contract as contract

    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/mental-stats", "GET"
    ) == ("studentAffairs.stats.view",)
    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/mental/123", "GET"
    ) == ("studentAffairs.risk.psyDetail.view",)


def test_mental_detail_role_and_student_scope_live_in_formal_service():
    from app.services.affairs_mental_service import _can_view_detail

    # 辅导员只有逐生授权命中时可见；学工处管理员默认不在原始明细角色内。
    assert _can_view_detail({"currentRoleCode": "COUNSELOR"}, 1, {1}) is True
    assert _can_view_detail({"currentRoleCode": "COUNSELOR"}, 2, {1}) is False
    assert _can_view_detail({"currentRoleCode": "STUDENT_AFFAIRS_ADMIN"}, 1, None) is False


def test_explicit_version_can_never_be_replaced_by_request_context():
    from app.core.exceptions import AppException
    from app.services import affairs_four_end_contract as contract
    from app.services.affairs_four_end_review_guard import _expected_version

    t_path = contract._REQUEST_PATH.set("/api/v1/mobile/teacher/affairs/risk/1/close")
    t_method = contract._REQUEST_METHOD.set("POST")
    t_version = contract._REQUEST_VERSION.set(7)
    try:
        assert _expected_version(contract, 7) == 7
        with pytest.raises(AppException) as exc:
            _expected_version(contract, 6)
        assert exc.value.code == "APPROVAL_VERSION_CONFLICT"
    finally:
        contract._REQUEST_VERSION.reset(t_version)
        contract._REQUEST_METHOD.reset(t_method)
        contract._REQUEST_PATH.reset(t_path)


def test_application_payload_hash_is_canonical_and_sensitive_to_changes():
    from app.services.affairs_student_atomic_service import _payload_sha256

    a = {"batchId": 1, "statement": "家庭情况说明", "members": [{"name": "甲", "age": 50}]}
    b = {"members": [{"age": 50, "name": "甲"}], "statement": "家庭情况说明", "batchId": 1}
    c = {**a, "statement": "修改后的家庭情况说明"}
    assert _payload_sha256(a) == _payload_sha256(b)
    assert _payload_sha256(a) != _payload_sha256(c)
    assert len(_payload_sha256(a)) == 64


def test_unknown_gender_never_enters_single_gender_dorm():
    from app.services.affairs_dorm_reliability_service import _strict_gender_ok

    assert _strict_gender_ok("MIXED", None) is True
    assert _strict_gender_ok("MALE", None) is False
    assert _strict_gender_ok("FEMALE", "UNKNOWN") is False
    assert _strict_gender_ok("MALE", "M") is True
    assert _strict_gender_ok("FEMALE", "F") is True


def test_activity_scope_matching_is_fail_closed():
    from app.services.affairs_activity_reliability_service import _activity_matches

    assert _activity_matches(SimpleNamespace(scope_type="SCHOOL", scope_ref=None), set(), set())
    assert _activity_matches(SimpleNamespace(scope_type="CLASS", scope_ref="C1"), {"C1"}, set())
    assert not _activity_matches(SimpleNamespace(scope_type="CLASS", scope_ref="C2"), {"C1"}, set())
    assert _activity_matches(SimpleNamespace(scope_type="COLLEGE", scope_ref="10"), set(), {"10"})
    assert not _activity_matches(SimpleNamespace(scope_type="UNKNOWN", scope_ref=""), set(), set())


def test_appeal_dashboard_read_path_does_not_reconcile_or_write():
    from pathlib import Path

    source = Path("app/services/affairs_appeal_dashboard_service.py").read_text(encoding="utf-8")
    assert "reconcile_appeal_todos" not in source
    assert ".commit(" not in source
