from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.services import audit_log
from app.services import role_assignment_p1_guard_service as service


@pytest.fixture
def setup(monkeypatch):
    db = Mock()
    db.execute.return_value.first.return_value = NS(user_id=51, role_code='STAFF')
    db.scalar.return_value = None
    link = NS(id=61, version=7, status='ACTIVE', created_at=datetime(2025, 1, 1))
    role = NS(id=71, role_code='STAFF')
    account = NS(id=51)
    monkeypatch.setattr(service, 'get_sessionmaker', lambda: lambda: db)
    monkeypatch.setattr(service, '_lock_role', Mock(return_value=role))
    monkeypatch.setattr(service, '_lock_account', Mock(return_value=account))
    monkeypatch.setattr(service, '_active_role_link_for', Mock(return_value=link))
    monkeypatch.setattr(service, '_assert_account_role_compatibility', Mock())
    guard = Mock()
    monkeypatch.setattr(service.ras, '_assert_role_delegation_allowed', guard)
    read = Mock(return_value={'id': '81'})
    monkeypatch.setattr(service.ras, 'get_assignment', read)
    db.add.side_effect = lambda row: setattr(row, 'id', 81)
    audit = Mock()
    monkeypatch.setattr(audit_log, 'record_critical_in_session', audit)
    return NS(db=db, link=link, audit=audit, guard=guard, read=read)


def register():
    return service.register_legacy_assignment(61, reason='核对历史职责后补登记', expected_version=7,
                                              tenant_id=1007, user={'userId': 'db-9'})


def test_registration_preserves_existing_access_and_unknown_origin(setup):
    before = vars(setup.link).copy()
    assert register() == {'id': '81'}
    row = setup.db.add.call_args.args[0]
    assert row.user_role_id == 61 and row.user_id == 51
    assert row.effective_at == before['created_at'] and row.expires_at is None
    assert row.source_type == 'UNKNOWN' and row.granted_by is None
    assert vars(setup.link) == before
    setup.guard.assert_called_once()
    assert setup.audit.call_args.kwargs['detail']['accessChanged'] is False
    setup.db.commit.assert_called_once()


@pytest.mark.parametrize('failure', ['missing', 'version', 'inactive', 'registered', 'guard', 'audit'])
def test_rejections_rollback_without_changing_original_link(setup, failure):
    before = vars(setup.link).copy()
    if failure == 'missing': setup.db.execute.return_value.first.return_value = None
    if failure == 'version': setup.link.version = 8; before['version'] = 8
    if failure == 'inactive': service._active_role_link_for.return_value = None
    if failure == 'registered': setup.db.scalar.return_value = 81
    if failure == 'guard': setup.guard.side_effect = AppException('NO_PERMISSION', '不能转授')
    if failure == 'audit': setup.audit.side_effect = RuntimeError('audit unavailable')
    with pytest.raises((AppException, RuntimeError)):
        register()
    setup.db.commit.assert_not_called(); setup.db.rollback.assert_called_once()
    assert vars(setup.link) == before


def test_registration_is_a_required_critical_audit():
    assert 'ROLE_ASSIGNMENT_REGISTER' in audit_log.CRITICAL_ACTIONS
