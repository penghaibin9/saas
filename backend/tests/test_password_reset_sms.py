from __future__ import annotations

import secrets

import pytest
from sqlalchemy import select


@pytest.fixture()
def reset_account(db_mode, monkeypatch):
    from app.core.config import settings
    from app.core.field_crypto import encrypt_field, hash_sensitive
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import PhoneLoginBinding, Role, SysConfig, Tenant, User, UserRole
    from app.services.phone_login_service import phone_lookup
    from app.services import auth_challenge_service, password_reset_service

    auth_challenge_service.reset_for_tests()
    password_reset_service.reset_for_tests()
    old = (settings.SMS_ENABLED, settings.SMS_PROVIDER, settings.SMS_TEMPLATE_PASSWORD_RESET)
    monkeypatch.setattr(settings, "SENSITIVE_SEARCH_HMAC_KEY", "ab" * 32)
    settings.SMS_ENABLED = "true"
    settings.SMS_PROVIDER = "mock"
    settings.SMS_TEMPLATE_PASSWORD_RESET = "test-template"
    db = get_sessionmaker()()
    suffix = secrets.token_hex(5)
    student_phone = f"138{secrets.randbelow(100_000_000):08d}"
    teacher_phone = f"139{secrets.randbelow(100_000_000):08d}"
    tenant = Tenant(tenant_code=f"reset-{suffix}", school_name="重置测试学校", status="ACTIVE")
    db.add(tenant)
    db.flush()
    student = User(
        tenant_id=tenant.id, login_name=f"S-{suffix}", real_name="测试学生",
        user_type="STUDENT", status="ACTIVE", password_hash=hash_password("OldPass123"),
        phone_encrypted=encrypt_field(student_phone), phone_hash=hash_sensitive(student_phone, "phone"),
    )
    teacher = User(
        tenant_id=tenant.id, login_name=f"T-{suffix}", real_name="测试教师",
        user_type="TEACHER", status="ACTIVE", password_hash=hash_password("OldPass123"),
        phone_encrypted=encrypt_field(teacher_phone), phone_hash=hash_sensitive(teacher_phone, "phone"),
    )
    student_role = Role(tenant_id=tenant.id, role_code="STUDENT", role_name="学生")
    teacher_role = Role(tenant_id=tenant.id, role_code="ACADEMIC_TEACHER", role_name="任课教师")
    db.add_all([student, teacher, student_role, teacher_role])
    db.flush()
    db.add_all([
        UserRole(tenant_id=tenant.id, user_id=student.id, role_id=student_role.id, status="ACTIVE"),
        UserRole(tenant_id=tenant.id, user_id=teacher.id, role_id=teacher_role.id, status="ACTIVE"),
        PhoneLoginBinding(
            tenant_id=tenant.id,
            user_id=student.id,
            state="VERIFIED",
            phone_ciphertext=encrypt_field(student_phone),
            active_phone_lookup=phone_lookup(tenant.id, student_phone),
            version=1,
        ),
        PhoneLoginBinding(
            tenant_id=tenant.id,
            user_id=teacher.id,
            state="VERIFIED",
            phone_ciphertext=encrypt_field(teacher_phone),
            active_phone_lookup=phone_lookup(tenant.id, teacher_phone),
            version=1,
        ),
        SysConfig(tenant_id=tenant.id, config_key="SEC_PHONE_RECOVERY_ENABLED", value_text="1"),
    ])
    db.commit()
    result = {
        "tenantId": tenant.id, "tenantCode": tenant.tenant_code,
        "userId": student.id, "loginName": student.login_name,
        "teacherId": teacher.id, "teacherLoginName": teacher.login_name,
    }
    db.close()
    yield result
    settings.SMS_ENABLED, settings.SMS_PROVIDER, settings.SMS_TEMPLATE_PASSWORD_RESET = old
    auth_challenge_service.reset_for_tests()
    password_reset_service.reset_for_tests()


@pytest.fixture()
def delivered_code(monkeypatch):
    """Capture only the local mock adapter input; the HTTP response stays secret-free."""
    from app.services.notification import sms_service

    captured = {}
    original = sms_service.notify_password_reset

    def capture(tenant_id, phone, code):
        captured["value"] = str(code)
        return original(tenant_id, phone, code)

    monkeypatch.setattr(sms_service, "notify_password_reset", capture)
    return captured


def _captcha(client, tenant_code, login_name, nonce, client_type="PC"):
    response = client.post("/api/v1/auth/captcha", json={
        "scene": "PASSWORD_RESET", "tenantCode": tenant_code, "loginName": login_name,
        "clientNonce": nonce, "clientType": client_type,
    }).json()
    assert response["code"] == 0
    return response["data"]


