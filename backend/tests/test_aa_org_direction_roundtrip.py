"""Professional directions: real DB versions, history, scope and atomic writes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import importlib

import pytest
from sqlalchemy import func, select

from test_aa_orgs_tier1_r2 import BASE, TID, _hdr, _seed_scoped


def _setup(client, db_mode):
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    response = client.post(f'{BASE}/major-direction-toggle', headers=headers, json={'enabled': True})
    assert response.status_code == 200
    return ids, headers, f"{BASE}/majors/{ids['majSw']}/directions"


def test_toggle_read_is_pure_and_stale_setting_cannot_overwrite(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig
    headers = _hdr(client, 'school_admin01')
    url = f'{BASE}/major-direction-toggle'
    assert client.get(url, headers=headers).json()['data'] == {'enabled': False, 'version': 0}
    with get_sessionmaker()() as db:
        assert not db.scalar(select(PlatformConfig).where(PlatformConfig.config_type == 'AA_FEATURE_TOGGLE'))
    first = client.post(url, headers=headers, json={'enabled': True, 'expectedVersion': 0}).json()['data']
    assert first == {'enabled': True, 'version': 1}
    stale = client.post(url, headers=headers, json={'enabled': False, 'expectedVersion': 0})
    assert stale.status_code == 409
    assert client.get(url, headers=headers).json()['data'] == first
    assert client.post(url, headers=headers, json={'enabled': True, 'expectedVersion': 1}).json()['data'] == first


def test_direction_versions_normalization_null_clear_and_disabled_history(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail
    _, headers, url = _setup(client, db_mode)
    created = client.post(url, headers=headers, json={'directionName': '  软件开发  ', 'code': '  DEV  '}).json()['data']
    assert (created['directionName'], created['code'], created['version']) == ('软件开发', 'DEV', 0)
    item = f"{url}/{created['id']}"
    updated = client.put(item, headers=headers, json={'directionName': '  全栈开发 ', 'code': None, 'expectedVersion': 0}).json()['data']
    assert (updated['directionName'], updated['code'], updated['version']) == ('全栈开发', None, 1)
    assert client.put(item, headers=headers, json={'directionName': '旧名称', 'expectedVersion': 0}).status_code == 409
    assert client.post(f'{item}/disable', headers=headers, json={'expectedVersion': 0}).status_code == 409
    disabled = client.post(f'{item}/disable', headers=headers, json={'expectedVersion': 1}).json()['data']
    assert disabled['status'] == 'DISABLED' and disabled['version'] == 2
    assert client.post(f'{item}/disable', headers=headers, json={'expectedVersion': 1}).json()['data'] == disabled
    assert client.put(item, headers=headers, json={'directionName': '改写历史', 'expectedVersion': 2}).status_code == 409
    assert client.get(url, headers=headers).json()['data']['items'] == [disabled]
    with get_sessionmaker()() as db:
        actions = db.scalars(select(AffairsAuditTrail.action).where(
            AffairsAuditTrail.biz_type == 'AA_ORG_MAJOR_DIRECTION', AffairsAuditTrail.biz_id == int(created['id']))).all()
        assert sorted(actions) == ['DIRECTION_CREATE', 'DIRECTION_DISABLE', 'DIRECTION_UPDATE']


def test_inactive_parents_and_reserved_historical_code_block_writes(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaMajorDirection, College, Major
    ids, headers, url = _setup(client, db_mode)
    created = client.post(url, headers=headers, json={'directionName': '原方向', 'code': 'HISTORY'}).json()['data']
    with get_sessionmaker()() as db:
        db.get(Major, ids['majSw']).status = 'DISABLED'
        db.commit()
    assert client.post(url, headers=headers, json={'directionName': '停用专业下新增'}).status_code == 400
    assert client.put(f"{url}/{created['id']}", headers=headers, json={'directionName': '修改'}).status_code == 400
    with get_sessionmaker()() as db:
        db.get(Major, ids['majSw']).status = 'ACTIVE'
        db.get(College, ids['colSw']).status = 'DISABLED'
        db.commit()
    assert client.post(url, headers=headers, json={'directionName': '停用学院下新增'}).status_code == 400
    with get_sessionmaker()() as db:
        db.get(College, ids['colSw']).status = 'ACTIVE'
        db.get(AaMajorDirection, int(created['id'])).is_deleted = True
        db.commit()
    assert client.post(url, headers=headers, json={'directionName': '历史编码', 'code': ' HISTORY '}).status_code == 409


def test_pagination_validation_and_switch_off_preserve_records(client, db_mode):
    _, headers, url = _setup(client, db_mode)
    for n in range(3):
        assert client.post(url, headers=headers, json={'directionName': f'方向{n}'}).status_code == 200
    first = client.get(url, headers=headers, params={'page': 1, 'pageSize': 2}).json()['data']
    second = client.get(url, headers=headers, params={'page': 2, 'pageSize': 2}).json()['data']
    assert first['total'] == second['total'] == 3 and len(second['items']) == 1
    assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
    for params in ({'page': 0}, {'pageSize': 0}, {'pageSize': 201}):
        assert client.get(url, headers=headers, params=params).status_code == 400
    for body in ({'directionName': 'x' * 201}, {'directionName': '方向', 'code': 'x' * 51}):
        assert client.post(url, headers=headers, json=body).status_code == 400
    client.post(f'{BASE}/major-direction-toggle', headers=headers, json={'enabled': False})
    assert client.put(f"{url}/{first['items'][0]['id']}", headers=headers, json={'directionName': '关闭后修改'}).status_code == 400
    client.post(f'{BASE}/major-direction-toggle', headers=headers, json={'enabled': True})
    assert client.get(url, headers=headers, params={'pageSize': 2}).json()['data'] == first


def test_concurrent_direction_edits_have_one_winner(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaMajorDirection, AffairsAuditTrail
    _, headers, url = _setup(client, db_mode)
    created = client.post(url, headers=headers, json={'directionName': '并发修改'}).json()['data']
    barrier = Barrier(2)
    def save(name):
        barrier.wait(timeout=10)
        return client.put(f"{url}/{created['id']}", headers=headers, json={'directionName': name, 'expectedVersion': 0})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ['甲更新', '乙更新']))
    assert sorted(r.status_code for r in results) == [200, 409]
    with get_sessionmaker()() as db:
        assert db.get(AaMajorDirection, int(created['id'])).version == 1
        assert db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.biz_type == 'AA_ORG_MAJOR_DIRECTION', AffairsAuditTrail.action == 'DIRECTION_UPDATE')) == 1


def test_concurrent_initial_toggle_and_duplicate_creation_are_serialized(client, db_mode):
    ids = _seed_scoped(db_mode)
    headers = _hdr(client, 'school_admin01')
    barrier = Barrier(2)
    def enable(_):
        barrier.wait(timeout=10)
        return client.post(f'{BASE}/major-direction-toggle', headers=headers, json={'enabled': True, 'expectedVersion': 0})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(enable, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    barrier = Barrier(2)
    def create(_):
        barrier.wait(timeout=10)
        return client.post(f"{BASE}/majors/{ids['majSw']}/directions", headers=headers, json={'directionName': '重复提交', 'code': 'SAME'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]


def test_direction_audit_failure_rolls_back_record(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaMajorDirection, PlatformConfig
    svc = importlib.import_module('app.modules.academic_affairs.services.academic_affairs_org_service')
    _, headers, url = _setup(client, db_mode)
    created = client.post(url, headers=headers, json={'directionName': '原方向'}).json()['data']
    def fail(*args, **kwargs):
        raise RuntimeError('direction audit failure')
    monkeypatch.setattr(svc, '_audit', fail)
    with pytest.raises(RuntimeError, match='direction audit failure'):
        client.put(f"{url}/{created['id']}", headers=headers, json={'directionName': '不应保存', 'expectedVersion': 0})
    with pytest.raises(RuntimeError, match='direction audit failure'):
        client.post(f"{url}/{created['id']}/disable", headers=headers, json={'expectedVersion': 0})
    with pytest.raises(RuntimeError, match='direction audit failure'):
        client.post(f'{BASE}/major-direction-toggle', headers=headers, json={'enabled': False, 'expectedVersion': 1})
    with get_sessionmaker()() as db:
        row = db.get(AaMajorDirection, int(created['id']))
        assert (row.direction_name, row.status, row.version) == ('原方向', 'ACTIVE', 0)
        toggle = db.scalar(select(PlatformConfig).where(PlatformConfig.tenant_id == TID, PlatformConfig.config_type == 'AA_FEATURE_TOGGLE'))
        assert toggle.enabled and toggle.version == 1
