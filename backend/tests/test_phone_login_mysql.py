"""Non-destructive tests on an already migrated, explicitly isolated MySQL database.

No db_mode / schema reset: each test rolls back only its own synthetic rows.
"""
import os
import secrets

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import PhoneLoginBinding, PhoneLoginCandidate


@pytest.fixture
def phone_db():
    engine = create_engine(os.environ['TEST_DATABASE_URL'])
    assert engine.url.get_backend_name() == 'mysql'
    assert engine.url.database.startswith('codex_phone_test_'), 'Use the dedicated phone test database'
    with engine.connect() as connection:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()
    with Session(engine) as db:
        yield db
        db.rollback()
    engine.dispose()


def binding(tenant, user, lookup=None):
    return PhoneLoginBinding(tenant_id=tenant, user_id=user,
        state='VERIFIED' if lookup else 'UNBOUND', active_phone_lookup=lookup,
        phone_ciphertext='test-envelope' if lookup else None)


def test_mysql_unique_phone_and_nullable_release(phone_db):
    db = phone_db
    tenant = secrets.randbelow(10**12) + 10**12
    first = binding(tenant, 1, 'a' * 64)
    db.add(first)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(binding(tenant, 2, 'a' * 64))
        db.flush()
    first.state = 'REVOKED'
    first.active_phone_lookup = first.phone_ciphertext = None
    first.version += 1
    db.flush()
    db.add_all([binding(tenant, 2, 'a' * 64), binding(tenant, 3), binding(tenant, 4)])
    db.flush()
    assert first.version == 1
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(binding(tenant, 1))
        db.flush()


def test_mysql_candidates_do_not_reserve_verified_phone(phone_db):
    tenant = secrets.randbelow(10**12) + 10**12
    phone_db.add_all([
        PhoneLoginCandidate(tenant_id=tenant, user_id=i, candidate_lookup='b' * 64, state='CONFLICT')
        for i in (1, 2)
    ])
    phone_db.add_all([binding(tenant, 3, 'b' * 64), binding(tenant + 1, 4, 'b' * 64)])
    phone_db.flush()


@pytest.mark.parametrize('values', [
    {'state': 'VERIFIED'}, {'state': 'REVOKED', 'active_phone_lookup': 'c' * 64},
    {'state': 'PENDING'}, {'version': -1},
])
def test_mysql_rejects_invalid_binding_state(phone_db, values):
    row = binding(secrets.randbelow(10**12) + 10**12, 1)
    for key, value in values.items():
        setattr(row, key, value)
    with pytest.raises(OperationalError) as failure, phone_db.begin_nested():
        phone_db.add(row)
        phone_db.flush()
    assert failure.value.orig.args[0] == 3819


def test_mysql_phone_schema_matches_declared_indexes(phone_db):
    inspector = inspect(phone_db.bind)
    for model in (PhoneLoginBinding, PhoneLoginCandidate):
        table = model.__table__
        columns = {c['name']: c for c in inspector.get_columns(table.name)}
        assert set(columns) == set(table.columns.keys())
        assert str(columns['version']['type']) == 'BIGINT'
        assert {i.name for i in table.indexes} == {i['name'] for i in inspector.get_indexes(table.name) if not i['unique']}


