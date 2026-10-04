"""Actual MySQL round trips and normal-account fence decisions; synthetic schools only."""
from uuid import uuid4
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import inspect, select

from app.db.session import get_sessionmaker
from app.models import EmpCompany, InternshipBatch, InternshipCheckin, InternshipPosition, InternshipRecord
from app.models.audit_outbox import AuditOutbox
from app.models.file import FileBinding, FileObject
from app.config import settings
from app.services.storage import get_backend
from test_yiyang_write_flows_mysql import flow, login, upload, seed_flow
from test_student_weekly_detail_mysql import teammate

LAT, LNG = 28.22823456789, 112.93887654321
BASE = '/api/v1/mobile/internship/checkin'


def fence(flow):
    with get_sessionmaker()() as db:
        company = EmpCompany(tenant_id=int(flow['tenantId']), name='合成定位精度企业', coop_status='ACTIVE')
        db.add(company); db.flush()
        position = InternshipPosition(tenant_id=int(flow['tenantId']), company_id=company.id,
            company_name=company.name, batch_id=int(flow['batchId']), title='合成围栏岗位', status='PUBLISHED',
            geofence_lat=LAT, geofence_lng=LNG, geofence_radius_m=5)
        db.add(position); db.flush()
        record = db.get(InternshipRecord, int(flow['recordId']))
        record.position_id = position.id
        batch = db.get(InternshipBatch, record.batch_id)
        batch.rules_config = {'checkin': {'maxAccuracyM': 10}}
        db.commit()
        return position.id


def checkin(student, flow, **changes):
    params = {'batchId': flow['batchId'], 'timezoneName': 'Asia/Shanghai'}
    preflight = student.post(BASE+'/preflight', params=params)
    assert preflight.status_code == 200, preflight.text
    body = {'batchId':flow['batchId'], 'checkinToken':preflight.json()['data']['token'],
            'idempotencyKey':uuid4().hex, 'timezoneName':'Asia/Shanghai', 'lat':LAT, 'lng':LNG,
            'gpsAccuracy':1, 'coordinateSystem':'GCJ02', 'locationProvider':'SYNTHETIC_TEST',
            'note':'合成围栏精度验收', **changes}
    return student.post(BASE, params={'batchId':flow['batchId']}, json=body)


def test_mysql_position_and_checkin_coordinates_preserve_input_precision(flow):
    position_id = fence(flow)
    with get_sessionmaker()() as db:
        position = db.get(InternshipPosition, position_id)
        assert abs(position.geofence_lat-LAT) < 1e-10
        assert abs(position.geofence_lng-LNG) < 1e-10
    with login(flow,'STUDENT') as student:
        response = checkin(student, flow)
        assert response.status_code == 200 and response.json()['data']['result'] == 'NORMAL', response.text
    with get_sessionmaker()() as db:
        row = db.scalar(select(InternshipCheckin).where(InternshipCheckin.tenant_id==int(flow['tenantId'])))
        assert abs(row.lat-LAT) < 1e-10 and abs(row.lng-LNG) < 1e-10
        columns = {column['name']:str(column['type']).upper() for column in inspect(db.bind).get_columns('t_internship_checkin')}
        assert columns['lat']=='DOUBLE' and columns['lng']=='DOUBLE'


@pytest.mark.parametrize('changes,expected', [
    ({},'NORMAL'), ({'lat':LAT+0.001},'OUT_OF_RANGE'),
    ({'gpsAccuracy':20},'LOW_ACCURACY'), ({'lat':LAT+4.8/111319.9},'LOCATION_UNCERTAIN'),
    ({'coordinateSystem':'WGS84'},'LOCATION_UNCERTAIN'),
    ({'lat':None,'lng':None},'NO_LOCATION'), ({'deviceRiskFlag':'mock'},'MOCK_LOCATION'),
])
def test_normal_student_real_fence_classification_and_audit(flow, changes, expected):
    fence(flow)
    with login(flow,'STUDENT') as student:
        response = checkin(student, flow, **changes)
        assert response.status_code == 200 and response.json()['data']['result']==expected, response.text
        calendar = student.get(BASE+'/calendar', params={'batchId':flow['batchId']})
        assert calendar.status_code==200, calendar.text
    with get_sessionmaker()() as db:
        row = db.scalar(select(InternshipCheckin).where(InternshipCheckin.tenant_id==int(flow['tenantId'])))
        assert row.result==expected and row.note=='合成围栏精度验收'
        events=db.scalars(select(AuditOutbox).where(AuditOutbox.tenant_id==int(flow['tenantId']),
                         AuditOutbox.event_type=='INTERNSHIP_CHECKIN_CREATE')).all()
        assert len(events)==1


