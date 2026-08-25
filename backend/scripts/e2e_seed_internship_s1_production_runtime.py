from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.models import EmpCompany, StudentProfile, Tenant, UnifiedMessage, User
from app.modules.internship.services import internship_enterprise_auth_service as enterprise_auth

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
STUDENT_LOGIN = "E2E20260001"
ENTERPRISE_LOGIN = "s1_enterprise"
ENTERPRISE_PHONE = "13900138088"
ENTERPRISE_PASSWORD = "S1Enterprise@2026"
MESSAGE_TITLE = "S1 Production Runtime 深链通知"
OUTPUT = Path("../e2e/runtime/internship-s1-production-runtime.json")


def assert_safe_target() -> None:
    app_env = str(os.getenv("APP_ENV") or "").lower()
    deploy = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if app_env in {"prod", "production"} or deploy in {"prod", "production", "staging"}:
        raise SystemExit("S1 seed refuses production/staging runtime")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    parsed = urlparse(db_url)
    if not db_url or not any(x in db_url.lower() for x in ("e2e", "test")):
        raise SystemExit("S1 seed requires an e2e/test database")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("S1 seed only accepts a local database")


def load_json(path: str) -> dict:
    return json.loads(Path(path).resolve().read_text(encoding="utf-8"))


def main() -> int:
    assert_safe_target()
    base = load_json("../e2e/runtime/internship-fixture.json")
    enterprise = load_json("../e2e/runtime/internship-enterprise-position-fixture.json")

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TENANT_ID)
        if not tenant or tenant.tenant_code != TENANT_CODE or tenant.is_deleted:
            raise RuntimeError("sandbox-school tenant missing")
        company = db.get(EmpCompany, int(base["companyId"]))
        if not company or company.tenant_id != TENANT_ID or company.is_deleted:
            raise RuntimeError("S1 base company missing")
        student_profile = db.scalar(select(StudentProfile).where(
            StudentProfile.tenant_id == TENANT_ID,
            StudentProfile.student_no == STUDENT_LOGIN,
            StudentProfile.is_deleted.is_(False),
        ))
        student_user = db.scalar(select(User).where(
            User.tenant_id == TENANT_ID,
            User.login_name == STUDENT_LOGIN,
            User.is_deleted.is_(False),
        ))
        if not student_profile or not student_user:
            raise RuntimeError("S1 student account/profile missing")

        # Keep the message deterministic per run and avoid stale same-title rows in a rerun DB.
        old_messages = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TENANT_ID,
            UnifiedMessage.receiver_user_id == student_user.id,
            UnifiedMessage.title == MESSAGE_TITLE,
            UnifiedMessage.is_deleted.is_(False),
        )).all()
        for old in old_messages:
            old.is_deleted = True

        message = UnifiedMessage(
            tenant_id=TENANT_ID,
            receiver_id=student_profile.id,
            receiver_user_id=student_user.id,
            receiver_type="STUDENT",
            receiver_context_key="GLOBAL",
            source_module="internship",
            title=MESSAGE_TITLE,
            content="S1 production-runtime smoke：从真实消息中心进入已登记学生端路由。",
            message_type="BUSINESS",
            status="UNREAD",
            priority="NORMAL",
            category="BUSINESS",
            delivered_at=datetime.utcnow(),
            delivery_status="DELIVERED",
            require_ack=False,
            action_key="student.leave.detail",
            action_params_json={"leaveId": "1"},
        )
        db.add(message)
        db.commit()
        db.refresh(message)
    finally:
        db.close()

    # Use the production enterprise invitation/activation services rather than directly
    # manufacturing an ACTIVE member. The helper itself still runs only against isolated test DB.
    set_tenant({"tenantId": str(TENANT_ID)})
    try:
        invitation = enterprise_auth.issue_company_invite(
            int(enterprise["campaignId"]),
            company_id=int(base["companyId"]),
            login_name=ENTERPRISE_LOGIN,
            real_name="S1 企业管理员",
            phone=ENTERPRISE_PHONE,
            member_role="COMPANY_ADMIN",
            invite_source="MANUAL",
            actor_user_id=None,
        )
        enterprise_auth.accept_invite(
            tenant_code=TENANT_CODE,
            token=invitation["inviteToken"],
            phone=ENTERPRISE_PHONE,
            password=ENTERPRISE_PASSWORD,
        )
    finally:
        set_tenant(None)

    payload = {
        "productExactSha": os.getenv("E2E_PRODUCT_EXACT_SHA") or "",
        "tenantCode": TENANT_CODE,
        "batchId": base["batchId"],
        "batchName": base["batchName"],
        "messageId": str(message.id),
        "messageTitle": MESSAGE_TITLE,
        "enterprise": {
            "tenantCode": TENANT_CODE,
            "loginName": ENTERPRISE_LOGIN,
            "password": ENTERPRISE_PASSWORD,
            "campaignId": enterprise["campaignId"],
            "campaignName": enterprise["campaignName"],
            "companyId": base["companyId"],
            "companyName": base["companyName"],
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[internship-s1-seed] ready:", json.dumps({
        **payload,
        "enterprise": {k: v for k, v in payload["enterprise"].items() if k != "password"},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
