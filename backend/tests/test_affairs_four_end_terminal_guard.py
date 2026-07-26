"""学工四端终态安全门目标测试。

只覆盖本分支新增安全边界，不运行教务、实习、毕设等无关模块。
"""
from __future__ import annotations

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

    # 真实总览路径仍使用冻结的总览查看权限。
    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/affairs", "GET"
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

    with pytest.raises(RuntimeError, match="缺少权限登记"):
        _assert_teacher_routes_registered(router)
