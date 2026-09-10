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
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '20260910_phone_login_foundation'
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
