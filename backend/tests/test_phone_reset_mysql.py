"""Phone reset uses the original queue and only current VERIFIED credentials."""
import pytest
from sqlalchemy import select
from tests.test_phone_login_mysql import phone_db, phone_identity
from tests.test_phone_binding_mysql import flow


@pytest.fixture
def reset_flow(flow):
    import secrets
    from app.db.session import get_sessionmaker
    from app.models import SysConfig, PhoneLoginBinding
    from app.core.field_crypto import encrypt_field
    from app.services.phone_login_service import phone_lookup
    with get_sessionmaker()() as db:
        phone = '+86139' + f'{secrets.randbelow(100_000_000):08d}'
        binding = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.user_id == flow['user_id']).with_for_update())
        binding.phone_ciphertext = encrypt_field(phone)
        binding.active_phone_lookup = phone_lookup(flow['tenant_id'], phone)
        db.add(SysConfig(tenant_id=flow['tenant_id'], config_key='SEC_PHONE_RECOVERY_ENABLED', value_text='1'))
        db.commit()
    return flow


def reset_token(flow):
    from app.services import password_reset_service as svc
    from app.db.session import get_sessionmaker
    from app.models import PasswordResetSmsJob
    from app.core.field_crypto import decrypt_field
    result, delivery = svc.begin_reset(flow['login'], flow['tenant'], flow['nonce'], 'TEACHER_PC')
    assert delivery
    with get_sessionmaker()() as db:
        job = db.scalar(select(PasswordResetSmsJob).where(PasswordResetSmsJob.request_id == result['requestId']))
        code = decrypt_field(job.code_encrypted, allow_legacy_plaintext=False)
    verified = svc.verify_reset_code(result['requestId'], code, flow['nonce'], 'TEACHER_PC')
    return verified['resetToken']


def test_reset_rejects_phone_changed_after_otp(reset_flow):
    from app.services import password_reset_service as svc
    from app.db.session import get_sessionmaker
    from app.models import PhoneLoginBinding
    from app.core.exceptions import AppException
    token = reset_token(reset_flow)
    with get_sessionmaker()() as db:
        binding = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.user_id == reset_flow['user_id']).with_for_update())
        binding.version += 1
        db.commit()
    with pytest.raises(AppException):
        svc.confirm_reset(token, 'Another-Password2!')


def test_reset_expiry_is_absolute_and_not_extended_by_validation_failure(reset_flow, monkeypatch):
    from app.services import password_reset_service as svc
    from app.core.exceptions import AppException
    token = reset_token(reset_flow)
    token_id = svc._digest('token', token)
    snapshot = svc._read('token', token_id)
    assert snapshot['expiresAt'] > svc.time.time()
    expiry = snapshot['expiresAt']
    with pytest.raises(AppException):
        svc.confirm_reset(token, 'Local-test-Password1!')
    assert svc._read('token', token_id)['expiresAt'] == expiry
    monkeypatch.setattr(svc.time, 'time', lambda: expiry + 1)
    with pytest.raises(AppException):
        svc.confirm_reset(token, 'Another-Password2!')


def test_reset_success_is_durable_idempotent_and_never_reapplies_password(reset_flow):
    from app.services import password_reset_service as svc, auth_service_db
    from app.core.exceptions import AppException
    token = reset_token(reset_flow)
    assert svc.confirm_reset(token, 'Another-Password2!')['reloginRequired']
    assert svc.confirm_reset(token, 'Another-Password2!')['runtimeMaterialized']
    with pytest.raises(AppException):
        svc.confirm_reset(token, 'Different-Password3!')
    with pytest.raises(AppException):
        auth_service_db.validate_token_subject(reset_flow['ctx'])


def test_contact_and_high_privilege_do_not_gain_sms_recovery(reset_flow):
    from app.services import password_reset_service as svc
    from app.db.session import get_sessionmaker
    from app.models import Role, UserRole
    with get_sessionmaker()() as db:
        role = Role(tenant_id=reset_flow['tenant_id'], role_code='SCHOOL_ADMIN', role_name='学校管理员')
        db.add(role)
        db.flush()
        db.add(UserRole(tenant_id=reset_flow['tenant_id'], user_id=reset_flow['user_id'], role_id=role.id))
        db.commit()
    assert svc._find_reset_account(reset_flow['login'], reset_flow['tenant'], 'TEACHER_PC') is None
