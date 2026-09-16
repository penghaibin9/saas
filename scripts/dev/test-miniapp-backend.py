"""Run mobile regression in a disposable MySQL container, never the daily school database."""
from __future__ import annotations
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4
import pymysql
from sqlalchemy.engine import URL
ROOT = Path(__file__).resolve().parents[2]
TESTS = [
    'test_mobile_action_v3_contract.py', 'test_teacher_mobile_v3_t4_student360_contract.py',
    'test_teacher_mobile_v3_t8_shared_contract.py', 'test_affairs_four_end_core_flow_matrix.py',
    'test_graduation_mobile_process.py', 'test_mobile_internship_permission_gate.py',
    'test_aa_mobile.py', 'test_mobile_aa_student_v2.py',
]
def docker(*args: str) -> str:
    result = subprocess.run(['docker', *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=45)
    if result.returncode:
        raise RuntimeError('Docker command failed; check Docker Desktop and the cached mysql:8.0 image.')
    return result.stdout.strip()
def main() -> int:
    run_id = uuid4().hex[:12]
    name = 'yueke-mobile-regression-' + run_id
    password = secrets.token_urlsafe(24)
    environment = dict(os.environ, MYSQL_ROOT_PASSWORD=secrets.token_urlsafe(24),
                       MYSQL_DATABASE='miniapp_regression_test', MYSQL_USER='qa', MYSQL_PASSWORD=password)
    logs = ROOT / '.codex-temp' / name
    logs.mkdir(parents=True, exist_ok=False)
    docker('image', 'inspect', 'mysql:8.0')  # No automatic image download or installation.
    created = False
    try:
        result = subprocess.run(['docker', 'run', '--pull=never', '--detach', '--rm', '--name', name,
            '--label', 'yueke.mobile-regression=' + run_id, '--publish', '127.0.0.1::3306',
            '-e', 'MYSQL_ROOT_PASSWORD', '-e', 'MYSQL_DATABASE', '-e', 'MYSQL_USER', '-e', 'MYSQL_PASSWORD',
            'mysql:8.0', '--innodb-flush-log-at-trx-commit=2'], env=environment,
            capture_output=True, text=True, timeout=45)
        if result.returncode: raise RuntimeError('Cannot start the isolated MySQL test container.')
        created = True
        state = json.loads(docker('inspect', name))[0]
        binding = state['NetworkSettings']['Ports']['3306/tcp'][0]
        if binding['HostIp'] != '127.0.0.1': raise RuntimeError('Refusing non-loopback test database.')
        port = int(binding['HostPort'])
        if port in {3306, 3307}: raise RuntimeError('Refusing shared or daily database ports.')
        deadline = time.monotonic() + 120
        while True:
            try:
                conn = pymysql.connect(host='127.0.0.1', port=port, user='qa', password=password,
                    database='miniapp_regression_test', connect_timeout=3, read_timeout=5, ssl_disabled=True)
                conn.close(); break
            except pymysql.MySQLError:
                if time.monotonic() >= deadline: raise RuntimeError('Isolated MySQL did not become ready.')
                time.sleep(1)
        url = URL.create('mysql+pymysql', username='qa', password=password, host='127.0.0.1', port=port,
            database='miniapp_regression_test', query={'charset': 'utf8mb4', 'ssl_disabled': 'true',
                'connect_timeout': '5', 'read_timeout': '60', 'write_timeout': '20'})
        environment.update(APP_ENV='test', ENV='test', ENVIRONMENT='test', DB_ENABLED='false',
            DATABASE_URL='', REDIS_URL='', TEST_DATABASE_URL=url.render_as_string(hide_password=False),
            FAST_TEST_SCHEMA='1', MOCK_LOGIN_ENABLED='true', PYTHONUTF8='1')
        # Mock-login is a fixture for these legacy tests only. No runtime .env is changed.
        command = [sys.executable, '-X', 'utf8', '-u', '-m', 'pytest', '-v', '--tb=short',
            '--disable-warnings', '-o', 'faulthandler_timeout=0', '--junitxml', str(logs / 'junit.xml'),
            *['tests/' + name for name in TESTS]]
        with (logs / 'pytest.log').open('wb') as output:
            result = subprocess.run(command, cwd=ROOT / 'backend', env=environment,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=900)
        print(f'Mobile MySQL regression exit={result.returncode}; evidence={logs}', flush=True)
        return result.returncode
    finally:
        if created:
            identity = json.loads(docker('inspect', name))[0]['Config']['Labels'].get('yueke.mobile-regression')
            if identity == run_id: docker('stop', '--time', '5', name)
if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error, RuntimeError) else 'Regression exceeded its bounded timeout.', file=sys.stderr)
        raise SystemExit(1)
