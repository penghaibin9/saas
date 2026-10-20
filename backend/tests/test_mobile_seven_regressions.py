from __future__ import annotations

import uuid
import os
import pytest

from app.api.v1 import auth
from app.core import token_store
from app.core.security import create_access_token, decode_token
from app.core.security_legacy import get_current_user
from starlette.requests import Request
from app.core.exceptions import AppException
from app.services import browser_auth_session_blocklist as blocklist
from app.services import mobile_student_service as student
from app.services.notification import wechat_subscribe_service as wechat


@pytest.fixture(autouse=True)
def optional_mysql_runtime(monkeypatch):
    """Opt-in real token-store checks; no schema reset and no school business writes."""
    if os.environ.get("MOBILE_REGRESSION_MYSQL") != "1":
        yield
        return
    from sqlalchemy.engine import make_url
    from app.core.config import settings
    from app.db.session import reset_state
    target = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(target)
    assert parsed.drivername.startswith("mysql")
    assert "test" in (parsed.database or "").lower() or "e2e" in (parsed.database or "").lower()
    assert parsed.database != "student_lifecycle_runtime_20260902"
    monkeypatch.setattr(settings, "DB_ENABLED", True)
    monkeypatch.setattr(settings, "DATABASE_URL", target)
    reset_state()
    try:
        yield
    finally:
        reset_state()


def claims(**values):
    return dict(userId='regression-' + uuid.uuid4().hex, tenantId='1001', activeContextId='student', clientType='STUDENT_MINI', **values)


def test_current_logout_blocks_access_and_refresh_but_preserves_other_device(monkeypatch):
    first = claims(authSessionId=uuid.uuid4().hex)
    second = {**first, 'authSessionId': uuid.uuid4().hex, 'clientType': 'TEACHER_MINI'}
    access = create_access_token(first)
    refresh_a = token_store.issue_refresh(first)
    refresh_b = token_store.issue_refresh(second)
    monkeypatch.setattr(auth.audit, 'record', lambda *args, **kwargs: None)
    result = auth.logout(user=first, authorization='Bearer ' + access, scope='current')
    assert result['data']['tokenInvalidated'] is True
    assert token_store.jti_blocked(decode_token(access)['jti'])
    with pytest.raises(AppException):
        get_current_user(Request({'type': 'http', 'path': '/api/v1/auth/me', 'headers': []}), authorization='Bearer ' + access)
    assert blocklist.auth_session_blocked(first['authSessionId'])
    assert not blocklist.auth_session_blocked(second['authSessionId'])
    assert token_store.consume_refresh(refresh_a) is None
    assert token_store.consume_refresh(refresh_b)['authSessionId'] == second['authSessionId']
    # A refresh created in a rotation race still cannot restore the logged-out session.
    raced = token_store.issue_refresh(first)
    with pytest.raises(AppException):
        auth.refresh(auth.RefreshRequest(refreshToken=raced))


def test_legacy_logout_revokes_only_supplied_matching_refresh(monkeypatch):
    first = claims()
    access = create_access_token(first)
    refresh_a, refresh_b = token_store.issue_refresh(first), token_store.issue_refresh(first)
    monkeypatch.setattr(auth.audit, 'record', lambda *args, **kwargs: None)
    result = auth.logout(auth.LogoutRequest(refreshToken=refresh_a), user=first,
                         authorization='Bearer ' + access, scope='current')
    assert result['data']['tokenInvalidated']
    assert token_store.consume_refresh(refresh_a) is None
    assert token_store.consume_refresh(refresh_b) == first


@pytest.mark.parametrize('field,value', [('userId','other'), ('tenantId','other-school'), ('activeContextId','teacher'), ('clientType','TEACHER_MINI'), ('authSessionId','another-device')])
def test_mismatched_refresh_is_not_consumed(field, value):
    first = claims()
    refresh = token_store.issue_refresh(first)
    assert token_store.consume_refresh(refresh, expected_claims={**first, field: value}) is None
    assert token_store.consume_refresh(refresh) == first


@pytest.mark.parametrize('service_key', ['LEAVE', 'SV1', '请假'])
def test_generic_leave_rejects_attachments_before_business_write(monkeypatch, service_key):
    monkeypatch.setattr(student, '_require_student', lambda user: user)
    monkeypatch.setattr(student, 'db_enabled', lambda: True)
    monkeypatch.setattr(student, '_session', lambda: pytest.fail('must not create a leave while discarding files'))
    with pytest.raises(AppException, match='我的请假'):
        student.campus_service_apply({}, {'serviceKey': service_key, 'reason': '请假说明测试材料', 'fileIds': ['123']})


def test_configured_credentials_and_openid_are_not_subscription_authorization(monkeypatch):
    monkeypatch.setattr(wechat, 'provider_status', lambda: {
        'configured': True, 'providerReady': True, 'authorizationReady': False,
        'templates': {'CASE_RESULT': True}, 'scenes': ['CASE_RESULT'], 'missing': [],
    })
    monkeypatch.setattr(wechat, '_template_id', lambda scene: 'template-1')
    monkeypatch.setattr(wechat, '_call_provider', lambda **kwargs: pytest.fail('must not send without consent authority'))
    result = wechat.send_subscribe_message(tenant_id=1001, openid='openid', scene='CASE_RESULT')
    assert result['status'] == 'SKIPPED'
    assert result['reasonCode'] == 'SUBSCRIPTION_AUTH_UNAVAILABLE'
