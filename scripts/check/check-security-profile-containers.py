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


def run(label, command, *, timeout=60, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False, **kwargs)
    if result.returncode:
        # Commands/container output may contain environment variables: do not echo them.
        raise RuntimeError(label + '_FAILED')
    return result.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-ci-only', action='store_true')
    args = parser.parse_args(argv)
    if not args.disposable_ci_only or os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('This check is restricted to an explicitly acknowledged disposable GitHub runner')
    root = Path(__file__).resolve().parents[2]
    suffix = secrets.token_hex(6)
    image, network, mysql = ('pr265-security-' + kind + '-' + suffix for kind in ('image', 'net', 'mysql'))
    created_mysql = created_network = False
    checks = []
    try:
        with tempfile.TemporaryDirectory(prefix='pr265-container-check-') as directory:
            folder = Path(directory)
            # Capture the exact base digest used in this CI build. This is NOT a vulnerability scan.
            run('PULL_PYTHON', ['docker', 'pull', 'python:3.12-slim'], timeout=180)
            python_digest = run('PYTHON_DIGEST', ['docker', 'image', 'inspect', 'python:3.12-slim',
                                                  '--format', '{{index .RepoDigests 0}}'])
            run('BUILD', ['docker', 'build', '-f', 'backend/Dockerfile.security', '--build-arg',
                          'PYTHON_BASE_IMAGE=' + python_digest, '-t', image, '.'], timeout=900, cwd=root)
            checks.append('security-image-build')
            run('IMAGE_CONTRACT', ['docker', 'run', '--rm', '--network', 'none', '--read-only',
                                   '--cap-drop=ALL', '--security-opt=no-new-privileges', image,
                                   'python', 'scripts/security_profile_probe.py', 'image'])
            checks.append('nonroot-image-runtime-contracts')
            run('APP_IMPORT', ['docker', 'run', '--rm', '--network', 'none', '--read-only',
                              '--tmpfs', '/tmp:rw,nosuid,nodev,noexec', '--cap-drop=ALL',
                              '--security-opt=no-new-privileges', '-e', 'APP_ENV=test', '-e', 'DB_ENABLED=false',
                              '-e', 'DEBUG=false', '-e', 'MOCK_LOGIN_ENABLED=false', image,
                              'python', '-c', 'import app.main; from app.core.module_registry import load_module_manifest; assert load_module_manifest()["modules"]'], timeout=90)
            checks.append('complete-app-route-import-no-database')
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
            ci_images = {'APP_IMAGE': image, 'PYTHON_BASE_IMAGE': python_digest, 'MYSQL_IMAGE': 'mysql:8.0',
                         'REDIS_IMAGE': 'redis:7-alpine', 'NGINX_IMAGE': 'nginx:stable-alpine',
                         'CLAMAV_IMAGE': 'clamav/clamav:stable'}
            for key, value in ci_images.items():
                content = content.replace(f'{key}=REQUIRED_REVIEWED_DIGEST', f'{key}={value}')
            env_path.write_text(content)
            run('COMPOSE_SYNTAX', ['docker', 'compose', '--env-file', str(env_path), '-f',
                                  str(folder / 'deploy/docker/docker-compose.security.yml'), 'config', '-q'])
            checks.append('real-docker-compose-render')
            passwords = {key: secrets.token_hex(32) for key in ('root', 'runtime', 'migrator')}
            mysql_env = folder / 'mysql.env'
            mysql_env.write_text('MYSQL_DATABASE=saas_lifecycle\nMYSQL_USER=saas_runtime\n' +
                                 f'MYSQL_PASSWORD={passwords["runtime"]}\nMYSQL_ROOT_PASSWORD={passwords["root"]}\n' +
                                 f'MIGRATOR_PASSWORD={passwords["migrator"]}\n')
            mysql_env.chmod(0o600)
            run('CREATE_NETWORK', ['docker', 'network', 'create', '--internal', network])
            created_network = True
            run('MYSQL_START', ['docker', 'run', '-d', '--name', mysql, '--network', network, '--network-alias', 'mysql',
                               '--env-file', str(mysql_env), '--mount',
                               f'type=bind,src={root / "deploy/docker/mysql-security-init/01-accounts.sh"},dst=/docker-entrypoint-initdb.d/01-accounts.sh,readonly',
                               'mysql:8.0'], timeout=180)
            created_mysql = True
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
            for attempt in range(60):
                try:
                    run('MYSQL_WAIT', base + ['--env-file', str(envs['migrator']), image, 'python', '-c', client + 'q.execute("SELECT 1")'])
                    break
                except RuntimeError:
                    if attempt == 59:
                        raise
                    time.sleep(2)
            run('MIGRATOR_DDL', base + ['--env-file', str(envs['migrator']), image, 'python', '-c',
                                      client + 'q.execute("CREATE TABLE pr265_privilege_probe (id INT PRIMARY KEY, value INT)")'])
            checks.append('migrator-schema-ddl-allowed')
            sql_test = client + '''
q.execute("INSERT INTO pr265_privilege_probe VALUES (1,2)")
q.execute("UPDATE pr265_privilege_probe SET value=3 WHERE id=1")
q.execute("SELECT value FROM pr265_privilege_probe WHERE id=1")
assert q.fetchone() == (3,)
q.execute("DELETE FROM pr265_privilege_probe WHERE id=1")
for sql in ("CREATE TABLE forbidden_probe (id INT)", "SELECT User FROM mysql.user", "CREATE USER 'forbidden_probe'@'%'"):
    try:
        q.execute(sql)
    except pymysql.MySQLError as exc:
        assert exc.args[0] in {1044, 1142, 1227}, exc.args[0]
    else:
        raise AssertionError("runtime privilege boundary failed")
c.close()
'''
            run('RUNTIME_PRIVILEGES', base + ['--env-file', str(envs['runtime']), image, 'python', '-c', sql_test])
            checks.append('runtime-dml-allowed-ddl-system-users-denied')
    except Exception as exc:
        print(json.dumps({'passed': False, 'errorType': type(exc).__name__, 'completedChecks': checks,
                          'releaseApproved': False, 'productionDataAccessed': False,
                          'failedCheck': str(exc) if re.fullmatch(r'[A-Z_]+_FAILED', str(exc)) else 'CHECK_ERROR'}))
        return 1
    finally:
        if created_mysql:
            subprocess.run(['docker', 'rm', '-f', '-v', mysql], capture_output=True, timeout=30)
        if created_network:
            subprocess.run(['docker', 'network', 'rm', network], capture_output=True, timeout=30)
    print(json.dumps({'passed': True, 'checks': checks, 'releaseApproved': False,
                      'fullComposeStarted': False, 'realClamAVScan': 'NOT_RUN', 'productionDataAccessed': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
