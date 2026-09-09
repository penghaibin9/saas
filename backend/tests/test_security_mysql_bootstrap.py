"""Execute the real initializer in bash, with ONLY the mysql client replaced.

No SQL engine or production account is touched. The image workflow separately
proves startup, migration and actual MySQL privilege boundaries.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'deploy/docker/mysql-security-init/01-accounts.sh'


def invoke(tmp_path, *, source=True, overrides=None, failure=0, parent_nounset=False):
    binary = tmp_path / 'mysql'
    binary.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
Path(os.environ['MYSQL_CAPTURE']).write_text(json.dumps({
    'args': sys.argv[1:], 'sql': sys.stdin.read(), 'password': os.environ.get('MYSQL_PWD')
}))
sys.exit(int(os.environ['MYSQL_CLIENT_EXIT']))
''')
    binary.chmod(0o700)
    capture = tmp_path / 'capture.json'
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('MYSQL_', 'MIGRATOR_', 'BASH_ENV', 'SHELLOPTS', 'BASHOPTS'))}
    env.update(PATH=f'{tmp_path}:{os.environ["PATH"]}', MYSQL_DATABASE='saas_lifecycle',
               MYSQL_USER='saas_runtime', MYSQL_ROOT_PASSWORD='a' * 64,
               MIGRATOR_PASSWORD='b' * 64, MYSQL_CAPTURE=str(capture), MYSQL_CLIENT_EXIT=str(failure))
    for key, value in (overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    if source:
        # Same calling convention and post-hook optional variable access as the
        # official entrypoint (not a reimplementation of the whole entrypoint).
        harness = '''set -eo pipefail
before=$(set +o)
before_pwd=${MYSQL_PWD-unset}
. "$1"
after=$(set +o)
[[ "$before" == "$after" ]]
[[ "${MYSQL_PWD-unset}" == "$before_pwd" ]]
if [ -n "$MYSQL_ONETIME_PASSWORD" ]; then :; fi
printf 'entrypoint-resumed\\n'
'''
        if parent_nounset:
            harness = 'set -u\n' + harness
        command = ['bash', '-c', harness, 'init-harness', str(SCRIPT)]
    else:
        command = ['bash', str(SCRIPT)]
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=10)
    return result, json.loads(capture.read_text()) if capture.exists() else None


def test_sourced_initializer_preserves_options_and_optional_entrypoint_variable(tmp_path):
    result, captured = invoke(tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'entrypoint-resumed\n'
    assert captured is not None


def test_executable_initializer_also_works(tmp_path):
    result, captured = invoke(tmp_path, source=False)
    assert result.returncode == 0 and captured is not None


def test_parent_nounset_and_preexisting_password_environment_are_preserved(tmp_path):
    result, _ = invoke(tmp_path, parent_nounset=True,
                       overrides={'MYSQL_ONETIME_PASSWORD': '', 'MYSQL_PWD': 'parent-only'})
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('source', [False, True])
@pytest.mark.parametrize('overrides', [
    {'MYSQL_DATABASE': 'other_school'}, {'MYSQL_USER': 'root'},
    {'MIGRATOR_PASSWORD': "x'; GRANT ALL ON *.*"},
    {'MIGRATOR_PASSWORD': 'A' * 64}, {'MIGRATOR_PASSWORD': None},
    {'MYSQL_ROOT_PASSWORD': None},
])
def test_invalid_inputs_stop_before_any_sql(tmp_path, source, overrides):
    result, captured = invoke(tmp_path, source=source, overrides=overrides)
    assert result.returncode != 0 and captured is None
    assert 'entrypoint-resumed' not in result.stdout


@pytest.mark.parametrize('source', [False, True])
def test_mysql_client_failure_is_not_swallowed(tmp_path, source):
    result, captured = invoke(tmp_path, source=source, failure=42)
    assert result.returncode == 42 and captured is not None
    assert 'entrypoint-resumed' not in result.stdout


def test_password_not_in_process_arguments_or_output_and_socket_is_explicit(tmp_path):
    result, captured = invoke(tmp_path, source=False, overrides={'SOCKET': '/tmp/mysql-init.sock'})
    assert result.returncode == 0, result.stderr
    assert '--socket=/tmp/mysql-init.sock' in captured['args']
    assert captured['password'] == 'a' * 64
    assert all('a' * 64 not in arg and 'b' * 64 not in arg for arg in captured['args'])
    assert 'a' * 64 not in result.stdout + result.stderr
    assert 'b' * 64 not in result.stdout + result.stderr


def test_grants_escape_schema_wildcard_and_keep_runtime_dml_only(tmp_path):
    result, captured = invoke(tmp_path, source=False)
    assert result.returncode == 0, result.stderr
    sql = captured['sql']
    grants = [line for line in sql.splitlines() if line.startswith('GRANT ')]
    assert len(grants) == 2
    assert all('ON `saas\\_lifecycle`.*' in line for line in grants)
    assert grants[1].startswith('GRANT SELECT, INSERT, UPDATE, DELETE ON ')
    assert 'REVOKE ALL PRIVILEGES, GRANT OPTION FROM' in sql
    assert not any('WITH GRANT OPTION' in line or '*.*' in line for line in grants)


def runner():
    import importlib.util
    path = ROOT / 'scripts/check/check-security-profile-containers.py'
    spec = importlib.util.spec_from_file_location('security_container_runner_unit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_subprocess_failure_reports_enums_not_secrets_or_argv(monkeypatch):
    module = runner()
    secret = 'synthetic-secret-never-in-report'
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
        a[0], 1, secret, f'OperationalError: (1045, Access denied: {secret})'))
    with pytest.raises(module.CheckFailure) as exc:
        module.run('MYSQL_WAIT', ['docker', 'run', secret])
    assert str(exc.value) == 'MYSQL_WAIT_FAILED'
    details = exc.value.safe_details
    assert details == {'timedOut': False, 'exitCode': 1,
                       'exceptionKinds': ['OperationalError'], 'mysqlErrorCodes': [1045]}
    assert secret not in json.dumps(details)


def test_timeout_is_classified_without_logging_captured_streams(monkeypatch):
    module = runner()
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(['not-to-be-logged'], 1, output='private', stderr='private')
    monkeypatch.setattr(module.subprocess, 'run', timeout)
    with pytest.raises(module.CheckFailure) as exc:
        module.run('BUILD', ['docker'])
    assert exc.value.safe_details == {'timedOut': True}


def test_mysql_diagnostics_keeps_only_state_and_recognized_flags(monkeypatch):
    module = runner()
    secret = 'synthetic-only-private-value'
    monkeypatch.setattr(module, 'run', lambda *a: json.dumps({
        'Running': False, 'OOMKilled': False, 'ExitCode': 1, 'Error': secret,
        'Health': {'Log': [{'Output': secret}]},
    }))
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
        a[0], 0, f'GENERATED ROOT PASSWORD: {secret}',
        f'{secret}: MYSQL_ONETIME_PASSWORD: unbound variable; Access denied'))
    result = module.mysql_diagnostics('owned-disposable-container')
    assert result == {'running': False, 'oomKilled': False, 'exitCode': 1,
                      'entrypointUnboundVariable': True, 'accessDenied': True,
                      'initializationComplete': False}
    assert secret not in json.dumps(result)


def test_diagnostic_read_error_is_explicit_not_replaced_by_healthy(monkeypatch):
    module = runner()
    def broken(*a, **kw):
        raise RuntimeError('private message')
    monkeypatch.setattr(module, 'run', broken)
    monkeypatch.setattr(module.subprocess, 'run', broken)
    assert module.mysql_diagnostics('owned') == {'stateUnavailable': True, 'logUnavailable': True}


def test_wait_fails_immediately_for_exited_mysql(monkeypatch):
    module = runner()
    calls = []
    def failure(*args):
        calls.append(args)
        raise module.CheckFailure('MYSQL_WAIT')
    monkeypatch.setattr(module, 'run', failure)
    monkeypatch.setattr(module, 'mysql_diagnostics', lambda _: {'running': False})
    monkeypatch.setattr(module.time, 'sleep', lambda _: pytest.fail('must not retry an exited container'))
    with pytest.raises(module.CheckFailure):
        module.wait_mysql(['owned-client'], 'owned-mysql')
    assert len(calls) == 1


def test_wait_retries_initializing_mysql_but_is_bounded(monkeypatch):
    module = runner()
    calls = []
    def failure(*args):
        calls.append(args)
        raise module.CheckFailure('MYSQL_WAIT')
    sleeps = []
    monkeypatch.setattr(module, 'run', failure)
    monkeypatch.setattr(module, 'mysql_diagnostics', lambda _: {'running': True})
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    with pytest.raises(module.CheckFailure):
        module.wait_mysql(['owned-client'], 'owned-mysql', attempts=3)
    assert len(calls) == 3 and sleeps == [2, 2]


def test_wait_success_does_not_probe_logs(monkeypatch):
    module = runner()
    monkeypatch.setattr(module, 'run', lambda *a: '1')
    monkeypatch.setattr(module, 'mysql_diagnostics', lambda _: pytest.fail('no failed startup'))
    module.wait_mysql(['owned-client'], 'owned-mysql')


@pytest.mark.parametrize('actions,flag', [('false', True), ('true', False), ('', False)])
def test_container_runner_requires_both_disposable_flags(monkeypatch, actions, flag):
    module = runner()
    monkeypatch.setenv('GITHUB_ACTIONS', actions)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: pytest.fail('not authorized'))
    with pytest.raises(SystemExit) as exc:
        module.main(['--disposable-ci-only'] if flag else [])
    assert exc.value.code == 2


def test_summary_artifact_does_not_overwrite_existing_file(tmp_path):
    module = runner()
    destination = tmp_path / 'evidence/result.json'
    summary = {'passed': False, 'failedCheck': 'MYSQL_WAIT_FAILED', 'releaseApproved': False}
    module.write_report(destination, summary)
    assert json.loads(destination.read_text()) == summary
    with pytest.raises(FileExistsError):
        module.write_report(destination, {'passed': True})
    assert json.loads(destination.read_text()) == summary
