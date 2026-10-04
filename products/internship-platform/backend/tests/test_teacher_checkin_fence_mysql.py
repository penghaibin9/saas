"""Teacher-owned location decisions against real MySQL, synthetic scopes only."""
from copy import deepcopy
import math

import pytest
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipBatch, InternshipTeacherCheckin, InternshipAuditTrail
from test_yiyang_write_flows_mysql import flow, login
from test_yiyang_write_flows_mysql import seed_flow

BASE = '/api/v1/teacher-mobile/internship/activity/checkins'
LAT, LNG = 28.2282345, 112.9388765


def configured(flow, sites=None, maximum=200):
    rule = {'maxAccuracyM': maximum, 'locations': sites if sites is not None else [{
        'name': '合成巡访地点', 'centerLat': LAT, 'centerLng': LNG,
        'radiusM': 500, 'coordinateSystem': 'GCJ02'}]}
    with get_sessionmaker()() as db:
        batch = db.get(InternshipBatch, int(flow['batchId']))
        batch.rules_config = {**(batch.rules_config or {}), 'teacherCheckin': rule}
        db.commit()
    return rule


@pytest.mark.parametrize('changes,expected', [
    ({}, 'NORMAL'),
    ({'latitude': LAT + 0.02}, 'OUT_OF_RANGE'),
    ({'latitude': LAT + math.degrees(500 / 6371000), 'accuracyM': 40}, 'LOCATION_UNCERTAIN'),
    ({'accuracyM': 350}, 'LOW_ACCURACY'),
    ({'accuracyM': None}, 'LOW_ACCURACY'),
    ({'coordinateSystem': 'WGS84'}, 'LOCATION_UNCERTAIN'),
    ({'mockLocation': True}, 'MOCK_LOCATION'),
    ({'deviceRiskFlags': ['MOCK_LOCATION']}, 'MOCK_LOCATION'),
    ({'latitude': None, 'longitude': None}, 'NO_LOCATION'),
])
def test_teacher_fence_decision_is_persisted_and_audited(flow, changes, expected):
    rule = configured(flow)
    body = {'batchId': flow['batchId'], 'latitude': LAT, 'longitude': LNG,
            'accuracyM': 1, 'coordinateSystem': 'GCJ02', 'timezoneName': 'Asia/Shanghai',
            'note': '合成教师围栏检查', **changes}
    with login(flow, 'INTERN_MENTOR') as teacher:
        response = teacher.post(BASE, json=body)
        assert response.status_code == 200, response.text
        receipt = response.json()['data']
        assert receipt['result'] == expected
        reread = teacher.get(BASE, params={'batchId': flow['batchId']}).json()['data']
        stored = next(row for row in reread if row['id'] == receipt['id'])
        assert stored['result'] == expected
        for field in ('checkedInAt', 'localCheckedInAt', 'distanceM'):
            assert stored[field] == receipt[field]
    with get_sessionmaker()() as db:
        row = db.get(InternshipTeacherCheckin, int(receipt['id']))
        assert row.result == expected
        trail = db.scalar(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == int(flow['tenantId']),
            InternshipAuditTrail.target_type == 'TEACHER_CHECKIN',
            InternshipAuditTrail.target_id == row.id,
            InternshipAuditTrail.action == 'TEACHER_CHECKIN_CREATE'))
        assert trail.detail_json['detailJson']['locationDecision']['rule'] == rule
        assert trail.detail_json['detailJson']['locationDecision']['result'] == expected
        if expected in {'NORMAL', 'OUT_OF_RANGE', 'LOW_ACCURACY', 'LOCATION_UNCERTAIN'} and body['coordinateSystem'] == 'GCJ02':
            assert row.distance_m is not None


