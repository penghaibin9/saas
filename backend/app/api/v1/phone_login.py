"""本人号码办理；所有写入复用原登录主体、短信证明及事务服务。"""
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.field_crypto import mask_phone_encrypted
from app.core.response import success
from app.core.security import get_current_user, verify_password
from app.db.session import get_sessionmaker
from app.services.phone_login_service import create_pending_candidate_in_session

router = APIRouter(prefix="/auth")


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReauthenticateRequest(StrictRequest):
    purpose: Literal['BIND_PHONE', 'CHANGE_PHONE', 'REVOKE_PHONE']
    newPhone: str | None = Field(None, max_length=20)
    currentPassword: str = Field(..., min_length=1, max_length=128)
    clientNonce: str = Field(..., min_length=8, max_length=128)
    expectedBindingVersion: StrictInt = Field(..., ge=0)

    @model_validator(mode='after')
    def validate_target(self):
        from app.services.phone_login_service import normalize_login_phone
        if self.purpose == 'REVOKE_PHONE':
            if 'newPhone' in self.model_fields_set:
                raise ValueError('解绑不能指定新号码')
        else:
            self.newPhone = normalize_login_phone(self.newPhone)
        return self


class OperationRequest(StrictRequest):
    operationId: str = Field(..., min_length=20, max_length=100)
    clientNonce: str = Field(..., min_length=8, max_length=128)


class ChallengeRequest(OperationRequest):
    reauthTicket: str = Field(..., min_length=20, max_length=200)


class VerifyRequest(OperationRequest):
    code: str = Field(..., pattern=r'^[0-9]{6}$')


class ConfirmRequest(OperationRequest):
    verificationGrant: str = Field(..., min_length=20, max_length=200)
    expectedBindingVersion: StrictInt = Field(..., ge=0)


class RevokeRequest(ChallengeRequest):
    expectedBindingVersion: StrictInt = Field(..., ge=0)
    reason: str = Field(..., min_length=2, max_length=300)


class StatusRequest(StrictRequest):
    receiptToken: str = Field(..., min_length=20, max_length=200)
    clientNonce: str = Field(..., min_length=8, max_length=128)


@router.post('/phone-binding/reauthenticate')
def reauthenticate_phone(body: ReauthenticateRequest, user=Depends(get_current_user)):
    from app.services import phone_binding_service as svc
    return success(svc.reauthenticate(user, purpose=body.purpose, new_phone=body.newPhone,
        current_password=body.currentPassword, nonce=body.clientNonce, expected_version=body.expectedBindingVersion))


@router.post('/phone-binding/challenges')
def issue_phone_challenge(body: ChallengeRequest, user=Depends(get_current_user)):
    from app.services import phone_binding_service as svc
    return success(svc.challenge(user, operation_id=body.operationId, ticket=body.reauthTicket, nonce=body.clientNonce))


@router.post('/phone-binding/challenges/{challenge_id}/verify')
def verify_phone_challenge(challenge_id: str, body: VerifyRequest, user=Depends(get_current_user)):
    from app.services import phone_binding_service as svc
    return success(svc.verify_challenge(user, operation_id=body.operationId, challenge_id=challenge_id,
        code=body.code, nonce=body.clientNonce))


@router.post('/phone-binding/confirm')
def confirm_phone(body: ConfirmRequest, user=Depends(get_current_user),
                  idempotency_key: str = Header(..., alias='Idempotency-Key', min_length=1, max_length=128)):
    from app.services import phone_binding_service as svc
    return success(svc.confirm(user, operation_id=body.operationId, grant=body.verificationGrant,
        nonce=body.clientNonce, expected_version=body.expectedBindingVersion, idempotency_key=idempotency_key))


@router.post('/phone-binding/revoke')
def revoke_phone(body: RevokeRequest, user=Depends(get_current_user),
                 idempotency_key: str = Header(..., alias='Idempotency-Key', min_length=1, max_length=128)):
    from app.services import phone_binding_service as svc
    return success(svc.confirm(user, operation_id=body.operationId, grant=body.reauthTicket,
        nonce=body.clientNonce, expected_version=body.expectedBindingVersion, idempotency_key=idempotency_key,
        revoke=True, reason=body.reason))


@router.post('/phone-binding/operation-status')
def phone_operation_status(body: StatusRequest):
    # Read-only scoped receipt survives epoch revocation. Never grants account access.
    from app.services import phone_binding_service as svc
    return success(svc.operation_status(receipt_token=body.receiptToken, nonce=body.clientNonce))


