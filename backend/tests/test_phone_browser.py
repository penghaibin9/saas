"""Real local browser plus original backend; only synthetic isolated rows.

Run the two existing Vite apps at 15310/15311 with VITE_PROXY_TARGET=18310.
No mock HTTP, schema cleanup, production data or external SMS.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

import pytest

from tests.test_phone_login_mysql import phone_db, phone_identity


@pytest.fixture
def phone_surface_identities(phone_db, phone_identity):
    """Prepare a synthetic student through the existing identity entities.

    The browser story still performs the real first-login password mutation.  A
    VERIFIED binding is fixture state for testing PHONE login; it is not evidence
    that an xlsx candidate became verified.
    """
    from datetime import datetime
    from app.core.field_crypto import encrypt_sensitive
    from app.core.security import hash_password
    from app.models import PhoneLoginBinding, Role, StudentAccountLink, StudentProfile, User, UserRole
    from app.services.phone_login_service import phone_lookup

    suffix = secrets.token_hex(5)
    account = 'student-' + suffix
    initial_account = 'student-new-' + suffix
    phone = '137' + str(secrets.randbelow(10**8)).zfill(8)
    teacher_account = 'mini-teacher-' + suffix
    teacher_phone = '139' + str(secrets.randbelow(10**8)).zfill(8)
    role = Role(tenant_id=phone_identity['tenant_id'], role_code='STUDENT', role_name='学生')
    teacher_role = phone_db.query(Role).filter(Role.tenant_id == phone_identity['tenant_id'],
        Role.role_code == 'ACADEMIC_TEACHER').one()
    profile = StudentProfile(tenant_id=phone_identity['tenant_id'], student_no=account,
        real_name='虚构学生移动验收', grade='2026')
    initial_profile = StudentProfile(tenant_id=phone_identity['tenant_id'], student_no=initial_account,
        real_name='虚构学生首登验收', grade='2026')
    user = User(tenant_id=phone_identity['tenant_id'], login_name=account,
        real_name=profile.real_name, password_hash=hash_password('Student-local-Password2!'),
        user_type='STUDENT', must_change_password=False)
    initial_user = User(tenant_id=phone_identity['tenant_id'], login_name=initial_account,
        real_name=initial_profile.real_name, password_hash=hash_password('Student-initial-Password1!'),
        user_type='STUDENT', must_change_password=True)
    teacher = User(tenant_id=phone_identity['tenant_id'], login_name=teacher_account,
        real_name='虚构教师移动验收', password_hash=hash_password('Local-test-Password1!'), user_type='TEACHER')
    phone_db.add_all([role, profile, initial_profile, user, initial_user, teacher])
    phone_db.flush()
    phone_db.add_all([
        UserRole(tenant_id=phone_identity['tenant_id'], user_id=user.id, role_id=role.id, status='ACTIVE'),
        UserRole(tenant_id=phone_identity['tenant_id'], user_id=initial_user.id, role_id=role.id, status='ACTIVE'),
        UserRole(tenant_id=phone_identity['tenant_id'], user_id=teacher.id, role_id=teacher_role.id, status='ACTIVE'),
        StudentAccountLink(tenant_id=phone_identity['tenant_id'], student_id=profile.id, user_id=user.id,
            link_status='ACTIVE', bound_login_name=account, bound_student_no=account,
            source='IDENTITY_IMPORT', bound_at=datetime.utcnow()),
        StudentAccountLink(tenant_id=phone_identity['tenant_id'], student_id=initial_profile.id, user_id=initial_user.id,
            link_status='ACTIVE', bound_login_name=initial_account, bound_student_no=initial_account,
            source='IDENTITY_IMPORT', bound_at=datetime.utcnow()),
        PhoneLoginBinding(tenant_id=phone_identity['tenant_id'], user_id=user.id, state='VERIFIED',
            active_phone_lookup=phone_lookup(phone_identity['tenant_id'], phone),
            phone_ciphertext=encrypt_sensitive(phone), version=1),
        PhoneLoginBinding(tenant_id=phone_identity['tenant_id'], user_id=teacher.id, state='VERIFIED',
            active_phone_lookup=phone_lookup(phone_identity['tenant_id'], teacher_phone),
            phone_ciphertext=encrypt_sensitive(teacher_phone), version=1),
    ])
    phone_db.commit()
    return {'student_account': account, 'student_phone': phone, 'initial_student_account': initial_account,
        'teacher_account': teacher_account, 'teacher_phone': teacher_phone}


def test_local_four_surface_phone_and_account_browser(phone_identity, phone_surface_identities):
    from app.core.config import settings
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'APP_ENV': 'test', 'DEPLOYMENT_MODE': 'development', 'DB_ENABLED': 'true',
        'DATABASE_URL': os.environ['TEST_DATABASE_URL'], 'SCHEDULER_MODE': 'external',
        'SMS_ENABLED': 'false', 'SMS_PROVIDER': 'mock',
        'SENSITIVE_SEARCH_HMAC_KEY': settings.SENSITIVE_SEARCH_HMAC_KEY,
        'DEFAULT_TENANT_CODE': phone_identity['tenant'],
        'CORS_ORIGINS': 'http://127.0.0.1:15310,http://127.0.0.1:15311,http://localhost:5189',
        'E2E_ALLOW_DESTRUCTIVE_TESTS': 'true', 'E2E_STAFF_BASE_URL': 'http://127.0.0.1:15310',
        'E2E_STUDENT_BASE_URL': 'http://127.0.0.1:15311/portal', 'E2E_API_BASE_URL': 'http://127.0.0.1:18310/api/v1',
        'PHONE_TEST_TENANT': phone_identity['tenant'], 'PHONE_TEST_ACCOUNT': phone_identity['login'],
        'PHONE_TEST_STUDENT_ACCOUNT': phone_surface_identities['student_account'],
        'PHONE_TEST_STUDENT_PHONE': phone_surface_identities['student_phone'],
        'PHONE_TEST_INITIAL_STUDENT_ACCOUNT': phone_surface_identities['initial_student_account'],
        'PHONE_TEST_MINI_TEACHER_ACCOUNT': phone_surface_identities['teacher_account'],
        'PHONE_TEST_MINI_TEACHER_PHONE': phone_surface_identities['teacher_phone'],
        'PHONE_TEST_MINI_BASE_URL': 'http://localhost:5189'}
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
        command = ['node', 'node_modules/@playwright/test/cli.js', 'test', '--config=playwright.phone.config.mjs']
        if os.environ.get('PHONE_E2E_GREP'):
            command.extend(['--grep', os.environ['PHONE_E2E_GREP']])
        result = subprocess.run(command,
            cwd=root / 'e2e', env=env, timeout=240, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.terminate()
        server.wait(timeout=15)
