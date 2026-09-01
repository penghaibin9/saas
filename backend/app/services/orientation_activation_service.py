"""Public newcomer self-activation: admission proof -> password -> WeChat bind -> login.

The admission ledger remains the candidate authority. Successful activation materializes the
existing StudentProfile/User/StudentAccountLink authorities in one transaction; no parallel
"pre-student account" is introduced.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.context import get_request_meta
from app.core.exceptions import AppException
from app.core.field_crypto import decrypt_field
from app.db.session import db_enabled, get_sessionmaker
from app.models import (
    OrientationActivationChallenge,
    OrientationAuditTrail,
    OrientationBatch,
    OrientationStudent,
    Tenant,
    User,
)
from app.services.auth_service_db import build_login_result
from app.services.db_service import audit_insert_in_session
from app.services.orientation_enrollment_finalize_service import OrientationEnrollmentFinalizeService

_LAST_SIX = re.compile(r"^[0-9X]{6}$")
_VERIFY_TTL_SECONDS = 10 * 60


def _secret() -> bytes:
    return (settings.JWT_SECRET_KEY or settings.JWT_SECRET).encode("utf-8")


def _digest(scope: str, value: str) -> str:
    return hmac.new(_secret(), f"{scope}\n{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def _allow(label: str, limit: int, window: int) -> bool:
    # Reuse the authentication challenge store: production/staging fail closed when Redis is down.
    from app.services.password_reset_service import _allow as auth_allow
    return auth_allow(f"orientation-activation:{label}", limit, window)


def _ip_hash() -> str:
    ip = str((get_request_meta() or {}).get("ip") or "unknown")
    return _digest("orientation-activation-ip", ip)[:24]


def _uniform_delay(started_at: float) -> None:
    remaining = started_at + 0.18 - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def _active_account(db, student: OrientationStudent):
    if not student.student_id:
        return None
    from app.services import student_account_link_service as links
    user_id = links.get_user_id_by_student(
        db, tenant_id=int(student.tenant_id), student_id=int(student.student_id),
    )
    if not user_id:
        return None
    return db.scalars(select(User).where(
        User.id == int(user_id), User.tenant_id == student.tenant_id,
        User.user_type == "STUDENT", User.status == "ACTIVE",
        User.is_deleted.is_(False),
    )).first()


def verify_admission_identity(*, tenant_code: str, admission_no: str,
                              id_card_last6: str, client_nonce: str) -> dict:
    """Verify admission number + ID-card suffix and issue a one-time durable challenge."""
    if not db_enabled():
        raise AppException("AUTH_STORE_UNAVAILABLE", "新生激活服务暂时不可用", http_status=503)
    started_at = time.monotonic()
    tenant_code = str(tenant_code or "").strip()
    admission_no = str(admission_no or "").strip()
    last_six = str(id_card_last6 or "").strip().upper()
    nonce = str(client_nonce or "").strip()
    if not tenant_code or not admission_no or not _LAST_SIX.fullmatch(last_six) or len(nonce) < 8:
        raise AppException("VALIDATION_ERROR", "请完整填写学校代码、录取号和身份证后六位")

    subject = _digest("orientation-activation-subject", f"{tenant_code.lower()}\n{admission_no.upper()}")[:32]
    if (not _allow(f"verify-subject:{subject}", 5, 15 * 60)
            or not _allow(f"verify-ip:{_ip_hash()}", 30, 15 * 60)):
        raise AppException("RATE_LIMITED", "核验尝试过于频繁，请 15 分钟后再试", http_status=429)

    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(
            Tenant.tenant_code == tenant_code,
            Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")),
            Tenant.is_deleted.is_(False),
        )).first()
        student = None
        batch = None
        if tenant:
            student = db.scalars(select(OrientationStudent).where(
                OrientationStudent.tenant_id == tenant.id,
                OrientationStudent.admission_no == admission_no,
                OrientationStudent.record_status == "ACTIVE",
                OrientationStudent.is_deleted.is_(False),
            ).with_for_update()).first()
            if student:
                batch = db.scalars(select(OrientationBatch).where(
                    OrientationBatch.id == student.batch_id,
                    OrientationBatch.tenant_id == tenant.id,
                    OrientationBatch.status == "ACTIVE",
                    OrientationBatch.is_deleted.is_(False),
                )).first()
        plain_id_card = decrypt_field(student.id_card_encrypted) if student else None
        identity_matches = bool(
            student and batch and plain_id_card and len(str(plain_id_card)) >= 6
            and hmac.compare_digest(str(plain_id_card)[-6:].upper(), last_six)
        )
        if not identity_matches:
            _uniform_delay(started_at)
            raise AppException("UNAUTHORIZED", "录取信息核验失败，请检查填写内容或联系招生老师")

        now = datetime.utcnow()
        if batch.report_start_date and now < batch.report_start_date:
            raise AppException("DATA_CONFLICT", "该迎新批次尚未开放自助激活", http_status=409)
        if batch.report_end_date and now > batch.report_end_date:
            raise AppException("DATA_CONFLICT", "该迎新批次自助激活已结束，请联系学校处理", http_status=409)
        existing_account = _active_account(db, student)
        if existing_account or student.identity_status == "LINKED":
            raise AppException(
                "DATA_CONFLICT", "该录取信息已激活，请直接登录",
                details={"alreadyActivated": True,
                         "loginName": existing_account.login_name if existing_account else (student.student_no or "")},
                http_status=409,
            )
        if not str(student.student_no or "").strip():
            raise AppException(
                "DATA_CONFLICT", "学校尚未为该录取记录分配学号，请联系招生老师后再试",
                details={"studentNumberPending": True}, http_status=409,
            )

        token = "oa_" + secrets.token_urlsafe(32)
        token_hash = _digest("orientation-activation-token", token)
        nonce_hash = _digest("orientation-activation-nonce", nonce)
        challenge = db.scalars(select(OrientationActivationChallenge).where(
            OrientationActivationChallenge.tenant_id == tenant.id,
            OrientationActivationChallenge.orientation_student_id == student.id,
            OrientationActivationChallenge.is_deleted.is_(False),
        ).with_for_update()).first()
        if challenge is None:
            challenge = OrientationActivationChallenge(
                tenant_id=tenant.id, orientation_student_id=student.id,
                token_hash=token_hash, client_nonce_hash=nonce_hash,
                status="VERIFIED", expires_at=now + timedelta(seconds=_VERIFY_TTL_SECONDS),
                verified_at=now, created_by=0,
            )
            db.add(challenge)
        else:
            challenge.token_hash = token_hash
            challenge.client_nonce_hash = nonce_hash
            challenge.status = "VERIFIED"
            challenge.expires_at = now + timedelta(seconds=_VERIFY_TTL_SECONDS)
            challenge.verified_at = now
            challenge.completed_at = None
            challenge.client_request_id = None
            challenge.bound_user_id = None
            challenge.wechat_bound = False
            challenge.version = int(challenge.version or 0) + 1
        db.add(OrientationAuditTrail(
            tenant_id=tenant.id, biz_type="STUDENT", biz_id=str(student.id),
            action="新生自助身份核验通过", operator="新生本人", role_name="PUBLIC",
            detail="录取号与身份证后六位核验通过；未记录证件尾号",
            occurred_at=now, created_by=0,
        ))
        db.commit()
        _uniform_delay(started_at)
        return {
            "verified": True,
            "activationToken": token,
            "expiresIn": _VERIFY_TTL_SECONDS,
            "candidate": {
                "name": student.name,
                "admissionNo": student.admission_no,
                "studentNo": student.student_no,
                "collegeName": student.college_name or "",
                "majorName": student.major_name or "",
                "className": student.class_name or "",
                "batchName": batch.batch_name,
            },
        }
    finally:
        db.close()


def complete_activation(*, activation_token: str, client_nonce: str, new_password: str,
                        client_request_id: str, wx_token: str | None,
                        client_type: str = "STUDENT_MINI") -> dict:
    """Consume the proof once, materialize authorities, bind WeChat, and return login tokens."""
    if not db_enabled():
        raise AppException("AUTH_STORE_UNAVAILABLE", "新生激活服务暂时不可用", http_status=503)
    token = str(activation_token or "").strip()
    nonce = str(client_nonce or "").strip()
    request_id = str(client_request_id or "").strip()
    client = str(client_type or "STUDENT_MINI").strip().upper()
    if len(token) < 20 or len(nonce) < 8 or not (12 <= len(request_id) <= 100):
        raise AppException("VALIDATION_ERROR", "激活请求无效，请重新核验录取身份")
    from app.services.system_config_service import get_int
    min_len = get_int("SEC_PASSWORD_MIN_LEN", 8)
    if len(new_password or "") < min_len:
        raise AppException("VALIDATION_ERROR", f"密码长度至少 {min_len} 位")
    if client not in {"STUDENT_MINI", "STUDENT_H5", "MP"}:
        raise AppException("VALIDATION_ERROR", "新生激活客户端类型无效")
    if not _allow(f"complete-ip:{_ip_hash()}", 20, 15 * 60):
        raise AppException("RATE_LIMITED", "激活提交过于频繁，请稍后再试", http_status=429)
    if settings.is_prod and not wx_token:
        raise AppException("WECHAT_AUTH_REQUIRED", "请从微信小程序重新进入并完成微信绑定")

    token_hash = _digest("orientation-activation-token", token)
    nonce_hash = _digest("orientation-activation-nonce", nonce)
    openid = None
    if wx_token:
        from app.services.wx_auth_service import openid_from_bind_token
        openid = openid_from_bind_token(wx_token)

    db = get_sessionmaker()()
    try:
        challenge = db.scalars(select(OrientationActivationChallenge).where(
            OrientationActivationChallenge.token_hash == token_hash,
            OrientationActivationChallenge.is_deleted.is_(False),
        ).with_for_update()).first()
        if challenge is None or not hmac.compare_digest(challenge.client_nonce_hash, nonce_hash):
            raise AppException("UNAUTHORIZED", "激活凭证无效或已过期，请重新核验录取身份")
        if challenge.status == "COMPLETED":
            if challenge.client_request_id != request_id or not challenge.bound_user_id:
                raise AppException("UNAUTHORIZED", "激活凭证已使用，请直接登录")
            account = db.get(User, int(challenge.bound_user_id))
            if not account or account.is_deleted or account.status != "ACTIVE":
                raise AppException("DATA_CONFLICT", "已激活账号当前不可用，请联系学校管理员")
            result = build_login_result(db, account, client_type=client)
            result["activation"] = {
                "completed": True, "idempotent": True,
                "wechatBound": bool(challenge.wechat_bound),
                "orientationPath": "/pages/student/orientation/index",
            }
            return result
        now = datetime.utcnow()
        if challenge.status != "VERIFIED" or challenge.expires_at <= now:
            challenge.status = "EXPIRED"
            db.commit()
            raise AppException("UNAUTHORIZED", "激活凭证已过期，请重新核验录取身份")

        student = db.scalars(select(OrientationStudent).where(
            OrientationStudent.id == challenge.orientation_student_id,
            OrientationStudent.tenant_id == challenge.tenant_id,
            OrientationStudent.record_status == "ACTIVE",
            OrientationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student or not student.student_no:
            raise AppException("DATA_CONFLICT", "录取记录已变化，请联系学校确认")
        if _active_account(db, student) or student.identity_status == "LINKED":
            raise AppException("DATA_CONFLICT", "该录取信息已由其他请求激活，请直接登录")

        profile = OrientationEnrollmentFinalizeService._profile(
            # The roster already carries a validated, tenant-bound org path.  This public
            # proof flow has no staff data-scope actor; passing None avoids inventing one.
            db, student, {"studentNo": student.student_no}, None,
            operation_label="新生自助激活建档",
        )
        account, _ = OrientationEnrollmentFinalizeService._account(
            db, profile, student, {"studentNo": student.student_no},
            source="ORIENTATION_SELF_ACTIVATION", operation_label="新生自助激活",
            initial_password=new_password,
        )
        if openid:
            from app.services.wx_auth_service import bind_openid_in_session
            bind_openid_in_session(db, openid, account)

        from app.services.orientation_flow_service import set_student_step_status
        student.student_id = profile.id
        student.identity_status = "LINKED"
        set_student_step_status(
            db, student, "ACTIVATE", "DONE", status_source="PROCESS_FACT",
            source_biz_id=f"orientation-self-activate:{request_id}",
        )
        if student.blocked_step == "ACTIVATE":
            student.blocked_step = None
            student.blocked_reason = None
        student.version = int(student.version or 0) + 1

        challenge.status = "COMPLETED"
        challenge.completed_at = now
        challenge.client_request_id = request_id
        challenge.bound_user_id = account.id
        challenge.wechat_bound = bool(openid)
        challenge.version = int(challenge.version or 0) + 1
        db.add(OrientationAuditTrail(
            tenant_id=student.tenant_id, biz_type="ACTIVATE", biz_id=str(student.id),
            action="新生自助激活账号", operator=student.name, role_name="STUDENT",
            detail=f"studentId={profile.id}; userId={account.id}; wechatBound={bool(openid)}",
            occurred_at=now, created_by=account.id,
        ))
        audit_insert_in_session(
            db, "ORIENTATION_SELF_ACTIVATION", "orientation",
            {"wechatBound": bool(openid), "clientType": client}, "SUCCESS",
            tenant_id=student.tenant_id, resource_id=str(student.id),
        )
        db.commit()
        account = db.get(User, int(account.id))
        result = build_login_result(db, account, client_type=client)
        result["activation"] = {
            "completed": True, "idempotent": False,
            "wechatBound": bool(openid),
            "orientationStudentId": str(student.id),
            "studentNo": profile.student_no,
            "orientationPath": "/pages/student/orientation/index",
        }
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
