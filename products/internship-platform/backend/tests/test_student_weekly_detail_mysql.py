"""本人周报详情：真实身份、历史附件、版本评分和扫描拒绝。"""
from uuid import uuid4
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.main import app
from app.models import InternshipBatch, InternshipRecord, Role, StudentAccountLink, User, UserRole, WeeklyReport
from test_yiyang_write_flows_mysql import flow, context, login, png_bytes, seed_flow, upload, PASSWORD

MOBILE = '/api/v1/mobile/internship'
PORTAL = '/api/v1/portal/internship'
STAFF = '/api/v1/internship'


def body(data, **extra):
    return {**context(data), 'expectedVersion': 0, 'weekNo': 1,
            'workContent': '岗位工作与安全操作记录。' * 5, 'harvestContent': '岗位学习成果。' * 5, **extra}


@pytest.mark.parametrize('surface', [MOBILE, PORTAL])
def test_own_detail_reads_two_immutable_versions_attachments_and_rating(flow, surface):
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher:
        first = upload(student, biz='INTERNSHIP_REPORT')
        payload = body(flow, attachmentFileIds=[first['fileId']])
        created = student.post(MOBILE+'/context/weekly-reports', json=payload)
        assert created.status_code == 200 and created.json()['code'] == 0, created.text
        row = created.json()['data']
        review_url = STAFF+'/reports/'+row['id']+'/review'
        returned = teacher.post(review_url, json={'batchId': flow['batchId'], 'expectedVersion': row['version'],
                                                 'action': 'RETURN', 'comment': '请补充岗位工作成果与图片说明'})
        assert returned.json()['code'] == 0, returned.text
        selected = student.get(surface+'/context/weekly-reports/'+row['id'], params=context(flow))
        assert selected.json()['code'] == 0, selected.text
        detail = selected.json()['data']
        second = upload(student, name='corrected.png', biz='INTERNSHIP_REPORT')
        payload.update(expectedVersion=detail['version'], attachmentFileIds=[second['fileId']], workContent=payload['workContent']+'已按指导意见完善工作成果。')
        updated = student.post(MOBILE+'/context/weekly-reports', json=payload)
        assert updated.json()['code'] == 0, updated.text
        current = updated.json()['data']
        approved = teacher.post(review_url, json={'batchId': flow['batchId'], 'expectedVersion': current['version'],
                                                'action': 'APPROVE', 'comment': '修改后符合岗位要求', 'ratingLevel': 4})
        assert approved.json()['code'] == 0, approved.text
        final = student.get(surface+'/context/weekly-reports/'+row['id'], params=context(flow)).json()['data']
        assert final['status'] == 'APPROVED' and final['review']['ratingLevel'] == 4
        assert final['batchId'] == flow['batchId'] and final['internshipId'] == flow['recordId']
        versions = final['immutableVersions']
        assert [version['versionNo'] for version in versions] == [2, 1]
        assert versions[0]['content']['workContent'] == payload['workContent']
        assert versions[1]['content']['workContent'] != payload['workContent']
        assert versions[0]['review']['action'] == 'APPROVE' and versions[1]['review']['action'] == 'RETURN'
        assert [version['attachments'][0]['fileId'] for version in versions] == [second['fileId'], first['fileId']]
        assert all(version['submittedAt'].endswith('Z') for version in versions)
        for file in [first, second]:
            assert student.get('/api/v1/files/download/'+file['fileId']).content == png_bytes()
            assert teacher.get('/api/v1/files/download/'+file['fileId']).content == png_bytes()


