"""Self-service phone credentials using original auth, SMS proofs, receipts and outbox.

Redis freezes short-lived proofs. MySQL uniquely consumes them with the binding,
credential epoch, audit and notification intent in one transaction.
"""
from __future__ import annotations

import hmac
import json
import secrets
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.field_crypto import decrypt_field, encrypt_field
from app.core.security import verify_password
from app.db.session import get_sessionmaker
from app.models import IdempotencyRecord, PasswordResetSmsJob, PhoneLoginBinding, PhoneLoginCandidate, User
from app.services import auth_service_db, audit_log, password_reset_service as proofs
from app.services.phone_login_service import normalize_login_phone, phone_lookup

PURPOSES = {'BIND_PHONE', 'CHANGE_PHONE', 'REVOKE_PHONE'}


def _invalid(message='验证流程无效或已过期，请重新办理', code='CHALLENGE_INVALID', status=400):
    return AppException(code, message, http_status=status)


def _remaining(snapshot):
    remaining = int(snapshot.get('expiresAt', 0)) - int(time.time())
    if remaining <= 0:
        raise _invalid()
    return remaining


def _session(ctx):
    return proofs._digest('phone-session', '\n'.join(str(ctx.get(k) or '') for k in
        ('userId', 'tenantId', 'authSessionId', 'activeContextId', 'currentRoleCode')) +
        ('\n' + str(ctx.get('tokenJti') or ctx.get('jti') or '') if not ctx.get('authSessionId') else ''))


def _masked(encrypted):
    phone = decrypt_field(encrypted, allow_legacy_plaintext=False) if encrypted else ''
    digits = str(phone or '').removeprefix('+86')
    return digits[:3] + '****' + digits[-4:] if digits else ''


def _locked_subject(db, ctx):
    user = auth_service_db._load_token_user(db, ctx)
    db.refresh(user, with_for_update=True)
    auth_service_db.validate_credential_epoch(user, ctx)
    if user.is_deleted or user.status != 'ACTIVE' or user.user_type not in {'STUDENT', 'TEACHER', 'STAFF', 'ADMIN', 'SCHOOL_ADMIN'}:
        raise _invalid('该账号不能办理本人手机验证', 'NO_PERMISSION', 403)
    if user.must_change_password:
        raise _invalid('请先修改初始密码', 'PASSWORD_CHANGE_REQUIRED', 403)
    auth_service_db._ensure_tenant_login_allowed(db, user)
    contexts = auth_service_db._role_contexts(db, user)
    if not auth_service_db._pick_context(contexts, context_id=ctx.get('activeContextId'), role_code=ctx.get('currentRoleCode')):
        raise _invalid('当前岗位已失效，请重新登录', 'UNAUTHORIZED', 401)
    binding = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.tenant_id == user.tenant_id,
        PhoneLoginBinding.user_id == user.id).with_for_update().execution_options(populate_existing=True))
    if binding and binding.is_deleted:
        raise _invalid('号码记录状态异常，请联系学校核对', 'DATA_CONFLICT', 409)
    return user, binding


def _validate_snapshot(user, binding, ctx, snapshot, nonce):
    _remaining(snapshot)
    if (snapshot['userId'] != user.id or snapshot['tenantId'] != user.tenant_id or
        snapshot['sessionHash'] != _session(ctx) or snapshot['nonceHash'] != proofs._digest('nonce', nonce) or
        snapshot['credentialVersion'] != int(user.credential_version) or
        snapshot['bindingVersion'] != (int(binding.version) if binding else 0)):
        raise _invalid('账号或号码状态已变化，请重新办理', 'SESSION_CHANGED', 401)


def _operation(operation_id):
    snapshot = proofs._read('phone-operation', operation_id, require_shared=True)
    if not snapshot or snapshot.get('operationId') != operation_id:
        raise _invalid()
    _remaining(snapshot)
    return snapshot


def _ticket(snapshot, ticket):
    if not hmac.compare_digest(snapshot['ticketHash'], proofs._digest('phone-ticket', ticket)):
        raise _invalid()


