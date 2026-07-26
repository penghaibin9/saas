"""学工四端终态安全门目标测试。

只覆盖本分支新增安全边界，不运行教务、实习、毕设等无关模块。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


TID = 1000000000000000001
MB = "/api/v1/mobile"


def _teacher_token(*, student_no: str = "") -> dict:
    from app.core.security import create_access_token

    payload = {
        "userId": "db-90001",
        "loginName": "teacher-with-student-fields",
        "realName": "测试教师",
        "userType": "TEACHER",
        "currentRoleCode": "COUNSELOR",
        "tenantId": str(TID),
        "activeContextId": "ctx",
        "clientType": "MP",
    }
    if student_no:
        payload["studentNo"] = student_no
    return {"Authorization": "Bearer " + create_access_token(payload)}


def _seed_student(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile

    db = get_sessionmaker()()
    cls = SchoolClass(
        tenant_id=TID,
        major_id=1,
        class_name="终态守卫测试班",
        grade="2026",
        status="ACTIVE",
    )
    db.add(cls)
    db.flush()
    student = StudentProfile(
        tenant_id=TID,
        student_no="FEG001",
        real_name="终态守卫学生",
        class_id=cls.id,
        gender="M",
        current_stage="CAMPUS",
        student_status="NORMAL",
        status="ACTIVE",
    )
    db.add(student)
    db.commit()
    sid = int(student.id)
    db.close()
    return sid


def test_teacher_cannot_enter_student_self_routes_even_with_student_number(client, db_mode):
    _seed_student(db_mode)
    headers = _teacher_token(student_no="FEG001")

    report = client.get(f"{MB}/affairs/second-class/report", headers=headers)
    assert report.status_code == 403

    transfers = client.get(f"{MB}/affairs/dorm/transfers/my", headers=headers)
    assert transfers.status_code == 403


def test_unknown_teacher_mobile_read_and_write_permissions_are_fail_closed():
    from app.services import affairs_four_end_contract as contract

    for method in ("GET", "POST"):
        required = contract._teacher_permissions(
            "/api/v1/mobile/teacher/affairs/future-unregistered-action",
            method,
        )
        assert "__AFFAIRS_MOBILE_WRITE_NOT_REGISTERED__" in required

    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/affairs", "GET",
    ) == ("studentAffairs.dashboard.view",)


def test_terminal_guard_normalizes_mounted_route_path():
    from app.services.affairs_four_end_terminal_guard import _runtime_path

    assert _runtime_path("/mobile/teacher/affairs/leaves/1/approve") == (
        "/api/v1/mobile/teacher/affairs/leaves/1/approve"
    )
    assert _runtime_path("/api/v1/mobile/teacher/affairs/leaves/1/approve") == (
        "/api/v1/mobile/teacher/affairs/leaves/1/approve"
    )


def test_terminal_guard_rejects_unregistered_mounted_teacher_read_and_write_routes():
    from fastapi import APIRouter
    from app.services.affairs_four_end_terminal_guard import _assert_teacher_routes_registered

    router = APIRouter()

    @router.get("/mobile/teacher/affairs/future-unregistered-read")
    def unsafe_read():
        return {"ok": True}

    @router.post("/mobile/teacher/affairs/future-unregistered-write")
    def unsafe_write():
        return {"ok": True}

    with pytest.raises(RuntimeError, match="权限矩阵不一致"):
        _assert_teacher_routes_registered(router)


def test_mobile_permission_codes_are_all_present_in_pc_catalog():
    from app.services.affairs_four_end_terminal_guard import (
        _DIRECT_PERMISSION_CODES,
        _MOBILE_CATALOG_CODES,
    )

    root = Path(__file__).resolve().parents[2]
    source = (root / "frontend/src/modules/studentAffairs/config/permissionCatalog.js").read_text(
        encoding="utf-8",
    )
    pc_codes = set(re.findall(r"permission\('([^']+)'", source))
    direct_codes = {code for codes in _DIRECT_PERMISSION_CODES.values() for code in codes}

    assert _MOBILE_CATALOG_CODES <= pc_codes
    assert direct_codes <= pc_codes


def test_teacher_mobile_write_routes_never_use_only_view_permission():
    from app.api.v1.router import api_router
    from app.services import affairs_four_end_contract as contract
    from app.services.affairs_four_end_terminal_guard import (
        _DIRECT_PERMISSION_CODES,
        _is_read_only_code,
        _is_teacher_mobile_path,
        _runtime_path,
    )

    failures = []
    for route in api_router.routes:
        path = _runtime_path(getattr(route, "path", ""))
        if not _is_teacher_mobile_path(path):
            continue
        for method in set(getattr(route, "methods", set()) or set()):
            if method in ("GET", "HEAD", "OPTIONS"):
                continue
            codes = _DIRECT_PERMISSION_CODES.get(path) or contract._teacher_permissions(path, method)
            if not codes or all(_is_read_only_code(code) for code in codes):
                failures.append(f"{method} {path}: {codes}")
    assert failures == []


def test_mental_statistics_and_individual_detail_permissions_are_separated():
    from app.services import affairs_four_end_contract as contract

    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/mental-stats", "GET",
    ) == ("studentAffairs.stats.view",)
    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/mental/123", "GET",
    ) == ("studentAffairs.risk.psyDetail.view",)
    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/mental/123", "POST",
    ) == ("studentAffairs.mental.manage",)
