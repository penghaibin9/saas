"""Real local browser plus original backend; only synthetic isolated rows.

Run the two existing Vite apps at 15310/15311 with VITE_PROXY_TARGET=18310.
No mock HTTP, schema cleanup, production data or external SMS.
"""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from tests.test_phone_login_mysql import phone_db, phone_identity


def test_local_staff_phone_and_account_browser(phone_identity):
    from app.core.config import settings
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'APP_ENV': 'test', 'DEPLOYMENT_MODE': 'development', 'DB_ENABLED': 'true',
        'DATABASE_URL': os.environ['TEST_DATABASE_URL'], 'SCHEDULER_MODE': 'external',
        'SMS_ENABLED': 'false', 'SMS_PROVIDER': 'mock',
        'SENSITIVE_SEARCH_HMAC_KEY': settings.SENSITIVE_SEARCH_HMAC_KEY,
        'DEFAULT_TENANT_CODE': phone_identity['tenant'],
        'CORS_ORIGINS': 'http://127.0.0.1:15310,http://127.0.0.1:15311',
        'E2E_ALLOW_DESTRUCTIVE_TESTS': 'true', 'E2E_STAFF_BASE_URL': 'http://127.0.0.1:15310',
        'E2E_STUDENT_BASE_URL': 'http://127.0.0.1:15311/portal', 'E2E_API_BASE_URL': 'http://127.0.0.1:18310/api/v1',
        'PHONE_TEST_TENANT': phone_identity['tenant'], 'PHONE_TEST_ACCOUNT': phone_identity['login']}
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
        '--port', '18310', '--no-access-log'], cwd=root / 'backend', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ready = False
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and server.poll() is None:
            try:
                with urllib.request.urlopen('http://127.0.0.1:18310/health', timeout=1) as response:
                    ready = response.status == 200
                if ready:
                    break
            except OSError:
                time.sleep(.2)
        assert ready, 'Dedicated local backend did not become healthy'
        result = subprocess.run(['node', 'node_modules/@playwright/test/cli.js', 'test', '--config=playwright.phone.config.mjs'],
            cwd=root / 'e2e', env=env, timeout=240, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.terminate()
        server.wait(timeout=15)
