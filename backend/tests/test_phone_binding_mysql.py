"""Real isolated MySQL + Redis proof and transaction regression. No SMS is sent."""
import pytest
from sqlalchemy import select, func

from tests.test_phone_login_mysql import phone_db, phone_identity
from app.core.exceptions import AppException


@pytest.fixture
def flow(phone_identity, monkeypatch):
    from app.core.config import settings
    from app.core.redis_client import get_redis
    from app.core.security import decode_token
    from app.services import control_plane_auth_service as auth
    assert get_redis().ping(), 'Real isolated Redis is required'
    for key, value in {'PHONE_BINDING_ENABLED': True, 'PHONE_SMS_CONSUMERS_READY': True,
                       'SMS_ENABLED': True, 'SMS_PROVIDER': 'mock',
                       'SMS_PHONE_DAILY_TENANT_BUDGET': 100, 'SMS_PHONE_DAILY_PLATFORM_BUDGET': 10000}.items():
        monkeypatch.setattr(settings, key, value)
    login = auth.login_with_password(phone_identity['login'], 'Local-test-Password1!', phone_identity['tenant'])
    return {**phone_identity, 'ctx': decode_token(login['accessToken']), 'nonce': 'local-browser-operation-nonce'}


def operation(flow):
    from app.services import phone_binding_service as svc
    return svc.reauthenticate(flow['ctx'], purpose='CHANGE_PHONE', new_phone='13900139000',
        current_password='Local-test-Password1!', nonce=flow['nonce'], expected_version=1)


def verified(flow, op):
    from app.services import phone_binding_service as svc
    from app.db.session import get_sessionmaker
    from app.models import PasswordResetSmsJob
    from app.core.field_crypto import decrypt_field
    svc.challenge(flow['ctx'], operation_id=op['operationId'], ticket=op['reauthTicket'], nonce=flow['nonce'])
    with get_sessionmaker()() as db:
        job = db.scalar(select(PasswordResetSmsJob).where(PasswordResetSmsJob.request_id == op['operationId']))
        assert job.purpose == 'CHANGE_PHONE'
        code = decrypt_field(job.code_encrypted, allow_legacy_plaintext=False)
    return svc.verify_challenge(flow['ctx'], operation_id=op['operationId'], challenge_id=op['operationId'],
        code=code, nonce=flow['nonce'])['verificationGrant']


def test_change_phone_preserves_subject_revokes_epoch_and_has_readonly_receipt(flow):
    from app.services import phone_binding_service as svc, auth_service_db, control_plane_auth_service as auth
    from app.db.session import get_sessionmaker
    from app.models import User, PhoneLoginBinding, IdempotencyRecord
    op = operation(flow)
    with pytest.raises(AppException):
        svc.challenge(flow['ctx'], operation_id=op['operationId'], ticket=op['reauthTicket'], nonce='wrong-nonce')
    grant = verified(flow, op)
    result = svc.confirm(flow['ctx'], operation_id=op['operationId'], grant=grant,
        nonce=flow['nonce'], expected_version=1, idempotency_key=op['operationId'])
    assert result['state'] == 'VERIFIED' and result['bindingVersion'] == 2 and result['reloginRequired']
    with pytest.raises(AppException):
        auth_service_db.validate_token_subject(flow['ctx'])
    with pytest.raises(AppException):
        svc.confirm(flow['ctx'], operation_id=op['operationId'], grant=grant,
            nonce=flow['nonce'], expected_version=1, idempotency_key='different-request')
    assert svc.operation_status(receipt_token=op['receiptToken'], nonce=flow['nonce'])['runtimeMaterialized']
    with pytest.raises(AppException):
        svc.operation_status(receipt_token=op['receiptToken'], nonce='wrong-nonce')
    with get_sessionmaker()() as db:
        assert db.get(User, flow['user_id']).login_name == flow['login']
        assert db.scalar(select(PhoneLoginBinding.version).where(PhoneLoginBinding.user_id == flow['user_id'])) == 2
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == flow['tenant_id'])) == 2
    assert auth.login_with_password('13900139000', 'Local-test-Password1!', flow['tenant'], identifier_type='PHONE')['userId'] == flow['ctx']['userId']


def test_audit_failure_rolls_back_binding_epoch_and_proof_consumption(flow, monkeypatch):
    from app.services import phone_binding_service as svc
    from app.db.session import get_sessionmaker
    from app.models import User, PhoneLoginBinding, IdempotencyRecord
    op = operation(flow)
    grant = verified(flow, op)
    original = svc.audit_log.record_critical_in_session
    def broken(*args, **kwargs):
        raise RuntimeError('injected audit failure')
    monkeypatch.setattr(svc.audit_log, 'record_critical_in_session', broken)
    with pytest.raises(RuntimeError, match='injected audit failure'):
        svc.confirm(flow['ctx'], operation_id=op['operationId'], grant=grant,
            nonce=flow['nonce'], expected_version=1, idempotency_key=op['operationId'])
    with get_sessionmaker()() as db:
        assert db.get(User, flow['user_id']).credential_version == 0
        assert db.scalar(select(PhoneLoginBinding.version).where(PhoneLoginBinding.user_id == flow['user_id'])) == 1
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.tenant_id == flow['tenant_id'])) == 0
    monkeypatch.setattr(svc.audit_log, 'record_critical_in_session', original)
    assert svc.confirm(flow['ctx'], operation_id=op['operationId'], grant=grant,
        nonce=flow['nonce'], expected_version=1, idempotency_key=op['operationId'])['runtimeMaterialized']