def _subject(user_ctx: dict) -> tuple[int, int]:
    raw_id, raw_tenant = str(user_ctx.get("userId") or ""), str(user_ctx.get("tenantId") or "")
    if not raw_id.startswith("db-") or not raw_id[3:].isdigit() or not raw_tenant.isdigit():
        raise AppException("UNAUTHORIZED", "请使用正式账号登录后操作")
    return int(raw_id[3:]), int(raw_tenant)


class CandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    phone: str = Field(..., min_length=11, max_length=20)
    currentPassword: str = Field(..., min_length=1, max_length=128)
    expectedCandidateVersion: StrictInt = Field(..., ge=0)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value):
        from app.services.phone_login_service import normalize_login_phone
        return normalize_login_phone(value)


@router.get("/phone-binding", summary="查看本人手机号登录绑定与待验证候选")
def get_phone_binding(user=Depends(get_current_user)):
    from app.models import PhoneLoginBinding, PhoneLoginCandidate
    user_id, tenant_id = _subject(user)
    db = get_sessionmaker()()
    try:
        from app.services.phone_binding_service import _locked_subject
        from app.services.notification.sms_service import phone_verification_ready
        _locked_subject(db, user)
        ready = phone_verification_ready()
        binding = db.scalars(select(PhoneLoginBinding).where(
            PhoneLoginBinding.tenant_id == tenant_id, PhoneLoginBinding.user_id == user_id,
            PhoneLoginBinding.is_deleted.is_(False),
        )).first()
        candidate = db.scalars(select(PhoneLoginCandidate).where(
            PhoneLoginCandidate.tenant_id == tenant_id, PhoneLoginCandidate.user_id == user_id,
            PhoneLoginCandidate.is_deleted.is_(False),
        )).first()
        return success({
            "state": binding.state if binding else "UNBOUND",
            "bindingVersion": int(binding.version or 0) if binding else 0,
            "phoneMasked": mask_phone_encrypted(binding.phone_ciphertext) if binding and binding.state == "VERIFIED" else "",
            "candidateState": candidate.state if candidate else "NONE",
            "candidateVersion": int(candidate.version or 0) if candidate else 0,
            "candidatePhoneMasked": mask_phone_encrypted(candidate.candidate_phone_ciphertext) if candidate else "",
            "allowedActions": {"registerCandidate": True,
                "verify": ready and not (binding and binding.state == 'VERIFIED'),
                "change": ready and bool(binding and binding.state == 'VERIFIED'),
                "revoke": bool(binding and binding.state == 'VERIFIED')},
            "verificationBlocked": "" if ready else "手机验证暂不可用，您仍可使用原账号登录",
        })
    finally:
        db.close()


@router.put("/phone-binding/candidate", summary="本人登记待核验手机号（不激活、不发码）")
def set_phone_candidate(body: CandidateRequest, user=Depends(get_current_user)):
    from app.models import PhoneLoginCandidate, User
    user_id, tenant_id = _subject(user)
    from app.services.control_plane_auth_service import rate_limit
    if not rate_limit(f"phone-candidate:{tenant_id}:{user_id}", 5, 300):
        raise AppException("RATE_LIMITED", "密码验证尝试过于频繁，请稍后再试", http_status=429)
    db = get_sessionmaker()()
    try:
        subject = db.scalars(select(User).where(
            User.id == user_id, User.tenant_id == tenant_id, User.status == "ACTIVE", User.is_deleted.is_(False),
        ).with_for_update()).first()
        if subject is None or not verify_password(body.currentPassword, subject.password_hash):
            raise AppException("REAUTH_REQUIRED", "请验证当前密码后再登记手机号", http_status=401)
        from app.services.auth_service_db import validate_credential_epoch
        validate_credential_epoch(subject, user)
        existing = db.scalars(select(PhoneLoginCandidate).where(
            PhoneLoginCandidate.tenant_id == tenant_id, PhoneLoginCandidate.user_id == user_id,
            PhoneLoginCandidate.is_deleted.is_(False),
        ).with_for_update()).first()
        actual_version = int(existing.version or 0) if existing else 0
        if body.expectedCandidateVersion != actual_version:
            raise AppException("DATA_CONFLICT", "待核验号码已变化，请刷新后重新确认", http_status=409)
        result = create_pending_candidate_in_session(
            db, tenant_id=tenant_id, user_id=user_id, phone=body.phone, source_kind="SELF_SERVICE",
            expected_version=body.expectedCandidateVersion,
        )
        db.commit()
        return success({"accepted": True, "state": "PENDING", "changed": result in {"CREATED", "UPDATED"}, "reloginRequired": False},
                       message="号码已登记为待本人验证；尚不能用于手机号登录")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
