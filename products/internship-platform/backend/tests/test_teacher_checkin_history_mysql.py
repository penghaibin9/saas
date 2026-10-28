"""Teacher history and school exports, real isolated MySQL and normal roles."""
from base64 import b64decode
from datetime import date, datetime, time, timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import insert, select

from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, InternshipTeacherCheckin
from app.models.audit_outbox import AuditOutbox
from test_yiyang_write_flows_mysql import flow, login, seed_flow

OWN = '/api/v1/teacher-mobile/internship/activity/checkins'
MANAGED = '/api/v1/internship/teacher-management/checkins'


def prepare_history(flow, count, *, teacher_id=None, end=None):
    # Historical facts are isolated fixtures, not browser acceptance actions.
    end = end or date.today() - timedelta(days=1)
    teacher_id = teacher_id or flow['users']['INTERN_MENTOR']
    rows = [{'tenant_id': int(flow['tenantId']), 'batch_id': int(flow['batchId']),
             'teacher_user_id': teacher_id, 'teacher_name_snapshot': '合成历史教师',
             'local_date': end-timedelta(days=index), 'timezone_name': 'Asia/Shanghai',
             'checked_in_at': datetime.combine(end-timedelta(days=index), time(1)),
             'result': 'RECORDED', 'note': '合成历史签到', 'is_deleted': False}
            for index in range(count)]
    with get_sessionmaker()() as db:
        db.execute(insert(InternshipTeacherCheckin), rows)
        db.commit()
    return rows


def test_month_reads_all_owned_history_beyond_recent_366_and_preserves_legacy_limit(flow):
    prepared = prepare_history(flow, 410)
    month = (date.today()-timedelta(days=390)).strftime('%Y-%m')
    expected = {row['local_date'].isoformat() for row in prepared if row['local_date'].strftime('%Y-%m') == month}
    prepare_history(flow, 4, teacher_id=flow['users']['SCHOOL_ADMIN'], end=date.fromisoformat(month+'-15'))
    with login(flow, 'INTERN_MENTOR') as teacher:
        response = teacher.get(OWN, params={'batchId': flow['batchId'], 'month': month, 'limit': 1})
        assert response.status_code == 200, response.text
        rows = response.json()['data']
        assert {row['localDate'] for row in rows} == expected and len(rows) > 1
        assert all(row['teacherUserId'] == str(flow['users']['INTERN_MENTOR']) for row in rows)
        assert len(teacher.get(OWN, params={'batchId': flow['batchId'], 'limit': 2}).json()['data']) == 2


@pytest.mark.parametrize('month', ['2026-00', '2026-13', '0000-01', '2026-1'])
def test_invalid_month_never_returns_unrelated_recent_history(flow, month):
    with login(flow, 'INTERN_MENTOR') as teacher:
        response = teacher.get(OWN, params={'batchId': flow['batchId'], 'month': month})
        assert response.status_code in (400, 422), response.text


def test_formal_teacher_note_admin_read_export_and_audit_are_same_fact(flow):
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow) as school:
        response = teacher.post(OWN, json={'batchId': flow['batchId'],
            'latitude': 35.6762, 'longitude': 139.6503, 'accuracyM': 1,
            'coordinateSystem': 'WGS84', 'countryRegion': '日本', 'timezoneName': 'Asia/Tokyo',
            'address': '+合成现场地址', 'note': '=合成教师备注，不执行公式'})
        assert response.status_code == 200, response.text
        receipt = response.json()['data']
        response = school.get(MANAGED, params={'batchId': flow['batchId']})
        assert response.status_code == 200, response.text
        managed = response.json()['data']
        assert managed['total'] == 1 and managed['items'][0]['id'] == receipt['id']
        assert managed['items'][0]['note'] == receipt['note']
        assert managed['items'][0]['localCheckedInAt'] == receipt['localCheckedInAt']
        exported = school.post(MANAGED+'/export', params={'batchId': flow['batchId']})
        assert exported.status_code == 200, exported.text
        data = exported.json()['data']
        workbook = load_workbook(BytesIO(b64decode(data['contentBase64'])))
        values = list(workbook.active.values)
        assert any("'=合成教师备注，不执行公式" in row for row in values)
        assert any("'+合成现场地址" in row for row in values)
        assert any(receipt['localCheckedInAt'] in row for row in values)
        assert not any('RECORDED' in row or 'WGS84' in row for row in values)
        assert not any(cell.data_type == 'f' for row in workbook.active for cell in row)
    with get_sessionmaker()() as db:
        trails = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == int(flow['tenantId']),
            InternshipAuditTrail.action == 'TEACHER_CHECKIN_EXPORT')).all()
        assert len(trails) == 1 and trails[0].detail_json['detailJson']['rowCount'] == 1
        assert len(db.scalars(select(AuditOutbox).where(
            AuditOutbox.tenant_id == int(flow['tenantId']),
            AuditOutbox.event_type == 'INTERNSHIP_TEACHER_CHECKIN_EXPORT')).all()) == 1