@pytest.fixture
def phone_identity(phone_db, monkeypatch):
    from app.core.config import settings
    from app.core.security import hash_password
    from app.db.session import reset_state
    from app.models import Tenant, User, Role, UserRole, SysConfig
    from app.services.phone_login_service import phone_lookup
    from app.core.field_crypto import encrypt_sensitive
    suffix = secrets.token_hex(6)
    monkeypatch.setattr(settings, 'DB_ENABLED', True)
    monkeypatch.setattr(settings, 'DATABASE_URL', os.environ['TEST_DATABASE_URL'])
    monkeypatch.setattr(settings, 'SENSITIVE_SEARCH_HMAC_KEY', secrets.token_hex(32))
    reset_state()
    tenant = Tenant(tenant_code='phone-' + suffix, school_name='手机号隔离测试学校')
    phone_db.add(tenant)
    phone_db.flush()
    user = User(tenant_id=tenant.id, login_name='staff-' + suffix, real_name='测试教师',
                password_hash=hash_password('Local-test-Password1!'), user_type='TEACHER')
    role = Role(tenant_id=tenant.id, role_code='ACADEMIC_TEACHER', role_name='任课教师')
    phone_db.add_all([user, role])
    phone_db.flush()
    phone_db.add(UserRole(tenant_id=tenant.id, user_id=user.id, role_id=role.id, status='ACTIVE'))
    phone_db.add(SysConfig(tenant_id=tenant.id, config_key='SEC_PHONE_LOGIN_ENABLED', value_text='1'))
    phone_db.add(PhoneLoginBinding(tenant_id=tenant.id, user_id=user.id, state='VERIFIED',
        active_phone_lookup=phone_lookup(tenant.id, '+8613800138000'),
        phone_ciphertext=encrypt_sensitive('+8613800138000'), version=1))
    phone_db.commit()
    yield {'tenant': tenant.tenant_code, 'user_id': user.id, 'tenant_id': tenant.id, 'login': user.login_name}
    reset_state()


def test_mysql_phone_and_account_use_original_subject_and_reject_revoked_epoch(phone_identity):
    from app.services import control_plane_auth_service as auth, auth_service_db
    from app.core.security import decode_token
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import User
    identity = phone_identity
    account = auth.login_with_password(identity['login'], 'Local-test-Password1!', identity['tenant'])
    phone = auth.login_with_password('13800138000', 'Local-test-Password1!', identity['tenant'], identifier_type='PHONE')
    assert account['userId'] == phone['userId'] == f"db-{identity['user_id']}"
    assert phone['username'] == identity['login']
    claims = decode_token(phone['accessToken'])
    auth_service_db.validate_token_subject(claims)
    with get_sessionmaker()() as db:
        user = db.get(User, identity['user_id'], with_for_update=True)
        user.credential_version += 1
        db.commit()
    with pytest.raises(AppException):
        auth_service_db.validate_token_subject(claims)
    with pytest.raises(AppException):
        auth.refresh(phone['refreshToken'])


def test_mysql_aliases_share_captcha_and_policy_off_preserves_account(phone_identity):
    from app.services import control_plane_auth_service as auth
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import SysConfig
    from sqlalchemy import select
    identity = phone_identity
    for identifier, mode in [(identity['login'], 'ACCOUNT'), ('+8613800138000', 'PHONE')]:
        with pytest.raises(AppException):
            auth.login_with_password(identifier, 'wrong-password', identity['tenant'], identifier_type=mode)
    assert auth.captcha_required('PASSWORD_LOGIN', identity['tenant'], identity['login'], 'ACCOUNT')
    assert auth.captcha_required('PASSWORD_LOGIN', identity['tenant'], '13800138000', 'PHONE')
    with get_sessionmaker()() as db:
        policy = db.scalar(select(SysConfig).where(SysConfig.tenant_id == identity['tenant_id'],
            SysConfig.config_key == 'SEC_PHONE_LOGIN_ENABLED'))
        policy.value_text = '0'
        db.commit()
    with pytest.raises(AppException):
        auth.login_with_password('13800138000', 'Local-test-Password1!', identity['tenant'], identifier_type='PHONE')
    assert auth.login_with_password(identity['login'], 'Local-test-Password1!', identity['tenant'])['username'] == identity['login']