def reauthenticate(ctx, *, purpose, new_phone, current_password, nonce, expected_version):
    if purpose not in PURPOSES or type(expected_version) is not int or expected_version < 0:
        raise _invalid('请选择有效操作并刷新号码状态', 'VALIDATION_ERROR', 422)
    if not nonce or len(nonce) < 8 or len(nonce) > 128:
        raise _invalid('请重新打开办理页面', 'VALIDATION_ERROR', 422)
    # Require shared proof storage before accepting a password-bearing operation.
    proofs._read('phone-readiness', 'probe', require_shared=True)
    from app.services.control_plane_auth_service import rate_limit
    if not rate_limit(f"phone-reauth:{ctx.get('tenantId')}:{ctx.get('userId')}", 5, 300):
        raise _invalid('验证尝试过于频繁，请稍后重试', 'RATE_LIMITED', 429)
    with get_sessionmaker()() as db:
        user, binding = _locked_subject(db, ctx)
        version = int(binding.version) if binding else 0
        if expected_version != version:
            raise _invalid('号码状态已变化，请刷新后确认', 'DATA_CONFLICT', 409)
        if not verify_password(current_password, user.password_hash):
            raise _invalid('当前密码不正确', 'REAUTH_REQUIRED', 401)
        verified = bool(binding and binding.state == 'VERIFIED')
        if (purpose == 'BIND_PHONE' and verified) or (purpose != 'BIND_PHONE' and not verified):
            raise _invalid('号码状态已变化，请刷新后确认', 'DATA_CONFLICT', 409)
        normalized = normalize_login_phone(new_phone) if purpose != 'REVOKE_PHONE' else None
        lookup = phone_lookup(user.tenant_id, normalized) if normalized else None
        if lookup:
            occupied = db.scalar(select(PhoneLoginBinding.id).where(
                PhoneLoginBinding.tenant_id == user.tenant_id, PhoneLoginBinding.active_phone_lookup == lookup,
                PhoneLoginBinding.state == 'VERIFIED'))
            if occupied:
                raise _invalid('此号码当前不能用于本次绑定，请核对号码', 'PHONE_NOT_AVAILABLE', 409)
        operation_id = 'po_' + secrets.token_urlsafe(32)
        ticket, receipt = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        snapshot = {'operationId': operation_id, 'purpose': purpose, 'userId': int(user.id),
            'tenantId': int(user.tenant_id), 'credentialVersion': int(user.credential_version),
            'bindingVersion': version, 'sessionHash': _session(ctx), 'nonceHash': proofs._digest('nonce', nonce),
            'phoneEncrypted': encrypt_field(normalized) if normalized else None, 'phoneLookup': lookup,
            'ticketHash': proofs._digest('phone-ticket', ticket), 'expiresAt': int(time.time()) + 300}
        proofs._set('phone-operation', operation_id, snapshot, 300, require_shared=True)
        proofs._set('phone-receipt', proofs._digest('phone-receipt', receipt),
            {k: snapshot[k] for k in ('operationId', 'userId', 'tenantId', 'nonceHash')}, 600, require_shared=True)
    return {'operationId': operation_id, 'reauthTicket': ticket, 'receiptToken': receipt,
        'expiresAt': snapshot['expiresAt'], 'expiresIn': 300, 'phoneMasked': _masked(snapshot['phoneEncrypted'])}


def challenge(ctx, *, operation_id, ticket, nonce):
    from app.services.notification.sms_service import phone_verification_ready
    if not phone_verification_ready():
        raise _invalid('手机验证暂不可用，请使用原账号登录', 'SMS_UNAVAILABLE', 503)
    snapshot = _operation(operation_id)
    _ticket(snapshot, ticket)
    if snapshot['purpose'] not in {'BIND_PHONE', 'CHANGE_PHONE'}:
        raise _invalid()
    with get_sessionmaker()() as db:
        user, binding = _locked_subject(db, ctx)
        _validate_snapshot(user, binding, ctx, snapshot, nonce)
        existing = db.scalar(select(PasswordResetSmsJob).where(PasswordResetSmsJob.request_id == operation_id))
        if existing:
            return {'accepted': True, 'challengeId': operation_id, 'expiresAt': snapshot['expiresAt'], 'retryAfter': 60}
        from app.services.control_plane_auth_service import rate_limit
        for key, limit, window in (
            (f"phone-send-cooldown:{user.tenant_id}:{user.id}", 1, 60),
            (f"phone-send-user:{user.tenant_id}:{user.id}", 3, 900),
            (f"phone-send-hour:{user.tenant_id}:{user.id}", 5, 3600),
            (f"phone-send-target:{snapshot['phoneLookup']}", 5, 3600),
            (f"phone-budget-tenant:{user.tenant_id}", settings.SMS_PHONE_DAILY_TENANT_BUDGET, 86400),
            ('phone-budget-platform', settings.SMS_PHONE_DAILY_PLATFORM_BUDGET, 86400),
        ):
            if not rate_limit(key, limit, window):
                raise _invalid('验证码请求过于频繁，请稍后再试', 'RATE_LIMITED', 429)
        code = f'{secrets.randbelow(1_000_000):06d}'
        payload = {**snapshot, 'codeHash': proofs._digest('code', f'{operation_id}\n{code}'),
            'clientType': snapshot['sessionHash'], 'attempts': 5}
        proofs._set('code', operation_id, payload, _remaining(snapshot), require_shared=True)
        db.add(PasswordResetSmsJob(tenant_id=user.tenant_id, user_id=user.id, request_id=operation_id,
            purpose=snapshot['purpose'], challenge_ref=operation_id, phone_encrypted=snapshot['phoneEncrypted'],
            code_encrypted=encrypt_field(code), expires_at=proofs._utc_now() + timedelta(seconds=_remaining(snapshot))))
        db.commit()
    return {'accepted': True, 'challengeId': operation_id, 'expiresAt': snapshot['expiresAt'], 'retryAfter': 60}


