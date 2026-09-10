"""Purpose and replay boundaries for the existing SMS proof infrastructure."""
import pytest


def test_original_sms_queue_has_purpose_discriminator():
    from app.models import PasswordResetSmsJob
    assert {'purpose', 'challenge_ref'} <= set(PasswordResetSmsJob.__table__.columns.keys())


def test_reset_verifier_cannot_consume_a_binding_challenge(monkeypatch):
    from app.services import password_reset_service as reset
    from app.core.config import settings
    monkeypatch.setattr(settings, 'APP_ENV', 'test')
    monkeypatch.setattr(reset, 'get_redis', lambda: None)
    reset._set('code', 'purpose-test', {'purpose': 'BIND_PHONE',
        'codeHash': reset._digest('code', 'purpose-test\n123456'),
        'nonceHash': reset._digest('nonce', 'nonce'), 'clientType': 'PC', 'attempts': 5}, 300)
    assert reset._verify_code('purpose-test', '123456', 'nonce', 'PC') is None


def test_phone_binding_api_rejects_client_verification_flags():
    from app.api.v1.phone_login import CandidateRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CandidateRequest(phone='13800138000', currentPassword='test', expectedCandidateVersion=0, phoneVerified=True)


def test_phone_confirmation_rejects_retarget_and_boolean_version():
    from app.api.v1.phone_login import ConfirmRequest
    from pydantic import ValidationError
    values = dict(operationId='po_' + 'a' * 32, verificationGrant='a' * 32,
                  clientNonce='nonce-test', expectedBindingVersion=1)
    for change in ({'phone': '13800138000'}, {'expectedBindingVersion': True}, {'userId': 'db-1'}):
        with pytest.raises(ValidationError):
            ConfirmRequest(**{**values, **change})
