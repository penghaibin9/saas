#!/usr/bin/env python3
"""Seed an ephemeral MySQL database and issue short-lived capacity tokens.

This tool is intended only for GitHub Actions/local test environments. It never creates
production credentials and never prints tokens to stdout. Teacher V3 T9 also seeds one
Student360/employment object plus per-context messages so every newly gated route has a real
server object to read in self-contained CI.

Teacher test userIds are synthetic positive integers. That is intentional: the production
message identity resolver can use them directly, so the capacity run measures the inbox query
instead of paying an artificial User-table lookup/CRC fallback on every request.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import sys
import os
from ephemeral_capacity_guard import assert_ephemeral_target
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select


TENANT_ID = 1000000000000000973
STUDENT_NO = "PERF-STU-001"
TEACHER_MESSAGE_SOURCE = "capacity-gate-teacher"
TEACHER_USER_ID_BASE = 8_500_000_000


def _teacher_user_id(index: int) -> str:
    return str(TEACHER_USER_ID_BASE + int(index))


def _teacher_context(index: int) -> str:
    return f"perf-teacher-context-{index:04d}"


def seed_runtime_data(token_count: int) -> tuple[int, int, int]:
    assert_ephemeral_target(os.environ)
    if not 1 <= token_count <= 1000:
        raise ValueError("token-count must be between 1 and 1000")
    from app.core.config import settings
    assert_ephemeral_target({**os.environ, "DATABASE_URL": settings.DATABASE_URL,
        "TEST_DATABASE_URL": settings.TEST_DATABASE_URL, "APP_ENV": settings.APP_ENV,
        "DEPLOYMENT_MODE": settings.DEPLOYMENT_MODE})
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent, StudentProfile, UnifiedMessage

    ensure_capacity_commercial_fixture()
    db = get_sessionmaker()()
    try:
        for index in range(1, token_count + 1):
            student = db.scalar(
                select(StudentProfile).where(
                    StudentProfile.tenant_id == TENANT_ID,
                    StudentProfile.student_no == _student_no(index),
                )
            )
            if student is None:
                student = StudentProfile(
                    tenant_id=TENANT_ID,
                    student_no=_student_no(index),
                    real_name="容量测试学生",
                    grade="2026",
                    current_stage="ON_CAMPUS",
                    student_status="NORMAL",
                    status="ACTIVE",
                )
                db.add(student)
                db.flush()

            employment = db.scalar(
                select(EmpStudent).where(
                    EmpStudent.tenant_id == TENANT_ID,
                    EmpStudent.student_id == student.id,
                    EmpStudent.is_deleted.is_(False),
                )
            )
            if employment is None:
                # EmpStudent is a domain model, not a CommonMixin status-bearing row. Keep the seed
                # aligned to the real ORM contract: lifecycle truth is record_status/verify_status.
                employment = EmpStudent(
                    tenant_id=TENANT_ID,
                    student_id=student.id,
                    student_no=student.student_no,
                    name=student.real_name,
                    grade=student.grade,
                    destination_type="EMPLOYED",
                    company_name="容量测试企业",
                    job_title="容量测试岗位",
                    verify_status="PENDING_VERIFY",
                    material_status="SUBMITTED",
                    record_status="ACTIVE",
                )
                db.add(employment)
                db.flush()

        # A rerun against the same local DB must stay deterministic instead of multiplying messages.
        db.execute(delete(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TENANT_ID,
            UnifiedMessage.source_module == TEACHER_MESSAGE_SOURCE,
        ))
        now = datetime.utcnow()
        message_count = 0
        specs = (
            ("SYSTEM", "SYSTEM", "NORMAL", "系统通知"),
            ("BUSINESS", "BUSINESS", "NORMAL", "学生动态"),
            ("EMERGENCY", "EMERGENCY", "EMERGENCY", "风险预警"),
            ("TODO_NOTICE", "TODO", "IMPORTANT", "催办提醒"),
        )
        for index in range(1, token_count + 1):
            receiver_uid = int(_teacher_user_id(index))
            context = _teacher_context(index)
            for offset, (message_type, category, priority, title) in enumerate(specs):
                db.add(UnifiedMessage(
                    tenant_id=TENANT_ID,
                    receiver_id=receiver_uid,
                    receiver_user_id=receiver_uid,
                    receiver_type="STAFF",
                    receiver_context_key=context,
                    source_module=TEACHER_MESSAGE_SOURCE,
                    message_type=message_type,
                    category=category,
                    priority=priority,
                    title=f"{title} {index}",
                    content="Teacher V3 T9 本地容量门禁消息，不含真实人员信息。",
                    status="UNREAD",
                    require_ack=message_type == "EMERGENCY",
                    delivered_at=now - timedelta(seconds=offset),
                    created_at=now - timedelta(seconds=offset),
                ))
                message_count += 1
        db.commit()
        return int(student.id), int(employment.id), message_count
    finally:
        db.close()


def _student_no(index: int) -> str:
    return f"PERF-STU-{int(index):04d}"


def _student_token(index: int) -> str:
    assert_ephemeral_target(os.environ)
    from app.core.security import create_access_token
    return create_access_token(
        {
            "userId": f"perf-student-{index:04d}",
            "loginName": _student_no(index),
            "realName": "容量测试学生",
            "userType": "STUDENT",
            "tid": "perf-local",
            "capacitySynthetic": True,
            "tenantId": str(TENANT_ID),
            "activeContextId": f"perf-student-context-{index:04d}",
            "currentRoleCode": "STUDENT",
            "clientType": "MP",
            "studentNo": _student_no(index),
        },
        expires_in=3600,
    )


def _teacher_token(index: int) -> str:
    assert_ephemeral_target(os.environ)
    from app.core.security import create_access_token
    # Fresh CI databases intentionally do not bootstrap the platform-owned published
    # SCHOOL_ADMIN RoleTemplate. In DB mode SCHOOL_ADMIN therefore fails closed by design and is
    # not a valid synthetic capacity identity. LEADER is the least-privileged built-in school
    # role that legitimately covers this gate's read-only cross-domain V3 routes (`*.view`) plus
    # the personal message inbox, while resolve_teacher_scope still treats it as tenant-wide.
    return create_access_token(
        {
            "userId": _teacher_user_id(index),
            "loginName": f"PERF-TEACHER-{index:04d}",
            "realName": "容量测试教师",
            "userType": "TEACHER",
            "tid": "perf-local",
            "capacitySynthetic": True,
            "tenantId": str(TENANT_ID),
            "activeContextId": _teacher_context(index),
            "currentRoleCode": "LEADER",
            "clientType": "MP",
        },
        expires_in=3600,
    )


def write_tokens(out_dir: Path, token_count: int) -> None:
    assert_ephemeral_target(os.environ)
    if not 1 <= token_count <= 1000:
        raise SystemExit("token-count must be between 1 and 1000")
    out_dir.mkdir(parents=True, exist_ok=True)
    students = [_student_token(index) for index in range(1, token_count + 1)]
    teachers = [_teacher_token(index) for index in range(1, token_count + 1)]
    (out_dir / "student-tokens.json").write_text(
        json.dumps(students, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "teacher-tokens.json").write_text(
        json.dumps(teachers, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")



CAPACITY_ORDER_REMARK = "Local capacity owned paid prerequisite; synthetic test data only"


def _activate_owned_capacity_order(platform, commercial) -> str:
    """Resume this fixture's exact order; never replace a foreign contract or FEATURES."""
    orders = platform.list_orders(tenant_id=TENANT_ID)
    if len(orders) > 1:
        raise ValueError("ambiguous capacity commercial history")
    if orders:
        order = orders[0]
        if not (order.get("remark") == CAPACITY_ORDER_REMARK
                and order.get("packageCode") == "professional"
                and order.get("orderType") == "NEW"
                and order.get("status") in {"unpaid", "paid"}
                and order.get("amount") == 1):
            raise ValueError("capacity fixture refuses to replace a foreign commercial order")
    else:
        state = commercial.commercial_state(TENANT_ID)
        if state.get("packageCode", "trial") != "trial":
            raise ValueError("capacity fixture refuses existing formal commercial state")
        order = platform.create_order({
            "tenantId": str(TENANT_ID), "packageCode": "professional", "orderType": "NEW",
            "durationDays": 30, "amount": 1, "remark": CAPACITY_ORDER_REMARK,
        })
    state = commercial.commercial_state(TENANT_ID)
    def verified(value):
        return (value.get("verified") is True and value.get("authoritySource") == "PAID_ORDER"
                and value.get("commercialOrderNo") == order["orderNo"]
                and all(value.get("features", {}).get(key) is True for key in ("internship", "employment")))
    if verified(state):
        return str(order["orderNo"])
    paid = platform.order_action(
        order["orderNo"], "mark-paid" if order["status"] == "unpaid" else "repair-activation",
        expected_version=int(order["version"]), reason="本地临时容量库正式订单授权夹具",
    )
    if paid.get("repairTaskRequired"):
        paid = platform.order_action(order["orderNo"], "repair-activation",
            expected_version=int(paid["version"]), reason="本地临时容量库修复授权激活")
    if not paid.get("tenantActivated") or not verified(commercial.commercial_state(TENANT_ID)):
        raise ValueError("capacity commercial prerequisite failed authoritative verification")
    return str(order["orderNo"])


