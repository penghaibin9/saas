"""Run before other acceptance tests, only against the explicitly isolated empty database."""
import json
import os
from pathlib import Path
import runpy
import secrets

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url


def test_empty_install_normal_login_and_first_school_setup(tmp_path):
    if os.environ.get('SYSTEM_EMPTY_INSTALL_ACCEPTANCE') != '1':
        pytest.skip('requires an explicitly isolated empty database')
    from app.config import settings
    url = make_url(settings.DATABASE_URL)
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and settings.APP_ENV == 'ci'
    assert url.host == '127.0.0.1' and url.port == 3306 and url.database == 'internship_auth_gate'
    from app.db.session import get_sessionmaker
    from app.models import Tenant, User, StudentProfile, StaffProfile, College, InternshipBatch
    models = (Tenant, User, StudentProfile, StaffProfile, College, InternshipBatch)

    def counts():
        with get_sessionmaker()() as db:
            return [db.scalar(select(func.count()).select_from(model)) for model in models]

    assert counts() == [0] * len(models), 'Empty-install test must precede all data-seeding tests'
    initialize = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/initialize_school.py'))['initialize']
    receipt = tmp_path / 'owner.json'
    initialize('EMPTY-INSTALL', '空库安装合成学校', 'owner', receipt)
    assert counts() == [1, 1, 0, 0, 0, 0]
    with pytest.raises(ValueError, match='禁止重复初始化'):
        initialize('ANOTHER', '不得新建第二所学校', 'other', tmp_path / 'second.json')
    assert counts() == [1, 1, 0, 0, 0, 0]
    assert not (tmp_path / 'second.json').exists()

    from fastapi.testclient import TestClient
    from app.main import app
    credentials = json.loads(receipt.read_text(encoding='utf-8'))
    password = 'Aa9!' + secrets.token_urlsafe(24)

    def ok(response):
        # Credential-bearing responses must never appear in assertion output.
        assert response.status_code == 200, response.status_code
        assert response.json()['code'] == 0
        return response.json()['data']

    with TestClient(app) as client:
        client.headers['X-Browser-Session-Id'] = 'empty-install-' + secrets.token_hex(12)
        login = {'tenantCode': 'EMPTY-INSTALL', 'loginName': 'owner', 'clientType': 'PC'}
        logged = ok(client.post('/api/v1/auth/browser-login', json={**login, 'password': credentials['temporaryPassword']}))
        assert logged['mustChangePassword']
        client.headers['Authorization'] = 'Bearer ' + logged['accessToken']
        assert client.get('/api/v1/system/overview').status_code == 403
        ok(client.post('/api/v1/auth/change-password', json={'currentPassword': credentials['temporaryPassword'], 'newPassword': password}))
        logged = ok(client.post('/api/v1/auth/browser-login', json={**login, 'password': password}))
        assert not logged['mustChangePassword']
        client.headers['Authorization'] = 'Bearer ' + logged['accessToken']
        assert ok(client.get('/api/v1/system/overview'))['studentCount'] == 0
        college = ok(client.post('/api/v1/system/organizations/colleges', json={
            'name': '首个合成院系', 'code': 'C01', 'parentId': '', 'reason': '空学校正式初始化办理'}))
        assert college['id']
        assert counts() == [1, 1, 0, 0, 1, 0]