def verify_challenge(ctx, *, operation_id, challenge_id, code, nonce):
    if operation_id != challenge_id:
        raise _invalid()
    snapshot = _operation(operation_id)
    with get_sessionmaker()() as db:
        user, binding = _locked_subject(db, ctx)
        _validate_snapshot(user, binding, ctx, snapshot, nonce)
        from app.services.control_plane_auth_service import rate_limit
        if not rate_limit(f"phone-verify:{user.tenant_id}:{user.id}", 10, 900):
            raise _invalid('验证尝试过于频繁，请稍后重试', 'RATE_LIMITED', 429)
        payload = proofs._verify_code(challenge_id, code, nonce, snapshot['sessionHash'],
            purpose=snapshot['purpose'], require_shared=True)
        if not payload or payload.get('operationId') != operation_id:
            raise _invalid('验证码无效或已过期，请重新获取')
        grant = secrets.token_urlsafe(32)
        proofs._set('phone-grant', proofs._digest('phone-grant', grant), snapshot,
            _remaining(snapshot), require_shared=True)
    return {'verified': True, 'verificationGrant': grant, 'expiresAt': snapshot['expiresAt']}


def _receipt_query(db, snapshot):
    return db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id == snapshot['tenantId'],
        IdempotencyRecord.user_id == str(snapshot['userId']), IdempotencyRecord.operation == 'PHONE_OPERATION',
        IdempotencyRecord.key_hash == proofs._digest('phone-operation', snapshot['operationId'])).with_for_update())


def revoke_binding_in_session(binding):
    """Common self/admin mutation. Caller owns User lock, version, epoch and audit."""
    binding.state, binding.phone_ciphertext, binding.active_phone_lookup = 'REVOKED', None, None
    binding.revoked_at = proofs._utc_now()


