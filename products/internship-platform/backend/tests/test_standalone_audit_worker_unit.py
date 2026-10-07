import json
import time
from unittest.mock import Mock
import pytest
from app import audit_worker as worker
from app.core.audit_payload import sanitize_audit_payload


def test_redaction_preserves_internship_identity_and_is_idempotent():
    original = {'internshipId': '123', 'actorUserId': 'db-7', 'ip': '127.0.0.1',
                'password': 'private', 'nested': [{'accessToken': 'private-token'}]}
    safe = sanitize_audit_payload(original)
    assert safe['internshipId'] == '123' and safe['actorUserId'] == 'db-7'
    assert safe['ip'].startswith('sha256:') and safe['password'].startswith('sha256:')
    assert safe['nested'][0]['accessToken'].startswith('sha256:')
    assert sanitize_audit_payload(safe) == safe
    assert original['password'] == 'private'


@pytest.mark.parametrize('payload', [None, {}, {'checkedAt': 0, 'healthy': True},
    {'checkedAt': time.time() + 600, 'healthy': True},
    {'checkedAt': time.time(), 'healthy': False}, {'checkedAt': 'bad', 'healthy': True}])
def test_health_probe_fails_closed(tmp_path, payload):
    path = tmp_path / 'heartbeat.json'
    if payload is not None:
        path.write_text(json.dumps(payload), encoding='utf-8')
    assert not worker.heartbeat_healthy(path)
    assert worker.main(['--healthcheck', '--heartbeat-file', str(path)]) == 1


def test_heartbeat_success_is_atomic_and_probe_does_not_touch_database(tmp_path, monkeypatch):
    path = tmp_path / 'heartbeat.json'
    monkeypatch.setattr(worker, 'run_once', Mock(side_effect=AssertionError('probe must not consume')))
    worker.write_heartbeat(path, True)
    assert worker.main(['--healthcheck', '--heartbeat-file', str(path)]) == 0
    assert list(tmp_path.glob('*.tmp')) == []


def test_once_failure_redacts_exception_and_invalidates_old_heartbeat(tmp_path, monkeypatch, caplog):
    path = tmp_path / 'heartbeat.json'
    worker.write_heartbeat(path, True)
    monkeypatch.setattr(worker, 'run_once', Mock(side_effect=RuntimeError('secret-password')))
    assert worker.main(['--once', '--heartbeat-file', str(path)]) == 1
    assert not worker.heartbeat_healthy(path)
    assert 'secret-password' not in caplog.text


def test_once_success_records_health(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'run_once', lambda *_: {'healthy': True, 'processed': 2, 'failed': 0})
    path = tmp_path / 'heartbeat.json'
    assert worker.main(['--once', '--heartbeat-file', str(path)]) == 0
    assert worker.heartbeat_healthy(path)


@pytest.mark.parametrize('args', [['--interval', '0'], ['--interval', 'nan'],
    ['--batch-size', '0'], ['--batch-size', '1001']])
def test_cli_bounds(args):
    with pytest.raises(SystemExit) as exc:
        worker.main(args)
    assert exc.value.code == 2