def test_student_can_reset_password_and_old_refreshes_are_revoked(client, reset_account, delivered_code):
    from app.core.security import verify_password
    from app.db.session import get_sessionmaker
    from app.models import NotificationTask, SecurityAuditLog, User

    nonce = "pc-reset-nonce-123"
    captcha = _captcha(client, reset_account["tenantCode"], reset_account["loginName"], nonce)
    requested = client.post("/api/v1/auth/password-reset/request", json={
        "tenantCode": reset_account["tenantCode"], "loginName": reset_account["loginName"],
        "captchaId": captcha["captchaId"], "captchaCode": captcha["devCode"],
        "clientNonce": nonce, "clientType": "PC",
    }).json()
    assert requested["code"] == 0
    assert requested["data"]["accepted"] is True
    assert "devCode" not in requested["data"]
    assert len(delivered_code["value"]) == 6

    verified = client.post("/api/v1/auth/password-reset/verify", json={
        "requestId": requested["data"]["requestId"], "code": delivered_code["value"],
        "clientNonce": nonce, "clientType": "PC",
    }).json()
    assert verified["code"] == 0 and verified["data"]["verified"] is True

    confirmed = client.post("/api/v1/auth/password-reset/confirm", json={
        "resetToken": verified["data"]["resetToken"],
        "newPassword": "NewPass456", "confirmPassword": "NewPass456",
    }).json()
    assert confirmed["code"] == 0 and confirmed["data"]["reloginRequired"] is True

    db = get_sessionmaker()()
    try:
        user = db.get(User, reset_account["userId"])
        assert verify_password("NewPass456", user.password_hash)
        task = db.scalars(select(NotificationTask).where(
            NotificationTask.tenant_id == reset_account["tenantId"],
            NotificationTask.biz_type == "PASSWORD_RESET",
        )).first()
        assert task.payload_json == {"redacted": True, "keys": ["code"]}
        assert delivered_code["value"] not in str(task.payload_json)
        audit = db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == reset_account["tenantId"],
            SecurityAuditLog.action == "PASSWORD_RESET_SELF_SERVICE",
        )).first()
        assert audit is not None
    finally:
        db.close()

    replay = client.post("/api/v1/auth/password-reset/confirm", json={
        "resetToken": verified["data"]["resetToken"],
        "newPassword": "Another789", "confirmPassword": "Another789",
    }).json()
    assert replay["bizCode"] == "RESET_TOKEN_INVALID"


def test_wrong_code_is_limited(client, reset_account, delivered_code):
    nonce = "mini-reset-nonce-123"
    captcha = _captcha(client, reset_account["tenantCode"], reset_account["loginName"], nonce, "STUDENT_MINI")
    requested = client.post("/api/v1/auth/password-reset/request", json={
        "tenantCode": reset_account["tenantCode"], "loginName": reset_account["loginName"],
        "captchaId": captcha["captchaId"], "captchaCode": captcha["devCode"],
        "clientNonce": nonce, "clientType": "STUDENT_MINI",
    }).json()["data"]
    assert "devCode" not in requested and len(delivered_code["value"]) == 6
    for _ in range(5):
        response = client.post("/api/v1/auth/password-reset/verify", json={
            "requestId": requested["requestId"], "code": "000000",
            "clientNonce": nonce, "clientType": "STUDENT_MINI",
        }).json()
        assert response["bizCode"] == "RESET_CODE_INVALID"
    expired = client.post("/api/v1/auth/password-reset/verify", json={
        "requestId": requested["requestId"], "code": delivered_code["value"],
        "clientNonce": nonce, "clientType": "STUDENT_MINI",
    }).json()
    assert expired["bizCode"] == "RESET_CODE_INVALID"



def test_teacher_can_reset_password_from_teacher_entry(client, reset_account, delivered_code):
    from app.core.security import verify_password
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog, User

    nonce = "teacher-reset-nonce"
    login_name = reset_account["teacherLoginName"]
    captcha = _captcha(client, reset_account["tenantCode"], login_name, nonce, "TEACHER_MINI")
    requested = client.post("/api/v1/auth/password-reset/request", json={
        "tenantCode": reset_account["tenantCode"], "loginName": login_name,
        "captchaId": captcha["captchaId"], "captchaCode": captcha["devCode"],
        "clientNonce": nonce, "clientType": "TEACHER_MINI",
    }).json()
    assert requested["code"] == 0 and "devCode" not in requested["data"]
    assert len(delivered_code["value"]) == 6

    verified = client.post("/api/v1/auth/password-reset/verify", json={
        "requestId": requested["data"]["requestId"], "code": delivered_code["value"],
        "clientNonce": nonce, "clientType": "TEACHER_MINI",
    }).json()
    assert verified["code"] == 0

    confirmed = client.post("/api/v1/auth/password-reset/confirm", json={
        "resetToken": verified["data"]["resetToken"],
        "newPassword": "TeacherPass456", "confirmPassword": "TeacherPass456",
    }).json()
    assert confirmed["code"] == 0 and confirmed["data"]["reloginRequired"] is True

    db = get_sessionmaker()()
    try:
        teacher = db.get(User, reset_account["teacherId"])
        assert verify_password("TeacherPass456", teacher.password_hash)
        audit = db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == reset_account["tenantId"],
            SecurityAuditLog.action == "PASSWORD_RESET_SELF_SERVICE",
        )).first()
        assert audit is not None and audit.detail_json["userType"] == "TEACHER"
    finally:
        db.close()