def test_old_reset_worker_does_not_claim_or_expire_phone_jobs(flow):
    from app.services import phone_binding_service as svc, password_reset_service as reset
    from app.db.session import get_sessionmaker
    from app.models import PasswordResetSmsJob
    op = operation(flow)
    svc.challenge(flow['ctx'], operation_id=op['operationId'], ticket=op['reauthTicket'], nonce=flow['nonce'])
    assert reset.process_delivery_jobs(tenant_id=flow['tenant_id']) == 0
    with get_sessionmaker()() as db:
        job = db.scalar(select(PasswordResetSmsJob).where(PasswordResetSmsJob.request_id == op['operationId']))
        assert job.status == 'PENDING'


def test_binding_proof_cannot_cross_session_or_survive_epoch_change(flow):
    from app.services import phone_binding_service as svc
    from app.db.session import get_sessionmaker
    from app.models import User
    op = operation(flow)
    with pytest.raises(AppException):
        svc.challenge({**flow['ctx'], 'jti': 'another-session'}, operation_id=op['operationId'],
                      ticket=op['reauthTicket'], nonce=flow['nonce'])
    grant = verified(flow, op)
    with get_sessionmaker()() as db:
        user = db.get(User, flow['user_id'], with_for_update=True)
        user.credential_version += 1
        db.commit()
    with pytest.raises(AppException):
        svc.confirm(flow['ctx'], operation_id=op['operationId'], grant=grant,
            nonce=flow['nonce'], expected_version=1, idempotency_key=op['operationId'])


def test_revoke_retains_row_and_account_login_then_self_bind_increments_version(flow):
    from app.services import phone_binding_service as svc, control_plane_auth_service as auth
    from app.core.security import decode_token
    from app.db.session import get_sessionmaker
    from app.models import PhoneLoginBinding, PasswordResetSmsJob
    from app.core.field_crypto import decrypt_field
    with get_sessionmaker()() as db:
        binding_id = db.scalar(select(PhoneLoginBinding.id).where(PhoneLoginBinding.user_id == flow['user_id']))
    op = svc.reauthenticate(flow['ctx'], purpose='REVOKE_PHONE', new_phone=None,
        current_password='Local-test-Password1!', nonce=flow['nonce'], expected_version=1)
    result = svc.confirm(flow['ctx'], operation_id=op['operationId'], grant=op['reauthTicket'],
        nonce=flow['nonce'], expected_version=1, idempotency_key=op['operationId'], revoke=True, reason='测试解绑')
    assert result['state'] == 'REVOKED' and result['bindingVersion'] == 2
    login = auth.login_with_password(flow['login'], 'Local-test-Password1!', flow['tenant'])
    ctx = decode_token(login['accessToken'])
    op = svc.reauthenticate(ctx, purpose='BIND_PHONE', new_phone='13800138000',
        current_password='Local-test-Password1!', nonce=flow['nonce'], expected_version=2)
    svc.challenge(ctx, operation_id=op['operationId'], ticket=op['reauthTicket'], nonce=flow['nonce'])
    with get_sessionmaker()() as db:
        code = decrypt_field(db.scalar(select(PasswordResetSmsJob.code_encrypted).where(PasswordResetSmsJob.request_id == op['operationId'])), allow_legacy_plaintext=False)
    grant = svc.verify_challenge(ctx, operation_id=op['operationId'], challenge_id=op['operationId'], code=code, nonce=flow['nonce'])['verificationGrant']
    assert svc.confirm(ctx, operation_id=op['operationId'], grant=grant, nonce=flow['nonce'], expected_version=2, idempotency_key=op['operationId'])['bindingVersion'] == 3
    with get_sessionmaker()() as db:
        row = db.get(PhoneLoginBinding, binding_id)
        assert row.user_id == flow['user_id'] and row.state == 'VERIFIED' and row.version == 3


def test_phone_worker_dispatches_only_through_original_mock_adapter(flow):
    from app.services import phone_binding_service as svc, password_reset_service as reset
    from app.db.session import get_sessionmaker
    from app.models import PasswordResetSmsJob, NotificationTask
    op = operation(flow)
    svc.challenge(flow['ctx'], operation_id=op['operationId'], ticket=op['reauthTicket'], nonce=flow['nonce'])
    assert reset.process_delivery_jobs(tenant_id=flow['tenant_id'], purposes=('CHANGE_PHONE', 'BIND_PHONE')) == 1
    with get_sessionmaker()() as db:
        job = db.scalar(select(PasswordResetSmsJob).where(PasswordResetSmsJob.request_id == op['operationId']))
        assert job.status == 'SENT' and job.code_encrypted is None and job.phone_encrypted is None
        task = db.scalar(select(NotificationTask).where(NotificationTask.tenant_id == flow['tenant_id']))
        assert task.payload_json == {'redacted': True, 'keys': ['code']}


def test_formal_phone_http_routes_require_subject_and_expose_scoped_receipt_only(flow, client):
    from app.services import control_plane_auth_service as auth
    login = auth.login_with_password(flow['login'], 'Local-test-Password1!', flow['tenant'])
    headers = {'Authorization': 'Bearer ' + login['accessToken']}
    assert client.get('/api/v1/auth/phone-binding').status_code == 401
    response = client.get('/api/v1/auth/phone-binding', headers=headers)
    assert response.status_code == 200 and response.json()['data']['state'] == 'VERIFIED'
    assert '13800138000' not in response.text
    invalid = client.post('/api/v1/auth/phone-binding/confirm', headers=headers, json={
        'operationId': 'po_' + 'a' * 32, 'verificationGrant': 'b' * 32, 'clientNonce': flow['nonce'],
        'expectedBindingVersion': True, 'phoneVerified': True})
    assert invalid.status_code >= 400
    status = client.post('/api/v1/auth/phone-binding/operation-status', json={
        'receiptToken': 'unknown-' + 'a' * 32, 'clientNonce': flow['nonce']})
    assert status.status_code >= 400
