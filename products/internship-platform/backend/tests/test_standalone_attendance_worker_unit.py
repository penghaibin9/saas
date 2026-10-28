"""Attendance lifecycle probes run without connecting to a school database."""
import json
import time
from unittest.mock import Mock

import pytest

from app import internship_attendance_worker as worker

TARGET = ['--tenant-id', '7', '--batch-id', '8']


@pytest.mark.parametrize('arguments', [[], ['--tenant-id', '7'], ['--tenant-id', '0', '--batch-id', '8'],
    ['--tenant-id', '7', '--batch-id', '-1'], TARGET + ['--interval', '0']])
def test_missing_or_invalid_targets_stop_before_any_cycle(monkeypatch, arguments):
    cycle = Mock(side_effect=AssertionError('must not scan without an explicit target'))
    monkeypatch.setattr(worker, 'run_cycle', cycle)
    with pytest.raises(SystemExit) as error:
        worker.main(arguments)
    assert error.value.code == 2
    cycle.assert_not_called()


def test_success_heartbeat_is_target_specific_and_probe_never_runs_business(tmp_path, monkeypatch):
    monkeypatch.setattr(worker.tempfile, 'gettempdir', lambda: str(tmp_path))
    cycle = Mock(return_value={'tenantId': '7', 'batchId': '8'})
    monkeypatch.setattr(worker, 'run_cycle', cycle)
    assert worker.main(TARGET + ['--once']) == 0
    cycle.assert_called_once_with(7, 8)
    cycle.reset_mock()
    assert worker.main(TARGET + ['--healthcheck']) == 0
    assert worker.main(['--tenant-id', '7', '--batch-id', '9', '--healthcheck']) == 1
    cycle.assert_not_called()
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('payload', [None, {}, {'checkedAt': time.time() - 181, 'healthy': True},
    {'checkedAt': time.time() + 600, 'healthy': True}, {'checkedAt': time.time(), 'healthy': False}])
def test_missing_stale_future_or_failed_heartbeat_is_unhealthy(tmp_path, monkeypatch, payload):
    path = tmp_path / 'attendance.json'
    if payload is not None:
        path.write_text(json.dumps(payload), encoding='utf-8')
    monkeypatch.setattr(worker, 'run_cycle', Mock(side_effect=AssertionError('probe cannot run a cycle')))
    assert worker.main(TARGET + ['--healthcheck', '--heartbeat-file', str(path)]) == 1


def test_cycle_failure_invalidates_heartbeat_and_redacts_exception(tmp_path, monkeypatch, caplog):
    path = tmp_path / 'attendance.json'
    worker.write_heartbeat(path, True)
    monkeypatch.setattr(worker, 'run_cycle', Mock(side_effect=RuntimeError('private-database-password')))
    assert worker.main(TARGET + ['--once', '--heartbeat-file', str(path)]) == 1
    assert not worker.heartbeat_healthy(path)
    assert 'private-database-password' not in caplog.text
    assert '考勤调度未完成' in caplog.text


def test_unwritable_heartbeat_cannot_report_healthy(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(worker, 'run_cycle', lambda *_: {})
    monkeypatch.setattr(worker, 'write_heartbeat', Mock(side_effect=OSError('private-path')))
    assert worker.main(TARGET + ['--once', '--heartbeat-file', str(tmp_path / 'attendance.json')]) == 1
    assert 'private-path' not in caplog.text