def teammate(flow):
    with get_sessionmaker()() as db:
        record = db.scalar(select(InternshipRecord).where(InternshipRecord.batch_id == int(flow['batches'][1]['id'])))
        role = db.scalar(select(Role).where(Role.tenant_id == int(flow['tenantId']), Role.role_code == 'STUDENT'))
        user = User(tenant_id=int(flow['tenantId']), login_name='other_student', real_name='另一个合成学生',
                    password_hash=hash_password(PASSWORD), user_type='STUDENT', status='ACTIVE', credential_version=0, must_change_password=False)
        db.add(user); db.flush()
        db.add_all([UserRole(tenant_id=int(flow['tenantId']), user_id=user.id, role_id=role.id, status='ACTIVE'),
                    StudentAccountLink(tenant_id=int(flow['tenantId']), user_id=user.id, student_id=record.student_id,
                                       link_status='ACTIVE', source='IDENTITY_IMPORT', bound_student_no='S1', bound_login_name='other_student')])
        db.commit()
        own_context = {'batchId': str(record.batch_id), 'internshipId': str(record.id)}
    client = TestClient(app)
    response = client.post('/api/v1/auth/browser-login', json={'tenantCode': flow['tenantCode'], 'loginName': 'other_student',
                           'password': PASSWORD, 'clientType': 'STUDENT_PC'}, headers={'X-Browser-Session-Id': 'weekly-'+uuid4().hex})
    assert response.status_code == 200, response.text
    client.headers.update({'Authorization': 'Bearer '+response.json()['data']['accessToken']})
    return client, own_context


@pytest.mark.parametrize('surface', [MOBILE, PORTAL])
def test_detail_denies_other_student_school_staff_wrong_batch_and_foreign_school(flow, surface):
    foreign = seed_flow()
    with login(flow, 'STUDENT') as student, login(flow) as staff, login(foreign, 'STUDENT') as outsider:
        created = student.post(MOBILE+'/context/weekly-reports', json=body(flow))
        row = created.json()['data']
        url = surface+'/context/weekly-reports/'+row['id']
        other, other_context = teammate(flow)
        with other:
            response = other.get(url, params=other_context)
            assert response.status_code == 404 and not response.json().get('data'), response.text
            assert other.get(url, params=context(flow)).json()['code'] != 0
        response = outsider.get(url, params=context(foreign))
        assert response.status_code == 404 and not response.json().get('data'), response.text
        assert staff.get(url, params=context(flow)).json()['code'] != 0
        assert student.get(url, params={**context(flow), 'batchId': flow['batches'][1]['id']}).json()['code'] != 0
        assert student.get(url).status_code == 422


def test_old_session_loses_weekly_detail_after_account_binding_revoked(flow):
    with login(flow, 'STUDENT') as student:
        row = student.post(MOBILE+'/context/weekly-reports', json=body(flow)).json()['data']
        with get_sessionmaker()() as db:
            link = db.scalar(select(StudentAccountLink).where(StudentAccountLink.user_id == flow['users']['STUDENT']))
            link.link_status = 'REVOKED'; db.commit()
        denied = student.get(MOBILE+'/context/weekly-reports/'+row['id'], params=context(flow))
        assert denied.status_code == 403 and not denied.json().get('data'), denied.text


def test_mobile_weekly_plan_minimum_and_scan_are_real_submission_gates(flow, monkeypatch):
    with get_sessionmaker()() as db:
        batch = db.get(InternshipBatch, int(flow['batchId']))
        batch.rules_config = {'weeklyReport': {'minWordCount': 120}}
        db.commit()
    monkeypatch.setenv('FILE_SCAN_REQUIRED', 'true')
    with login(flow, 'STUDENT') as student:
        short = student.post(MOBILE+'/context/weekly-reports', json=body(flow, workContent='工作', harvestContent='学习'))
        assert short.json()['code'] != 0
        pdf = BytesIO()
        Image.new('RGB', (160, 100), (235, 242, 250)).save(pdf, format='PDF')
        accepted = student.post('/api/v1/files', files={'file': ('report.pdf', pdf.getvalue(), 'application/pdf')})
        pending = accepted.json()['data']
        assert pending['readyForBusiness'] is False
        payload = body(flow, workContent='岗位工作。'*30, attachmentFileIds=[pending['fileId']])
        denied = student.post(MOBILE+'/context/weekly-reports', json=payload)
        assert denied.json()['code'] != 0 and not denied.json().get('data')
        assert student.get('/api/v1/files/download/'+pending['fileId']).status_code == 404
    with get_sessionmaker()() as db:
        assert db.scalar(select(WeeklyReport).where(WeeklyReport.internship_id == int(flow['recordId']))) is None
