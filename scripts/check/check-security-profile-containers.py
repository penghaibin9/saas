#!/usr/bin/env python3
"""Disposable CI-only image/Compose/MySQL privilege acceptance. NEVER deploys SaaS.

No published ports, no existing volume access, no production secrets, no registry
push. Only the random container/network created by this process are removed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import tempfile
import time


SECURITY_PYTHON_BASE_TAG = "registry.access.redhat.com/ubi9/python-312-minimal:9.8"
RUNTIME_BASE_TAG = "registry.access.redhat.com/ubi9/ubi-micro:9.8"


class CheckFailure(RuntimeError):
    """Failure metadata contains enums/numbers only, never command output."""
    def __init__(self, label, result=None, *, timed_out=False):
        super().__init__(label + '_FAILED')
        self.safe_details = {'timedOut': bool(timed_out)}
        if result is not None:
            self.safe_details['exitCode'] = int(result.returncode)
            text = (result.stdout or '') + (result.stderr or '')
            self.safe_details['exceptionKinds'] = [kind for kind in (
                'ModuleNotFoundError', 'PermissionError', 'OperationalError',
                'ProgrammingError', 'IntegrityError', 'AssertionError',
            ) if kind in text]
            self.safe_details['mysqlErrorCodes'] = sorted({int(code) for code in re.findall(
                r'(?:ERROR |\()(\d{4})(?:[ ,(])', text)
                if 1000 <= int(code) <= 4999})[:8]


def run(label, command, *, timeout=60, **kwargs):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise CheckFailure(label, timed_out=True) from exc
    if result.returncode:
        raise CheckFailure(label, result)
    return result.stdout.strip()


def mysql_diagnostics(container):
    """Read bounded diagnostics but publish only whitelisted state and flags."""
    result = {}
    try:
        state = json.loads(run('MYSQL_STATE', ['docker', 'inspect', '--format', '{{json .State}}', container]))
        result.update(running=state.get('Running') is True,
                      oomKilled=state.get('OOMKilled') is True,
                      exitCode=int(state.get('ExitCode', -1)))
    except Exception:
        result['stateUnavailable'] = True
    try:
        # docker logs sends the server's stderr to stderr; collect both privately.
        # Do not return excerpts: MySQL initialization can echo temporary secrets.
        raw = subprocess.run(['docker', 'logs', '--tail', '120', container],
                             capture_output=True, text=True, timeout=10, check=False)
        if raw.returncode:
            raise RuntimeError('MYSQL_LOG_FAILED')
        output = (raw.stdout or '') + (raw.stderr or '')
        result['entrypointUnboundVariable'] = 'unbound variable' in output
        result['accessDenied'] = 'Access denied' in output
        result['initializationComplete'] = 'MySQL init process done' in output
    except Exception:
        result['logUnavailable'] = True
    return result


def wait_mysql(command, container, *, attempts=60):
    for attempt in range(attempts):
        try:
            run('MYSQL_WAIT', command)
            return
        except CheckFailure:
            state = mysql_diagnostics(container)
            if state.get('running') is False or attempt == attempts - 1:
                raise
            time.sleep(2)


def complete(checks, name):
    checks.append(name)
    print(json.dumps({'check': name, 'passed': True}), flush=True)


def write_report(path, report):
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Never include env files, raw docker inspect/logs, SQL or command argv.
        with path.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-ci-only', action='store_true')
    parser.add_argument('--report-file', type=Path)
    args = parser.parse_args(argv)
    if not args.disposable_ci_only or os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('This check is restricted to an explicitly acknowledged disposable GitHub runner')
    root = Path(__file__).resolve().parents[2]
    suffix = secrets.token_hex(6)
    image, network, mysql = ('pr265-security-' + kind + '-' + suffix for kind in ('image', 'net', 'mysql'))
    created_mysql = created_network = False
    checks = []
    report = {}
    try:
        with tempfile.TemporaryDirectory(prefix='pr265-container-check-') as directory:
            folder = Path(directory)
            # Build exactly the same reviewed two-base candidate used by the Trivy gate.
            # Tags are pulled only to resolve immutable RepoDigests; the Docker build
            # receives the digests, never mutable tags. This is not a vulnerability scan.
            run('PULL_PYTHON', ['docker', 'pull', SECURITY_PYTHON_BASE_TAG], timeout=180)
            run('PULL_RUNTIME', ['docker', 'pull', RUNTIME_BASE_TAG], timeout=180)
            python_digest = run('PYTHON_DIGEST', ['docker', 'image', 'inspect', SECURITY_PYTHON_BASE_TAG,
                                                  '--format', '{{index .RepoDigests 0}}'])
            runtime_digest = run('RUNTIME_DIGEST', ['docker', 'image', 'inspect', RUNTIME_BASE_TAG,
                                                    '--format', '{{index .RepoDigests 0}}'])
            run('BUILD', ['docker', 'build', '-f', 'backend/Dockerfile.security',
                          '--build-arg', 'SECURITY_PYTHON_BASE_IMAGE=' + python_digest,
                          '--build-arg', 'RUNTIME_BASE_IMAGE=' + runtime_digest,
                          '-t', image, '.'], timeout=900, cwd=root)
            complete(checks, 'security-image-build')
            run('IMAGE_CONTRACT', ['docker', 'run', '--rm', '--network', 'none', '--read-only',
                                   '--cap-drop=ALL', '--security-opt=no-new-privileges', image,
                                   'python', 'scripts/security_profile_probe.py', 'image'])
            complete(checks, 'nonroot-image-runtime-contracts')
            run('APP_IMPORT', ['docker', 'run', '--rm', '--network', 'none', '--read-only',
                              '--tmpfs', '/tmp:rw,nosuid,nodev,noexec', '--cap-drop=ALL',
                              '--security-opt=no-new-privileges', '-e', 'APP_ENV=test', '-e', 'DB_ENABLED=false',
                              '-e', 'DEBUG=false', '-e', 'MOCK_LOGIN_ENABLED=false', image,
                              'python', '-c', 'import app.main; from app.core.module_registry import load_module_manifest; assert load_module_manifest()["modules"]'], timeout=90)
            complete(checks, 'complete-app-route-import-no-database')
            # Render the real YAML in an isolated layout; relative runtime.env is generated here.
            (folder / 'deploy/docker').mkdir(parents=True)
            (folder / 'deploy/docker/docker-compose.security.yml').write_bytes(
                (root / 'deploy/docker/docker-compose.security.yml').read_bytes())
            spec = importlib.util.spec_from_file_location('ci_profile_generator', root / 'scripts/deploy/prepare-security-config.py')
            generator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(generator)
            config_dir = folder / 'deploy/env/security'
            generator.prepare(config_dir, 'school.example.test', new_empty_install=True)
            env_path = config_dir / 'compose.env'
            content = env_path.read_text()
            # Syntax render only: do not pretend these mutable CI tags passed release preflight.
            # PYTHON_BASE_IMAGE is a deployment-profile input for migration tooling; keep it
            # pinned to the same reviewed Python digest used to build the application image.
            ci_images = {'APP_IMAGE': image, 'PYTHON_BASE_IMAGE': python_digest, 'MYSQL_IMAGE': 'mysql:8.0',
                         'REDIS_IMAGE': 'redis:7-alpine', 'NGINX_IMAGE': 'nginx:stable-alpine',
                         'CLAMAV_IMAGE': 'clamav/clamav:stable'}
            for key, value in ci_images.items():
                content = content.replace(f'{key}=REQUIRED_REVIEWED_DIGEST', f'{key}={value}')
            env_path.write_text(content)
            run('COMPOSE_SYNTAX', ['docker', 'compose', '--env-file', str(env_path), '-f',
                                  str(folder / 'deploy/docker/docker-compose.security.yml'), 'config', '-q'])
            complete(checks, 'real-docker-compose-render')
            # Validate actual Compose JSON, not the hand-normalized policy fixture.
            # Temporary tags are intentional here: the validator MUST still report
            # IMMUTABLE_IMAGE_REQUIRED for them. This is not a release bypass.
            for relative in ('deploy/docker/mysql-security-init/01-accounts.sh',
                             'deploy/nginx/security-http.conf', 'deploy/nginx/security-server.conf',
                             'deploy/nginx/security-headers.conf'):
                path = folder / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((root / relative).read_bytes())
            for relative in ('frontend/dist', 'student-portal/dist', 'enterprise-portal/dist',
                             'miniapp/dist/build/h5'):
                path = folder / relative
                path.mkdir(parents=True, exist_ok=True)
                (path / 'index.html').write_text('CI mount identity fixture; not a production UI')
            spec = importlib.util.spec_from_file_location(
                'ci_profile_preflight', root / 'scripts/deploy/check-security-profile.py')
            preflight = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(preflight)
            model = json.loads(run('COMPOSE_JSON', ['docker', 'compose', '--env-file', str(env_path),
                                  '-f', str(folder / 'deploy/docker/docker-compose.security.yml'),
                                  'config', '--format', 'json']))
            violations = preflight.validate_rendered(model, root=folder)
            tag_rejections = sorted(name + ':IMMUTABLE_IMAGE_REQUIRED'
                                    for name, service in model['services'].items()
                                    if not preflight.DIGEST.fullmatch(service['image']))
            if violations != tag_rejections:
                failure = CheckFailure('COMPOSE_BOUNDARY')
                # Only include validator identifiers when the service names are
                # the known profile set. No paths, commands, environment or model.
                if set(model['services']) == {'backend', 'scheduler', 'file-scan', 'migrate',
                                             'prepare-storage', 'mysql', 'redis', 'nginx', 'clamav'}:
                    failure.safe_details['policyErrors'] = violations
                    flags = {}
                    for service in ('mysql', 'nginx'):
                        counts = {'missing': 0, 'false': 0, 'true': 0, 'invalid': 0}
                        for mount in model['services'][service].get('volumes', []):
                            if mount.get('type') != 'bind':
                                continue
                            options = mount.get('bind', {})
                            if not isinstance(options, dict):
                                counts['invalid'] += 1
                            elif 'create_host_path' not in options:
                                counts['missing'] += 1
                            else:
                                flag = options['create_host_path']
                                counts['true' if flag is True else 'false' if flag is False else 'invalid'] += 1
                        flags[service] = counts
                    failure.safe_details['bindOptionShape'] = flags
                raise failure
            complete(checks, 'real-compose-execution-and-checked-input-boundaries')
            passwords = {key: secrets.token_hex(32) for key in ('root', 'runtime', 'migrator')}
            mysql_env = folder / 'mysql.env'
            mysql_env.write_text('MYSQL_DATABASE=saas_lifecycle\nMYSQL_USER=saas_runtime\n' +
                                 f'MYSQL_PASSWORD={passwords["runtime"]}\nMYSQL_ROOT_PASSWORD={passwords["root"]}\n' +
                                 f'MIGRATOR_PASSWORD={passwords["migrator"]}\n')
            mysql_env.chmod(0o600)
            run('CREATE_NETWORK', ['docker', 'network', 'create', '--internal', network])
            created_network = True
            run('MYSQL_CREATE', ['docker', 'create', '--name', mysql, '--network', network, '--network-alias', 'mysql',
                               '--env-file', str(mysql_env), '--mount',
                               f'type=bind,src={root / "deploy/docker/mysql-security-init/01-accounts.sh"},dst=/docker-entrypoint-initdb.d/01-accounts.sh,readonly',
                               'mysql:8.0', *model['services']['mysql']['command']], timeout=180)
            created_mysql = True
            run('MYSQL_START', ['docker', 'start', mysql])
            base = ['docker', 'run', '--rm', '--network', network, '--read-only', '--cap-drop=ALL',
                    '--security-opt=no-new-privileges']
            client = ('import os,pymysql; c=pymysql.connect(host="mysql",user=os.environ["PROBE_USER"],'
                      'password=os.environ["PROBE_PASSWORD"],database="saas_lifecycle",connect_timeout=3,autocommit=True); q=c.cursor(); ')
            envs = {}
            for role in ('migrator', 'runtime'):
                path = folder / (role + '.env')
                path.write_text(f'PROBE_USER=saas_{role}\nPROBE_PASSWORD={passwords[role]}\n')
                path.chmod(0o600)
                envs[role] = path
            # SQL grants are exercised over the Docker network, never the runner's host MySQL.
            wait_mysql(base + ['--env-file', str(envs['migrator']), image, 'python', '-c',
                               client + 'q.execute("SELECT 1")'], mysql)
            complete(checks, 'mysql-official-entrypoint-completed')
            # A look-alike schema proves that the underscore is NOT a wildcard.
            # Both databases exist solely in this randomly named disposable container.
            run('SCOPE_FIXTURE', ['docker', 'exec', '-i', mysql, 'sh', '-c',
                                 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --protocol=socket -uroot'],
                input='CREATE DATABASE saasXlifecycle; CREATE TABLE saasXlifecycle.sentinel (id INT);')
            run('MIGRATOR_DDL', base + ['--env-file', str(envs['migrator']), image, 'python', '-c',
                                      client + 'q.execute("CREATE TABLE pr265_privilege_probe (id INT PRIMARY KEY, value INT)")'])
            complete(checks, 'migrator-schema-ddl-allowed')
            run('MIGRATOR_TRIGGER', base + ['--env-file', str(envs['migrator']), image, 'python', '-c',
                    client + 'q.execute("SELECT @@log_bin, @@binlog_format, @@log_bin_trust_function_creators"); '
                    'assert q.fetchone() == (1, "ROW", 1); '
                    'q.execute("CREATE TRIGGER pr265_migration_trigger BEFORE INSERT ON pr265_privilege_probe FOR EACH ROW SET NEW.value=NEW.value")'])
            complete(checks, 'trusted-migrator-trigger-with-row-binlog-no-super')
            sql_test = client + '''
q.execute("INSERT INTO pr265_privilege_probe VALUES (1,2)")
q.execute("UPDATE pr265_privilege_probe SET value=3 WHERE id=1")
q.execute("SELECT value FROM pr265_privilege_probe WHERE id=1")
assert q.fetchone() == (3,)
q.execute("DELETE FROM pr265_privilege_probe WHERE id=1")
for sql in ("CREATE TABLE forbidden_probe (id INT)", "SELECT User FROM mysql.user", "CREATE USER 'forbidden_probe'@'%'",
            "CREATE TRIGGER forbidden_trigger BEFORE UPDATE ON pr265_privilege_probe FOR EACH ROW SET NEW.value=1",
            "CREATE FUNCTION forbidden_function() RETURNS INT DETERMINISTIC RETURN 1",
            "SET GLOBAL log_bin_trust_function_creators=0"):
    try:
        q.execute(sql)
    except pymysql.MySQLError as exc:
        assert exc.args[0] in {1044, 1142, 1227}, exc.args[0]
    else:
        raise AssertionError("runtime privilege boundary failed")
c.close()
'''
            run('RUNTIME_PRIVILEGES', base + ['--env-file', str(envs['runtime']), image, 'python', '-c', sql_test])
            complete(checks, 'runtime-dml-allowed-ddl-trigger-function-global-settings-denied')
            for role in ('runtime', 'migrator'):
                scope_proof = client + '''
for sql in ("SELECT id FROM saasXlifecycle.sentinel", "CREATE TABLE saasXlifecycle.forbidden (id INT)",
            "SET GLOBAL log_bin_trust_function_creators=0"):
    try:
        q.execute(sql)
    except pymysql.MySQLError as exc:
        assert exc.args[0] in {1044, 1142, 1227}, exc.args[0]
    else:
        raise AssertionError("look-alike schema incorrectly authorized")
c.close()
'''
                run('EXACT_SCHEMA_SCOPE', base + ['--env-file', str(envs[role]), image,
                                                'python', '-c', scope_proof])
            complete(checks, 'runtime-and-migrator-lookalike-schema-denied')
            run('DROP_PROBE', base + ['--env-file', str(envs['migrator']), image, 'python', '-c',
                                     client + 'q.execute("DROP TABLE pr265_privilege_probe")'])
            # Now exercise the actual image's Alembic path, not create_all or
            # hand-written application DDL. No account or business seed is run.
            migration_env = folder / 'migration.env'
            migration_env.write_text(
                'APP_ENV=production\nDEPLOYMENT_MODE=production\nDEBUG=false\nMOCK_LOGIN_ENABLED=false\n'
                'DB_ENABLED=true\nDB_DRIVER=mysql\nDB_HOST=mysql\nDB_PORT=3306\n'
                'DB_NAME=saas_lifecycle\nDB_USER=saas_migrator\nDATABASE_URL=\n'
                + f'DB_PASSWORD={passwords["migrator"]}\n')
            migration_env.chmod(0o600)
            run('IMAGE_ALEMBIC_UPGRADE', base + ['--tmpfs', '/tmp:rw,nosuid,nodev,noexec',
                                              '--env-file', str(migration_env), image,
                                              'alembic', 'upgrade', 'head'], timeout=900)
            complete(checks, 'nonroot-image-alembic-empty-schema-to-head')
            version_proof = client + '''
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.db.base import metadata
expected = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
assert len(expected) == 1
q.execute("SELECT version_num FROM alembic_version")
assert [item[0] for item in q.fetchall()] == expected
q.execute("SHOW TABLES")
assert set(metadata.tables).issubset({item[0] for item in q.fetchall()})
c.close()
'''
            run('RUNTIME_MIGRATED_SCHEMA', base + ['--env-file', str(envs['runtime']),
                                                '-e', 'APP_ENV=test', '-e', 'DB_ENABLED=false',
                                                image, 'python', '-c', version_proof])
            complete(checks, 'runtime-sees-actual-migration-head-and-model-tables')
        report = {'passed': True, 'checks': checks, 'releaseApproved': False,
                  'fullComposeStarted': False, 'realClamAVScan': 'NOT_RUN', 'productionDataAccessed': False}
    except Exception as exc:
        report = {'passed': False, 'errorType': type(exc).__name__, 'completedChecks': checks,
                  'releaseApproved': False, 'productionDataAccessed': False,
                  'failedCheck': str(exc) if re.fullmatch(r'[A-Z_]+_FAILED', str(exc)) else 'CHECK_ERROR'}
        if isinstance(exc, CheckFailure):
            report['failureDetails'] = exc.safe_details
        if created_mysql:
            report['mysqlDiagnostics'] = mysql_diagnostics(mysql)
    finally:
        cleanup_failed = []
        resources = []
        if created_mysql:
            resources.append(('mysql', ['docker', 'rm', '-f', '-v', mysql]))
        if created_network:
            resources.append(('network', ['docker', 'network', 'rm', network]))
        for kind, command in resources:
            try:
                result = subprocess.run(command, capture_output=True, timeout=30, check=False)
                if result.returncode:
                    cleanup_failed.append(kind)
            except Exception:
                cleanup_failed.append(kind)
        if cleanup_failed:
            report.update(passed=False, cleanupFailed=cleanup_failed)
    try:
        write_report(args.report_file, report)
    except Exception as exc:
        report.update(passed=False, reportWriteFailure=type(exc).__name__)
    print(json.dumps(report, indent=2))
    return 0 if report.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