def confirm(ctx, *, operation_id, grant, nonce, expected_version, idempotency_key, revoke=False, reason=''):
    if not idempotency_key or len(idempotency_key) > 128 or type(expected_version) is not int:
        raise _invalid('请重新确认本次操作', 'VALIDATION_ERROR', 422)
    snapshot = _operation(operation_id) if revoke else proofs._read('phone-grant', proofs._digest('phone-grant', grant), require_shared=True)
    if not snapshot or snapshot.get('operationId') != operation_id:
        raise _invalid()
    if revoke:
        _ticket(snapshot, grant)
        if snapshot['purpose'] != 'REVOKE_PHONE' or len(reason.strip()) < 2:
            raise _invalid('请填写解绑原因', 'VALIDATION_ERROR', 422)
    elif snapshot['purpose'] not in {'BIND_PHONE', 'CHANGE_PHONE'}:
        raise _invalid()
    fingerprint = proofs._digest('phone-request', json.dumps([operation_id, expected_version, nonce, idempotency_key, revoke, reason], ensure_ascii=False))
    db = get_sessionmaker()()
    try:
        user, binding = _locked_subject(db, ctx)
        receipt = _receipt_query(db, snapshot)
        if receipt:
            if receipt.fingerprint != fingerprint:
                raise _invalid('操作内容已变化，请查询原办理结果', 'DATA_CONFLICT', 409)
            return dict(receipt.result_json)
        _validate_snapshot(user, binding, ctx, snapshot, nonce)
        if expected_version != snapshot['bindingVersion']:
            raise _invalid('号码状态已变化，请刷新后确认', 'DATA_CONFLICT', 409)
        proof_digest = proofs._digest('phone-consumed-proof', grant)
        db.add(IdempotencyRecord(tenant_id=user.tenant_id, user_id=str(user.id), operation='PHONE_PROOF',
            key_hash=proof_digest, fingerprint=fingerprint, state='SUCCEEDED',
            expires_at=proofs._utc_now() + timedelta(days=1)))
        if not binding:
            binding = PhoneLoginBinding(tenant_id=user.tenant_id, user_id=user.id, state='UNBOUND', version=0)
            db.add(binding)
        binding.version = expected_version + 1
        if revoke:
            revoke_binding_in_session(binding)
        else:
            binding.state = 'VERIFIED'
            binding.phone_ciphertext, binding.active_phone_lookup = snapshot['phoneEncrypted'], snapshot['phoneLookup']
            binding.verified_at, binding.revoked_at = proofs._utc_now(), None
            binding.verification_method, binding.lookup_key_id = 'CURRENT_PASSWORD_AND_OTP', 'phone_login_v1'
            candidate = db.scalar(select(PhoneLoginCandidate).where(PhoneLoginCandidate.tenant_id == user.tenant_id,
                PhoneLoginCandidate.user_id == user.id).with_for_update())
            if candidate and candidate.candidate_lookup == snapshot['phoneLookup']:
                candidate.state, candidate.version = 'APPLIED', int(candidate.version) + 1
                binding.source_candidate_id, binding.source_job_id = candidate.id, candidate.source_job_id
        user.credential_version = int(user.credential_version) + 1
        result = {'operationId': operation_id, 'bindingVersion': binding.version,
            'credentialVersion': user.credential_version, 'phoneMasked': _masked(binding.phone_ciphertext),
            'state': binding.state, 'runtimeMaterialized': True, 'reloginRequired': True,
            'cacheInvalidated': False, 'cacheRecoveryRequired': True, 'notificationQueued': True,
            'warning': '安全变更已生效，请重新登录'}
        audit_log.record_critical_in_session(db, 'PHONE_BINDING_CHANGE', f'user:{user.id}',
            detail={'operationId': operation_id, 'purpose': snapshot['purpose'], 'bindingVersion': binding.version,
                'credentialVersion': user.credential_version, 'phoneMasked': result['phoneMasked'], 'reason': reason},
            tenant_id=user.tenant_id, resource_id=str(user.id))
        from app.services.message_event_outbox_service import emit_message_event
        emit_message_event(db, event_code='AUTH.PHONE_CHANGED', source_module='systemAdmin', source_biz_type='USER',
            source_biz_id=user.id, recipient_refs=[{'userId': user.id}], tenant_id=user.tenant_id,
            content='您的账号登录号码已变更，原账号仍可使用。如非本人操作，请立即联系学校核对。', dedup_key=operation_id)
        db.add(IdempotencyRecord(tenant_id=user.tenant_id, user_id=str(user.id), operation='PHONE_OPERATION',
            key_hash=proofs._digest('phone-operation', operation_id), fingerprint=fingerprint, state='SUCCEEDED',
            result_json=result, expires_at=proofs._utc_now() + timedelta(days=1)))
        db.commit()
        cleanup = auth_service_db.credential_change_receipt(user, ctx)
        return {**result, **cleanup}
    except IntegrityError:
        db.rollback()
        raise _invalid('号码或验证证明已被使用，请核对办理结果', 'PHONE_NOT_AVAILABLE', 409) from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def operation_status(*, receipt_token, nonce):
    if not proofs._allow(f'phone-status:{proofs._ip_hash()}', 60, 300):
        raise _invalid('结果查询过于频繁，请稍后重试', 'RATE_LIMITED', 429)
    scope = proofs._read('phone-receipt', proofs._digest('phone-receipt', receipt_token), require_shared=True)
    if not scope or not hmac.compare_digest(scope['nonceHash'], proofs._digest('nonce', nonce)):
        raise _invalid()
    with get_sessionmaker()() as db:
        receipt = _receipt_query(db, scope)
        return dict(receipt.result_json) if receipt else {'operationId': scope['operationId'], 'state': 'PENDING', 'runtimeMaterialized': False}


def delivery_is_current(db, job):
    snapshot = proofs._read('phone-operation', job.challenge_ref or '', require_shared=True)
    if not snapshot or snapshot.get('expiresAt', 0) <= time.time() or snapshot['purpose'] != job.purpose:
        return False
    if snapshot['tenantId'] != job.tenant_id or snapshot['userId'] != job.user_id or job.request_id != job.challenge_ref:
        return False
    user = db.scalar(select(User).where(User.id == job.user_id, User.tenant_id == job.tenant_id,
        User.is_deleted.is_(False), User.status == 'ACTIVE'))
    binding = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.user_id == job.user_id,
        PhoneLoginBinding.tenant_id == job.tenant_id))
    return bool(user and int(user.credential_version) == snapshot['credentialVersion'] and
        (int(binding.version) if binding else 0) == snapshot['bindingVersion'] and
        phone_lookup(job.tenant_id, decrypt_field(job.phone_encrypted, allow_legacy_plaintext=False)) == snapshot['phoneLookup'])