def test_student_original_and_server_watermark_download_match_recorded_hashes(flow):
    fence(flow)
    output=BytesIO()
    Image.new('RGB',(800,600),(228,238,246)).save(output,format='JPEG')
    original=output.getvalue()
    with login(flow,'STUDENT') as student:
        photo=upload(student,original,name='synthetic-checkin.jpg',mime='image/jpeg',biz='INTERNSHIP_CHECKIN_PHOTO')
        response=checkin(student,flow,photoFileId=photo['fileId'],address='合成围栏位置，非真实现场')
        assert response.status_code==200 and response.json()['data']['result']=='NORMAL', response.text
        receipt=response.json()['data']
        assert receipt['watermarkedFileId'] and receipt['watermarkedFileId']!=photo['fileId']
        raw=student.get('/api/v1/files/download/'+photo['fileId'])
        derived=student.get('/api/v1/files/download/'+receipt['watermarkedFileId'])
        assert raw.status_code==200 and raw.content==original
        assert derived.status_code==200 and derived.content!=original, derived.text if derived.status_code!=200 else ''
        assert sha256(raw.content).hexdigest()==receipt['evidenceSha256']
        assert sha256(derived.content).hexdigest()==receipt['watermarkedSha256']
        assert receipt['date'] in receipt['watermarkText'] and '合成围栏位置' in receipt['watermarkText']
        assert '28.228235,112.938877' in receipt['watermarkText']
        with Image.open(BytesIO(derived.content)) as image:assert image.size==(800,600)
    with login(flow,'INTERN_MENTOR') as mentor:
        listed=mentor.get('/api/v1/internship/checkins',params={'batchId':flow['batchId']})
        assert listed.status_code==200, listed.text
        item=next(item for item in listed.json()['data']['items'] if item['id']==receipt['id'])
        assert item['photoFileId']==photo['fileId'] and item['watermarkedFileId']==receipt['watermarkedFileId']
        assert item['photoSha256']==receipt['evidenceSha256'] and item['watermarkedSha256']==receipt['watermarkedSha256']
        for file_id, content in [(photo['fileId'], original), (receipt['watermarkedFileId'], derived.content)]:
            authorized = mentor.get('/api/v1/files/download/'+file_id)
            assert authorized.status_code==200 and authorized.content==content, authorized.text
    other, _ = teammate(flow)
    foreign = seed_flow()
    with other, login(foreign, 'STUDENT') as outsider:
        for file_id in [photo['fileId'], receipt['watermarkedFileId']]:
            assert other.get('/api/v1/files/download/'+file_id).status_code==404
            assert outsider.get('/api/v1/files/download/'+file_id).status_code==404
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, int(flow['recordId']))
        record.advisor_user_id = flow['users']['SCHOOL_ADMIN']
        db.commit()
    with login(flow,'INTERN_MENTOR') as previous_mentor:
        for file_id in [photo['fileId'], receipt['watermarkedFileId']]:
            assert previous_mentor.get('/api/v1/files/download/'+file_id).status_code==404


def test_exemption_evidence_binds_only_own_file_and_authorized_teacher_can_read(flow):
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher:
        photo=upload(student, biz='INTERNSHIP_CHECKIN_EXEMPTION')
        request={'batchId':flow['batchId'],'internshipId':flow['recordId'],'startDate':'2026-09-02','endDate':'2026-09-03',
                 'reason':'合成免签申请验证','evidenceFileId':photo['fileId']}
        other, other_context=teammate(flow)
        with other:
            denied=other.post('/api/v1/mobile/internship/context/checkin-exemptions',json={**request,**other_context})
            assert denied.status_code in {403,404}, denied.text
        created=student.post('/api/v1/mobile/internship/context/checkin-exemptions',json=request)
        assert created.status_code==200 and created.json()['code']==0, created.text
        for client in [student,teacher]:
            assert client.get('/api/v1/files/download/'+photo['fileId']).status_code==200


def test_modified_original_cannot_create_a_watermark_or_commit_checkin(flow):
    fence(flow)
    output=BytesIO()
    Image.new('RGB',(800,600),(228,238,246)).save(output,format='JPEG')
    original=output.getvalue()
    replacement=BytesIO()
    Image.new('RGB',(800,600),(246,218,198)).save(replacement,format='JPEG')
    with login(flow,'STUDENT') as student:
        photo=upload(student,original,name='integrity-checkin.jpg',mime='image/jpeg',biz='INTERNSHIP_CHECKIN_PHOTO')
        with get_sessionmaker()() as db:
            row=db.get(FileObject,int(photo['fileId']))
            path=get_backend().fetch_local(row.file_key).resolve()
            assert path.is_relative_to(Path(settings.FILE_STORAGE_DIR).resolve())
        try:
            path.write_bytes(replacement.getvalue())
            damaged=student.get('/api/v1/files/download/'+photo['fileId'])
            assert damaged.status_code==409 and damaged.json()['bizCode']=='FILE_INTEGRITY_ERROR', damaged.text
            result=checkin(student,flow,photoFileId=photo['fileId'],address='合成原图完整性检查')
            assert result.status_code==409 and result.json()['bizCode']=='FILE_INTEGRITY_ERROR', result.text
            with get_sessionmaker()() as db:
                assert not db.scalars(select(InternshipCheckin).where(InternshipCheckin.tenant_id==int(flow['tenantId']))).all()
                assert not db.scalars(select(FileBinding).where(FileBinding.tenant_id==int(flow['tenantId']))).all()
                files=db.scalars(select(FileObject).where(FileObject.tenant_id==int(flow['tenantId']))).all()
                assert len(files)==1 and files[0].biz_type=='TEMP_PRIVATE'
                assert not db.scalars(select(AuditOutbox).where(AuditOutbox.tenant_id==int(flow['tenantId']),
                    AuditOutbox.event_type=='INTERNSHIP_CHECKIN_CREATE')).all()
        finally:
            path.write_bytes(original)