def test_mysql_password_change_revokes_both_alias_sessions(phone_identity):
    from app.services import control_plane_auth_service as auth, auth_service_db
    from app.core.security import decode_token
    from app.core.exceptions import AppException
    identity = phone_identity
    old = auth.login_with_password(identity['login'], 'Local-test-Password1!', identity['tenant'])
    claims = decode_token(old['accessToken'])
    result = auth.change_own_password(claims, 'Local-test-Password1!', 'Local-test-Password2!')
    assert result['reloginRequired']
    with pytest.raises(AppException):
        auth_service_db.validate_token_subject(claims)
    new = auth.login_with_password('13800138000', 'Local-test-Password2!', identity['tenant'], identifier_type='PHONE')
    new_claims = decode_token(new['accessToken'])
    assert new_claims['credentialVersion'] == claims['credentialVersion'] + 1
    auth_service_db.validate_token_subject(new_claims)


def test_mysql_two_connections_cannot_claim_same_phone(phone_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    engine = phone_db.bind
    tenant = secrets.randbelow(10**12) + 10**12
    attempting = Event()
    def competitor():
        with Session(engine) as second:
            second.add(binding(tenant, 2, 'd' * 64))
            attempting.set()
            try:
                second.commit()
                return 'accepted'
            except IntegrityError as exc:
                second.rollback()
                assert exc.orig.args[0] == 1062
                return 'duplicate'
    first = binding(tenant, 1, 'd' * 64)
    phone_db.add(first)
    phone_db.flush()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(competitor)
        assert attempting.wait(5)
        phone_db.commit()
        assert future.result(timeout=10) == 'duplicate'


def test_mysql_contact_and_candidate_never_authenticate(phone_identity):
    from app.services import control_plane_auth_service as auth
    from app.services.phone_login_service import phone_lookup
    from app.core.exceptions import AppException
    from app.core.field_crypto import encrypt_sensitive, hash_sensitive
    from app.db.session import get_sessionmaker
    from app.models import User
    from sqlalchemy import select
    identity = phone_identity
    with get_sessionmaker()() as db:
        row = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.user_id == identity['user_id'],
            PhoneLoginBinding.tenant_id == identity['tenant_id']))
        row.state = 'REVOKED'
        row.active_phone_lookup = row.phone_ciphertext = None
        row.version += 1
        user = db.get(User, identity['user_id'])
        user.phone_encrypted = encrypt_sensitive('13800138000')
        user.phone_hash = hash_sensitive('13800138000', 'phone')
        db.add(PhoneLoginCandidate(tenant_id=user.tenant_id, user_id=user.id,
            candidate_phone_ciphertext=encrypt_sensitive('+8613800138000'),
            candidate_lookup=phone_lookup(user.tenant_id, '+8613800138000'), state='PENDING'))
        db.commit()
    with pytest.raises(AppException):
        auth.login_with_password('13800138000', 'Local-test-Password1!', identity['tenant'], identifier_type='PHONE')
    assert auth.login_with_password(identity['login'], 'Local-test-Password1!', identity['tenant'])['userId'] == f"db-{identity['user_id']}"


def test_candidate_writer_preserves_existing_binding_and_rejects_import_overwrite(phone_identity):
    from app.services.phone_login_service import create_pending_candidate_in_session
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from sqlalchemy import select
    identity = phone_identity
    with get_sessionmaker()() as db:
        common = dict(tenant_id=identity['tenant_id'], user_id=identity['user_id'])
        assert create_pending_candidate_in_session(db, **common, phone='13800138000', source_kind='IDENTITY_IMPORT') == 'VERIFIED_UNCHANGED'
        with pytest.raises(AppException):
            create_pending_candidate_in_session(db, **common, phone='13900139000', source_kind='IDENTITY_IMPORT')
        assert create_pending_candidate_in_session(db, **common, phone='13900139000', source_kind='SELF_SERVICE', expected_version=0) == 'CREATED'
        db.flush()
        candidate = db.scalar(select(PhoneLoginCandidate).where(PhoneLoginCandidate.user_id == identity['user_id']))
        assert candidate.state == 'PENDING' and candidate.version == 1
        assert '13900139000' not in candidate.candidate_phone_ciphertext
        with pytest.raises(AppException):
            create_pending_candidate_in_session(db, **common, phone='13700137000', source_kind='SELF_SERVICE', expected_version=0)
        db.rollback()