def test_managed_history_pagination_filters_and_reversed_dates(flow):
    prepare_history(flow, 45)
    prepare_history(flow, 2, teacher_id=flow['users']['SCHOOL_ADMIN'])
    params = {'batchId': flow['batchId'], 'teacherUserId': flow['users']['INTERN_MENTOR'],
              'result': 'RECORDED', 'pageSize': 10}
    with login(flow) as school:
        first = school.get(MANAGED, params=params)
        assert first.status_code == 200, first.text
        data = first.json()['data']
        assert data['total'] == 45 and len(data['items']) == 10
        second = school.get(MANAGED, params={**params, 'page': 2}).json()['data']
        assert not set(row['id'] for row in data['items']) & set(row['id'] for row in second['items'])
        dates = {'startDate': (date.today()-timedelta(days=5)).isoformat(),
                 'endDate': (date.today()-timedelta(days=3)).isoformat()}
        narrowed = school.get(MANAGED, params={**params, **dates}).json()['data']
        assert narrowed['total'] == 3
        bad = school.get(MANAGED, params={**params, 'startDate': dates['endDate'], 'endDate': dates['startDate']})
        assert bad.status_code == 400, bad.text
        assert school.get(MANAGED, params={**params, 'result': 'UNRECOGNIZED'}).status_code in (400, 422)


def test_history_and_export_reject_other_role_scope_and_tenant(flow):
    foreign = seed_flow()
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow, 'STUDENT') as student, login(foreign) as other_school:
        for client in (teacher, student):
            assert client.get(MANAGED, params={'batchId': flow['batchId']}).status_code == 403
            assert client.post(MANAGED+'/export', params={'batchId': flow['batchId']}).status_code == 403
        assert other_school.get(MANAGED, params={'batchId': flow['batchId']}).status_code == 404
        assert other_school.post(MANAGED+'/export', params={'batchId': flow['batchId']}).status_code == 404
        assert student.get(OWN, params={'batchId': flow['batchId'], 'month': '2025-01'}).status_code == 403
        assert teacher.get(OWN, params={'batchId': flow['batches'][1]['id'], 'month': '2025-01'}).status_code == 403


def test_export_over_limit_refuses_truncation_and_narrowed_export_keeps_all_rows(flow):
    prepare_history(flow, 5001)
    with login(flow) as school:
        too_large = school.post(MANAGED+'/export', params={'batchId': flow['batchId']})
        assert too_large.status_code == 400 and '5000' in too_large.json()['message'], too_large.text
        with get_sessionmaker()() as db:
            assert db.scalar(select(InternshipAuditTrail.id).where(
                InternshipAuditTrail.tenant_id == int(flow['tenantId']),
                InternshipAuditTrail.action == 'TEACHER_CHECKIN_EXPORT')) is None
        narrowed = school.post(MANAGED+'/export', params={'batchId': flow['batchId'],
            'startDate': (date.today()-timedelta(days=5)).isoformat(), 'endDate': (date.today()-timedelta(days=1)).isoformat()})
        assert narrowed.status_code == 200 and narrowed.json()['data']['rowCount'] == 5, narrowed.text