def test_teacher_without_fence_is_recorded_instead_of_declared_inside(flow):
    configured(flow, sites=[])
    with login(flow, 'INTERN_MENTOR') as teacher:
        receipt = teacher.post(BASE, json={'batchId': flow['batchId'], 'latitude': LAT,
            'longitude': LNG, 'coordinateSystem': 'GCJ02', 'accuracyM': 1}).json()['data']
        assert receipt['result'] == 'RECORDED'
        assert receipt['distanceM'] is None


def test_teacher_international_coordinates_and_second_allowed_site(flow, monkeypatch):
    from datetime import datetime, timezone
    from app.modules.internship.services import internship_teacher_activity_service as activity
    captured = datetime.now(timezone.utc).replace(microsecond=900000)

    class FractionalClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return captured.astimezone(tz) if tz else captured.replace(tzinfo=None)

    monkeypatch.setattr(activity, 'datetime', FractionalClock)
    first = {'name': '合成国内巡访点', 'centerLat': LAT, 'centerLng': LNG,
             'radiusM': 500, 'coordinateSystem': 'GCJ02'}
    second = {'name': '合成境外巡访点', 'centerLat': 35.6762, 'centerLng': 139.6503,
              'radiusM': 300, 'coordinateSystem': 'WGS84'}
    rule = configured(flow, sites=[first, second])
    with login(flow, 'INTERN_MENTOR') as teacher:
        response = teacher.post(BASE, json={'batchId': flow['batchId'],
            'latitude': second['centerLat'], 'longitude': second['centerLng'], 'accuracyM': 1,
            'coordinateSystem': 'WGS84', 'countryRegion': '日本', 'timezoneName': 'Asia/Tokyo'})
        assert response.status_code == 200, response.text
        receipt = response.json()['data']
        assert receipt['result'] == 'NORMAL' and receipt['distanceM'] == 0
        assert receipt['countryRegion'] == '日本' and receipt['coordinateSystem'] == 'WGS84'
        assert receipt['timezoneName'] == 'Asia/Tokyo'
    with get_sessionmaker()() as db:
        trail = db.scalar(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == int(flow['tenantId']),
            InternshipAuditTrail.target_type == 'TEACHER_CHECKIN',
            InternshipAuditTrail.target_id == int(receipt['id'])))
        assert trail.detail_json['detailJson']['locationDecision']['matchedLocation']['name'] == second['name']
        original = deepcopy(trail.detail_json['detailJson']['locationDecision']['rule'])
        trail_id = trail.id
        from datetime import timezone
        from zoneinfo import ZoneInfo
        saved=db.get(InternshipTeacherCheckin,int(receipt['id']))
        assert saved.checked_in_at == captured.replace(tzinfo=None, microsecond=0)
        expected_local=saved.checked_in_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M:%S')
        assert receipt['localCheckedInAt']==expected_local
        assert original == rule
        batch = db.get(InternshipBatch, int(flow['batchId']))
        batch.rules_config = {**(batch.rules_config or {}), 'teacherCheckin': {'locations': []}}
        db.commit()
    with get_sessionmaker()() as db:
        assert db.get(InternshipTeacherCheckin, int(receipt['id'])).result == 'NORMAL'
        assert db.get(InternshipAuditTrail, trail_id).detail_json['detailJson']['locationDecision']['rule'] == original


def test_teacher_corrupt_fence_configuration_never_falls_open(flow):
    configured(flow, sites=[{'name': '配置异常', 'centerLat': 999, 'centerLng': LNG,
                            'radiusM': 500, 'coordinateSystem': 'GCJ02'}])
    with login(flow, 'INTERN_MENTOR') as teacher:
        response = teacher.post(BASE, json={'batchId': flow['batchId'], 'latitude': LAT,
            'longitude': LNG, 'coordinateSystem': 'GCJ02', 'accuracyM': 1})
        assert response.status_code == 409, response.text
    with get_sessionmaker()() as db:
        assert not db.scalars(select(InternshipTeacherCheckin).where(
            InternshipTeacherCheckin.tenant_id == int(flow['tenantId']))).all()


