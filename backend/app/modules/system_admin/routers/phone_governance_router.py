"""Fine-grained school phone administration, separate from self-service."""
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field, field_validator
from app.api.v1.phone_login import StrictRequest
from app.core.permissions import require_permission
from app.core.response import success
from app.modules.system_admin.services import phone_governance_service as svc
from app.services.phone_login_service import normalize_login_phone

router = APIRouter(prefix='/system')


class PhoneQuery(StrictRequest):
    accountType: Literal['', 'STAFF', 'STUDENT'] = ''
    state: Literal['', 'UNBOUND', 'VERIFIED', 'REVOKED', 'PENDING', 'CONFLICT'] = ''
    userId: str = Field('', pattern=r'^(?:[1-9][0-9]*)?$')
    keyword: str = Field('', max_length=100)
    phone: str = Field('', max_length=20)
    reason: str = Field('', max_length=300)
    page: int = Field(1, ge=1, le=100000)
    pageSize: int = Field(20, ge=1, le=100)

    @field_validator('phone')
    @classmethod
    def normalize(cls, value):
        return normalize_login_phone(value) if value else ''


class AdminCandidate(StrictRequest):
    phone: str = Field('', max_length=20)
    expectedCandidateVersion: int = Field(..., ge=0)
    reason: str = Field(..., min_length=5, max_length=300)

    @field_validator('phone')
    @classmethod
    def normalize(cls, value):
        return normalize_login_phone(value) if value else ''


class PhonePolicy(StrictRequest):
    configKey: Literal['SEC_PHONE_LOGIN_ENABLED', 'SEC_PHONE_RECOVERY_ENABLED']
    value: int = Field(..., ge=0, le=1)
    expectedVersion: int = Field(..., ge=0)
    reason: str = Field(..., min_length=5, max_length=300)


class PhoneBatchPreview(StrictRequest):
    action: Literal['REMIND', 'EXPORT']
    filters: PhoneQuery
    reason: str = Field(..., min_length=5, max_length=300)


class PhoneBatchConfirm(StrictRequest):
    previewId: str = Field(..., min_length=30, max_length=100)


class AdminRevoke(StrictRequest):
    currentPassword: str = Field(..., min_length=1, max_length=128)
    expectedBindingVersion: int = Field(..., ge=1)
    reason: str = Field(..., min_length=5, max_length=300)
    operationKey: str = Field(..., min_length=20, max_length=100)


@router.post('/phone-bindings/query')
def query_phone_bindings(body: PhoneQuery, user=Depends(require_permission(svc.PREFIX + 'view'))):
    return success(svc.query(user, body))


@router.put('/users/{user_id}/phone-candidate')
def set_phone_candidate(user_id: int, body: AdminCandidate, user=Depends(require_permission(svc.PREFIX + 'candidate.manage'))):
    return success(svc.set_candidate(user, user_id, body))


@router.get('/phone-login-policy')
def get_phone_policy(user=Depends(require_permission(svc.PREFIX + 'policy.view'))):
    return success(svc.policy(user))


@router.put('/phone-login-policy')
def set_phone_policy(body: PhonePolicy, user=Depends(require_permission(svc.PREFIX + 'policy.manage'))):
    return success(svc.set_policy(user, body))


@router.post('/phone-bindings/batch-preview')
def preview_phone_batch(body: PhoneBatchPreview, user=Depends(require_permission(svc.PREFIX + 'view'))):
    return success(svc.preview_batch(user, body))


@router.post('/phone-bindings/batch-confirm')
def confirm_phone_batch(body: PhoneBatchConfirm, user=Depends(require_permission(svc.PREFIX + 'view'))):
    return success(svc.confirm_batch(user, body))


@router.post('/users/{user_id}/phone-binding/revoke')
def revoke_user_phone(user_id: int, body: AdminRevoke, user=Depends(require_permission(svc.PREFIX + 'revoke'))):
    return success(svc.revoke_binding(user, user_id, body))