def ensure_capacity_commercial_fixture() -> None:
    """The exact loopback test schema only; all payment facts remain synthetic and local."""
    assert_ephemeral_target(os.environ)
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import platform_service
    from app.services.module_access_service import module_access_state

    with get_sessionmaker()() as db:
        tenant = db.get(Tenant, TENANT_ID)
        if tenant is None:
            db.add(Tenant(id=TENANT_ID, tenant_code="perf-local",
                school_name="本地临时容量验收学校", status="ACTIVE"))
            db.commit()
        elif tenant.tenant_code != "perf-local" or tenant.status != "ACTIVE" or tenant.is_deleted:
            raise ValueError("capacity tenant ID has foreign ownership or inactive status")
    _activate_owned_capacity_order(platform_service, commercial)
    for key in ("internship", "employment"):
        if module_access_state(TENANT_ID, key).get("allowed") is not True:
            raise ValueError("capacity fixture cannot bypass school module access: " + key)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local capacity data")
    parser.add_argument("--out", type=Path, default=ROOT / "performance/secrets")
    parser.add_argument("--token-count", type=int, default=1)
    args = parser.parse_args()
    assert_ephemeral_target(os.environ)
    if not 1 <= args.token_count <= 1000:
        raise SystemExit("token-count must be between 1 and 1000")
    student_id, employment_id, message_count = seed_runtime_data(args.token_count)
    write_tokens(args.out, args.token_count)
    print(
        f"seeded_students={args.token_count} synthetic_identity_pool=true "
        f"teacher_messages={message_count} student_tokens={args.token_count} "
        f"teacher_tokens={args.token_count}"
    )


if __name__ == "__main__":
    main()