def test_rule_read_uses_current_teacher_scope_and_denies_other_roles(flow):
    rule=configured(flow)
    path='/api/v1/teacher-mobile/internship/activity/checkin-rule'
    with login(flow,'INTERN_MENTOR') as teacher,login(flow,'STUDENT') as student:
        response=teacher.get(path,params={'batchId':flow['batchId']})
        assert response.status_code==200 and response.json()['data']['locations']==rule['locations']
        assert response.json()['data']['configured'] is True
        assert student.get(path,params={'batchId':flow['batchId']}).status_code==403
        assert teacher.get(path,params={'batchId':flow['batches'][1]['id']} if len(flow['batches'])>1 else {'batchId':1}).status_code in {403,404}
    foreign=seed_flow()
    with login(foreign,'INTERN_MENTOR') as other:
        assert other.get(path,params={'batchId':flow['batchId']}).status_code==404


def test_school_config_is_validated_and_frozen_after_normal_activation(flow):
    rule={'maxAccuracyM':100,'locations':[{'name':'合成学校巡访点','centerLat':LAT,'centerLng':LNG,'radiusM':500,'coordinateSystem':'WGS84'}]}
    body={'batchName':'合成教师范围批次','batchNo':'FENCE-'+flow['tenantId'],
          'startDate':'2026-09-01','endDate':'2026-12-30','rules':{'teacherCheckin':rule}}
    with login(flow) as school,login(flow,'INTERN_MENTOR') as teacher:
        denied=teacher.post('/api/v1/internship/batches',json=body)
        assert denied.status_code==403,denied.text
        invalid=school.post('/api/v1/internship/batches',json={**body,'rules':{'teacherCheckin':{'locations':[{'name':'缺坐标'}]}}})
        assert invalid.status_code in {400,422},invalid.text
        response=school.post('/api/v1/internship/batches',json=body)
        assert response.status_code==200,response.text
        identifier=response.json()['data']['id']
        detail=school.get('/api/v1/internship/batches/'+identifier).json()['data']
        assert detail['rules']['teacherCheckin']==rule
        activated=school.post('/api/v1/internship/batches/'+identifier+'/activate',json={'expectedVersion':detail['version']})
        assert activated.status_code==200,activated.text
        current=school.get('/api/v1/internship/batches/'+identifier).json()['data']
        assert current['status']=='RUNNING' and current['rules']['teacherCheckin']==rule
        changed=school.put('/api/v1/internship/batches/'+identifier,json={'expectedVersion':current['version'],'rules':{'teacherCheckin':{'locations':[]}}})
        assert changed.status_code==400 and changed.json()['bizCode']=='DATA_CONFLICT',changed.text
        assert school.get('/api/v1/internship/batches/'+identifier).json()['data']['rules']['teacherCheckin']==rule


@pytest.mark.parametrize('status',['DRAFT','CLOSED','ARCHIVED','VOID'])
def test_nonrunning_batch_cannot_create_new_teacher_checkin(flow,status):
    configured(flow)
    with get_sessionmaker()() as db:
        db.get(InternshipBatch,int(flow['batchId'])).status=status
        db.commit()
    with login(flow,'INTERN_MENTOR') as teacher:
        rule=teacher.get('/api/v1/teacher-mobile/internship/activity/checkin-rule',params={'batchId':flow['batchId']}).json()['data']
        assert rule['canCheckin'] is False and rule['unavailableReason']
        response=teacher.post(BASE,json={'batchId':flow['batchId'],'latitude':LAT,'longitude':LNG,'accuracyM':1,'coordinateSystem':'GCJ02'})
        assert response.status_code==409,response.text
    with get_sessionmaker()() as db:
        assert not db.scalars(select(InternshipTeacherCheckin).where(InternshipTeacherCheckin.tenant_id==int(flow['tenantId']))).all()
