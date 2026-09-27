"""Yiyang C04 / G11 controlled student password reset acceptance."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

TID_A = 1000000000000000001
TID_B = 1000000000000000002
MENTOR_ID = 7001
OTHER_MENTOR_ID = 7002

MENTOR = {
    "tenantId": str(TID_A),
    "userId": str(MENTOR_ID),
    "realName": "指导教师甲",
    "userType": "TEACHER",
    "currentRoleCode": "INTERN_MENTOR",
}


@pytest.fixture()
def g11_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        AuditOutbox,
        College,
        InternshipAuditTrail,
        InternshipBatch,
        InternshipRecord,
        StudentAccountLink,
        StudentProfile,
        User,
    )

    old_url = settings.DATABASE_URL
    old_secret = settings.JWT_SECRET
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'g11.db').as_posix()}"
    settings.JWT_SECRET = "g11-test-secret-not-for-production"
    db_session._engine = None
    db_session._factory = None
    engine = db_session.get_engine()

    for table in (
        College.__table__,
        InternshipBatch.__table__,
        StudentProfile.__table__,
        User.__table__,
        StudentAccountLink.__table__,
        InternshipRecord.__table__,
        InternshipAuditTrail.__table__,
        AuditOutbox.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old_url
        settings.JWT_SECRET = old_secret
        db_session._engine = None
        db_session._factory = None


def _seed():
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (
        College,
        InternshipBatch,
        InternshipRecord,
        StudentAccountLink,
        StudentProfile,
        User,
    )

    db = get_sessionmaker()()
    try:
        college_a = College(
            tenant_id=TID_A, college_code="C-A", college_name="信息工程学院", status="ACTIVE"
        )
        college_b = College(
            tenant_id=TID_A, college_code="C-B", college_name="商学院", status="ACTIVE"
        )
        db.add_all([college_a, college_b])
        db.flush()

        batch_a = InternshipBatch(
            tenant_id=TID_A, batch_name="益阳G11批次", batch_no="YIYANG-G11",
            planned_count=3, status="RUNNING",
        )
        batch_b = InternshipBatch(
            tenant_id=TID_B, batch_name="外校G11批次", batch_no="OTHER-G11",
            planned_count=1, status="RUNNING",
        )
        db.add_all([batch_a, batch_b])
        db.flush()

        specs = [
            # key, tenant, college, advisor id, advisor name
            ("assigned", TID_A, college_a.id, MENTOR_ID, "指导教师甲"),
            ("same_college_unassigned", TID_A, college_a.id, OTHER_MENTOR_ID, "指导教师乙"),
            ("other_college", TID_A, college_b.id, OTHER_MENTOR_ID, "指导教师乙"),
            ("other_tenant", TID_B, None, MENTOR_ID, "指导教师甲"),
        ]
        out = {}
        for index, (key, tenant_id, college_id, advisor_id, advisor_name) in enumerate(specs, start=1):
            student = StudentProfile(
                tenant_id=tenant_id,
                student_no=f"G11-{index:03d}",
                real_name=f"G11学生{index}",
                college_id=college_id,
                current_stage="INTERNSHIP",
                student_status="NORMAL",
                status="ACTIVE",
            )
            db.add(student)
            db.flush()
            account = User(
                tenant_id=tenant_id,
                login_name=student.student_no,
                real_name=student.real_name,
                password_hash=hash_password("Old!Password123"),
                user_type="STUDENT",
                status="ACTIVE",
                must_change_password=False,
                credential_version=3,
            )
            db.add(account)
            db.flush()
            link = StudentAccountLink(
                tenant_id=tenant_id,
                student_id=student.id,
                user_id=account.id,
                link_status="ACTIVE",
                bound_login_name=account.login_name,
                bound_student_no=student.student_no,
                source="MANUAL",
            )
            db.add(link)
            batch = batch_a if tenant_id == TID_A else batch_b
            record = InternshipRecord(
                tenant_id=tenant_id,
                student_id=student.id,
                batch_id=batch.id,
                advisor_name=advisor_name,
                advisor_user_id=advisor_id,
                eligibility_status="QUALIFIED",
                destination_type="ASSIGNED",
                status="ONBOARD",
                risk_level="NONE",
            )
            db.add(record)
            db.flush()
            out[key] = {
                "student_id": student.id,
                "account_id": account.id,
                "record_id": record.id,
                "batch_id": batch.id,
                "account_version": int(account.version or 0),
                "credential_version": int(account.credential_version or 0),
            }
        db.commit()
        return out
    finally:
        db.close()


def _student_token(account_id: int, credential_version: int):
    from app.core.security import create_access_token
    return create_access_token({
        "userId": f"db-{account_id}",
        "tenantId": str(TID_A),
        "realName": "G11学生1",
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
        "credentialVersion": int(credential_version),
        "clientType": "STUDENT_MINI",
    })


def test_g11_only_assigned_student_can_be_reset_and_old_session_dies(g11_db):
    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.core.security import verify_password
    from app.db.session import get_sessionmaker
    from app.main import app
    from app.models import InternshipAuditTrail, User
    from app.modules.internship.services import internship_student_account_service as accounts

    set_tenant({"tenantId": str(TID_A)})
    set_current_user(MENTOR)
    seeded = _seed()
    assigned = seeded["assigned"]

    state = accounts.account_state(
        assigned["record_id"], MENTOR, batch_id=assigned["batch_id"])
    assert state["bound"] is True
    assert state["canReset"] is True
    assert state["accountVersion"] == assigned["account_version"]
    assert "G11-" not in state["loginNameMasked"] or "***" in state["loginNameMasked"]

    # Same-college but not assigned to this mentor must still be denied.
    for key in ("same_college_unassigned", "other_college"):
        target = seeded[key]
        with pytest.raises(AppException) as exc:
            accounts.reset_password(target["record_id"], {
                "batchId": str(target["batch_id"]),
                "expectedAccountVersion": target["account_version"],
                "reason": "学生本人反馈无法登录系统",
            }, MENTOR)
        assert exc.value.http_status == 403
        assert exc.value.code in {"NO_PERMISSION", "NO_DATA_SCOPE"}

    # Cross-school record must be indistinguishable from an unavailable record.
    other = seeded["other_tenant"]
    with pytest.raises(AppException) as exc:
        accounts.reset_password(other["record_id"], {
            "batchId": str(other["batch_id"]),
            "expectedAccountVersion": other["account_version"],
            "reason": "学生本人反馈无法登录系统",
        }, MENTOR)
    assert exc.value.http_status in {403, 404}

    old_token = _student_token(
        assigned["account_id"], assigned["credential_version"])

    reset = accounts.reset_password(assigned["record_id"], {
        "batchId": str(assigned["batch_id"]),
        "expectedAccountVersion": state["accountVersion"],
        "reason": "学生本人反馈忘记登录密码",
    }, MENTOR)
    temporary = reset["tempPassword"]
    assert temporary
    assert reset["mustChangePassword"] is True
    assert reset["reloginRequired"] is True
    assert reset["credentialVersion"] == assigned["credential_version"] + 1

    db = get_sessionmaker()()
    try:
        account = db.get(User, assigned["account_id"])
        assert account.must_change_password is True
        assert int(account.credential_version) == assigned["credential_version"] + 1
        assert verify_password(temporary, account.password_hash)
        assert not verify_password("Old!Password123", account.password_hash)

        trails = db.query(InternshipAuditTrail).filter_by(
            tenant_id=TID_A, target_type="ACCOUNT_RESET",
            action="STUDENT_PASSWORD_RESET",
        ).all()
        assert len(trails) == 1
        serialized = json.dumps(trails[0].detail_json, ensure_ascii=False)
        assert "忘记登录密码" in serialized
        assert temporary not in serialized
        assert "Old!Password123" not in serialized
        assert account.password_hash not in serialized
    finally:
        db.close()

    client = TestClient(app)

    # The access token that was valid before reset is now invalid server-side.
    old = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer " + old_token},
    )
    assert old.status_code == 401, old.text
    assert old.json()["bizCode"] == "UNAUTHORIZED"

    current_version = reset["credentialVersion"]
    current_token = _student_token(assigned["account_id"], current_version)

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer " + current_token},
    )
    assert me.status_code == 200, me.text
    assert me.json()["data"]["mustChangePassword"] is True

    # New credential epoch still cannot enter business APIs until the student changes password.
    blocked = client.get(
        "/api/v1/mobile/internship/context/my",
        headers={"Authorization": "Bearer " + current_token},
    )
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["bizCode"] == "PASSWORD_CHANGE_REQUIRED"

    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": "Bearer " + current_token},
        json={
            "currentPassword": temporary,
            "newPassword": "New!StudentPass456",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["success"] is True
    final_version = changed.json()["data"]["credentialVersion"]
    assert final_version == current_version + 1

    # The token used to perform the password change becomes stale immediately afterwards.
    stale_after_change = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer " + current_token},
    )
    assert stale_after_change.status_code == 401, stale_after_change.text

    db = get_sessionmaker()()
    try:
        account = db.get(User, assigned["account_id"])
        assert account.must_change_password is False
        assert int(account.credential_version) == final_version
        assert verify_password("New!StudentPass456", account.password_hash)
        trails = db.query(InternshipAuditTrail).filter_by(
            tenant_id=TID_A, target_type="ACCOUNT_RESET",
        ).order_by(InternshipAuditTrail.id).all()
        assert [row.action for row in trails] == [
            "STUDENT_PASSWORD_RESET", "STUDENT_PASSWORD_CHANGE"
        ]
        audit_text = json.dumps(
            [row.detail_json for row in trails], ensure_ascii=False)
        assert temporary not in audit_text
        assert "New!StudentPass456" not in audit_text
    finally:
        db.close()


def test_g11_routes_and_permission_contract():
    from app.main import app
    from app.core.permissions import has_permission

    paths = set(app.openapi().get("paths", {}))
    assert "/api/v1/mobile/teacher/internship/context/students/{record_id}/account" in paths
    assert "/api/v1/mobile/teacher/internship/context/students/{record_id}/reset-password" in paths
    assert "/api/v1/auth/change-password" in paths
    assert has_permission({"currentRoleCode": "INTERN_MENTOR"}, "internship.student.password.reset")
    assert not has_permission({"currentRoleCode": "COUNSELOR"}, "internship.student.password.reset")
