"""真实账号、隔离学校和 MySQL 公告链；附件扫描引擎在测试中替身化。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.models import (College, InternshipAuditTrail, InternshipEmergencyNotice,
                        InternshipEmergencyNoticeTeacherReceipt,
                        StudentAccountLink, StudentProfile)
from app.models.internship import InternshipEmergencyNoticeReceipt
from app.models.file import FileBinding, FileJob, FileObject
from app.services import file_scan_service as scan
from app.services.clamav_client import ClamAVScanResult
from test_yiyang_write_flows_mysql import flow, login, seed_flow
from test_student_weekly_detail_mysql import teammate

STAFF = '/api/v1/teacher-mobile/internship/emergency-notices'
MOBILE = '/api/v1/mobile/internship/emergency-notices'
PORTAL = '/api/v1/portal/internship/context/notices'


def publish(client, data, **extra):
    response = client.post(STAFF, json={'batchId': data['batchId'], 'title': '合成安全通知',
                                      'content': '请认真阅读合成测试公告并明确确认知悉。', 'urgency': 'IMPORTANT', **extra})
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    return response.json()['data']


def pending(client, data, surface=MOBILE):
    response = client.get(surface+'/pending', params={'batchId': data['batchId']})
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    return response.json()['data']


class SyntheticCleanScanner:
    def version(self): return 'synthetic-test-engine/1'
    def scan_path(self, path):
        assert path.is_file()
        return ClamAVScanResult('CLEAN', None, 'synthetic-test-result')


def ready_pdf(client, data, monkeypatch):
    """Target only this test's job; run the real fingerprint/promote/audit pipeline."""
    monkeypatch.setenv('CLAMAV_ENABLED', 'true')
    monkeypatch.setenv('FILE_SCAN_REQUIRED', 'true')
    buf = BytesIO(); Image.new('RGB', (160, 100), (235, 242, 250)).save(buf, format='PDF')
    content = buf.getvalue()
    response = client.post('/api/v1/files', files={'file': ('notice.pdf', content, 'application/pdf')})
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    meta = response.json()['data']
    assert not meta['readyForBusiness'] and meta['scanStatus'] == 'PENDING'
    assert client.get('/api/v1/files/download/'+meta['fileId']).status_code == 404
    with get_sessionmaker()() as db:
        row = db.get(FileObject, int(meta['fileId']))
        job = db.scalar(select(FileJob).where(FileJob.file_id == row.id, FileJob.tenant_id == int(data['tenantId'])).with_for_update())
        job.status, job.attempts, job.locked_at, job.locked_by = 'RUNNING', 1, datetime.utcnow(), uuid4().hex
        claim = scan.Claim(job.id, job.tenant_id, row.id, 1, job.locked_by, row.file_key, row.sha256, row.size_bytes, job.locked_at)
        db.commit()
    result, version = scan.scan_claim(claim, SyntheticCleanScanner())
    finished = scan.finish_claim(claim, result=result, engine_version=version)
    assert finished['scanStatus'] == 'CLEAN'
    assert client.get('/api/v1/files/'+meta['fileId']).json()['data']['readyForBusiness']
    return meta['fileId'], content


def test_normal_student_list_popup_relogin_and_explicit_receipt(flow):
    with login(flow) as school:
        row = publish(school, flow)
    with login(flow, 'STUDENT') as student:
        for path in (PORTAL, MOBILE):
            read = student.get(path, params={'batchId': flow['batchId']})
            assert read.status_code == 200 and read.json()['code'] == 0, read.text
            assert row['id'] in [item['id'] for item in read.json()['data']]
        assert pending(student, flow)[0]['id'] == row['id']
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipEmergencyNoticeReceipt).where(
            InternshipEmergencyNoticeReceipt.notice_id == int(row['id']))) == 0
    with login(flow, 'STUDENT') as student:
        assert pending(student, flow)[0]['id'] == row['id']
        url = MOBILE+'/'+row['id']+'/ack'
        first = student.post(url, params={'batchId': flow['batchId']})
        second = student.post(url, params={'batchId': flow['batchId']})
        assert first.json()['code'] == second.json()['code'] == 0, first.text+second.text
        assert first.json()['data']['alreadyAcknowledged'] is False
        assert second.json()['data']['alreadyAcknowledged'] is True
        assert first.json()['data']['receiptId'] == second.json()['data']['receiptId']
        assert pending(student, flow) == []
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == int(flow['tenantId']),
            InternshipAuditTrail.action == 'EMERGENCY_NOTICE_ACKNOWLEDGED')) == 1


def test_normal_mentor_reads_and_acknowledges_but_cannot_publish_or_withdraw(flow):
    with login(flow) as school, login(flow, 'INTERN_MENTOR') as teacher:
        row = publish(school, flow)
        assert pending(teacher, flow, STAFF)[0]['id'] == row['id']
        assert teacher.get(STAFF, params={'batchId': flow['batchId']}).json()['code'] == 0
        assert teacher.post(STAFF, json={'batchId': flow['batchId'], 'title': '越权发布', 'content': '老师不能冒用校级管理员'}).status_code == 403
        assert teacher.post(STAFF+'/'+row['id']+'/withdraw', json={'reason': '越权撤回'}).status_code == 403
        assert teacher.get(STAFF+'/pending', params={'batchId': flow['batches'][1]['id']}).status_code == 403
        ack = teacher.post(STAFF+'/'+row['id']+'/ack', params={'batchId': flow['batchId']})
        assert ack.json()['code'] == 0, ack.text
        assert pending(teacher, flow, STAFF) == []


@pytest.mark.parametrize('role,surface,receipt_model', [
    ('STUDENT', MOBILE, InternshipEmergencyNoticeReceipt),
    ('INTERN_MENTOR', STAFF, InternshipEmergencyNoticeTeacherReceipt),
])
def test_simultaneous_acknowledgement_has_one_receipt(flow, role, surface, receipt_model):
    with login(flow) as school, login(flow, role) as one, login(flow, role) as two:
        row = publish(school, flow)
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = [future.result(timeout=20) for future in [
                pool.submit(c.post, surface+'/'+row['id']+'/ack', params={'batchId': flow['batchId']}) for c in (one, two)]]
        assert all(r.status_code == 200 and r.json()['code'] == 0 for r in replies), [r.text for r in replies]
        assert sorted(r.json()['data']['alreadyAcknowledged'] for r in replies) == [False, True]
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(receipt_model).where(receipt_model.notice_id == int(row['id']))) == 1


@pytest.mark.parametrize('when', ['future', 'expired'])
@pytest.mark.parametrize('role,surface', [('STUDENT', MOBILE), ('INTERN_MENTOR', STAFF)])
def test_inactive_notice_cannot_be_acknowledged_by_old_url(flow, when, role, surface):
    dates = {'validFrom': (datetime.utcnow()+timedelta(days=1)).isoformat()+'Z'} if when == 'future' else {
        'validUntil': (datetime.utcnow()-timedelta(days=1)).isoformat()+'Z'}
    with login(flow) as school, login(flow, role) as receiver:
        row = publish(school, flow, **dates)
        assert pending(receiver, flow, surface) == []
        ack = receiver.post(surface+'/'+row['id']+'/ack', params={'batchId': flow['batchId']})
        assert ack.status_code == 404 and not ack.json().get('data'), ack.text


def test_revoked_binding_wrong_batch_staff_and_foreign_school_are_denied(flow):
    foreign = seed_flow()
    with login(flow) as school, login(flow, 'STUDENT') as student, login(foreign, 'STUDENT') as outsider:
        row = publish(school, flow)
        assert student.get(MOBILE+'/pending', params={'batchId': flow['batches'][1]['id']}).json()['code'] != 0
        assert outsider.post(MOBILE+'/'+row['id']+'/ack', params={'batchId': foreign['batchId']}).status_code == 404
        assert school.get(PORTAL, params={'batchId': flow['batchId']}).status_code == 403
        with get_sessionmaker()() as db:
            link = db.scalar(select(StudentAccountLink).where(StudentAccountLink.user_id == flow['users']['STUDENT']))
            link.link_status = 'REVOKED'; db.commit()
        for url in (PORTAL, MOBILE+'/pending'):
            assert student.get(url, params={'batchId': flow['batchId']}).status_code == 403


def test_notice_attachment_current_authority_membership_and_withdrawal(flow, monkeypatch):
    foreign = seed_flow()
    with login(flow) as school, login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher, login(foreign) as outsider:
        fid, content = ready_pdf(school, flow, monkeypatch)
        row = publish(school, flow, attachmentFileIds=[fid])
        for client in (school, student, teacher):
            assert client.get('/api/v1/files/'+fid).status_code == 200
            downloaded = client.get('/api/v1/files/download/'+fid)
            assert downloaded.status_code == 200 and downloaded.content == content, downloaded.text
        assert outsider.get('/api/v1/files/'+fid).status_code == 404
        with get_sessionmaker()() as db:
            binding = db.scalar(select(FileBinding).where(FileBinding.file_id == int(fid)))
            binding.status = 'INACTIVE'; db.commit()
        assert student.get('/api/v1/files/download/'+fid).status_code == 404
        with get_sessionmaker()() as db:
            db.get(FileBinding, binding.id).status = 'ACTIVE'; db.commit()
        assert student.get('/api/v1/files/download/'+fid).status_code == 200
        assert school.post(STAFF+'/'+row['id']+'/withdraw', json={'reason': '合成撤回验证'}).json()['code'] == 0
        for client in (school, student, teacher):
            assert client.get('/api/v1/files/'+fid).status_code == 404
            assert client.get('/api/v1/files/download/'+fid).status_code == 404
        assert student.post(MOBILE+'/'+row['id']+'/ack', params={'batchId': flow['batchId']}).status_code == 404


def test_notice_publish_cannot_take_other_uploaders_private_or_pending_attachment(flow, monkeypatch):
    with login(flow) as school, login(flow, 'STUDENT') as student:
        fid, _ = ready_pdf(student, flow, monkeypatch)
        denied = school.post(STAFF, json={'batchId': flow['batchId'], 'title': '不得取用私有附件',
                                        'content': '附件来自另一个账号，不能发布。', 'attachmentFileIds': [fid]})
        assert denied.status_code == 404 and not denied.json().get('data'), denied.text
        buf = BytesIO(); Image.new('RGB', (160, 100)).save(buf, format='PDF')
        uploaded = school.post('/api/v1/files', files={'file': ('pending.pdf', buf.getvalue(), 'application/pdf')}).json()['data']
        blocked = school.post(STAFF, json={'batchId': flow['batchId'], 'title': '扫描未完成',
                                         'content': '待扫描附件不能成为正式公告。', 'attachmentFileIds': [uploaded['fileId']]})
        assert blocked.status_code == 404 and not blocked.json().get('data'), blocked.text
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.tenant_id == int(flow['tenantId']))) == 0


def test_college_reception_scope_is_enforced_for_popup_ack_and_attachment(flow, monkeypatch):
    with get_sessionmaker()() as db:
        colleges = [College(tenant_id=int(flow['tenantId']), code='C'+str(i), college_name='合成学院'+str(i), status='ACTIVE') for i in (1, 2)]
        db.add_all(colleges); db.flush()
        db.get(StudentProfile, int(flow['studentId'])).college_id = colleges[0].id
        selected_id = colleges[0].id; other_id = colleges[1].id; db.commit()
    other, own_context = teammate(flow)
    with get_sessionmaker()() as db:
        from app.models import InternshipRecord
        record = db.get(InternshipRecord, int(own_context['internshipId']))
        record.batch_id = int(flow['batchId'])
        other_student_id = record.student_id
        db.get(StudentProfile, other_student_id).college_id = other_id; db.commit()
    with other, login(flow) as school, login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher:
        fid, _ = ready_pdf(school, flow, monkeypatch)
        row = publish(school, flow, audienceScope='COLLEGE', recipientCollegeIds=[selected_id], attachmentFileIds=[fid])
        assert pending(student, flow)[0]['id'] == row['id']
        assert pending(teacher, flow, STAFF)[0]['id'] == row['id']
        assert pending(other, flow) == []
        assert other.post(MOBILE+'/'+row['id']+'/ack', params={'batchId': flow['batchId']}).status_code == 403
        assert other.get('/api/v1/files/download/'+fid).status_code == 404
        assert student.get('/api/v1/files/download/'+fid).status_code == 200


@pytest.mark.parametrize('change', ['expired', 'removed_from_notice', 'mismatched_business'])
def test_current_notice_authority_blocks_old_attachment_links(flow, monkeypatch, change):
    with login(flow) as school, login(flow, 'STUDENT') as student:
        fid, _ = ready_pdf(school, flow, monkeypatch)
        row = publish(school, flow, attachmentFileIds=[fid])
        assert student.get('/api/v1/files/download/'+fid).status_code == 200
        with get_sessionmaker()() as db:
            notice = db.get(InternshipEmergencyNotice, int(row['id']))
            if change == 'expired': notice.valid_until = datetime.utcnow()-timedelta(days=1)
            elif change == 'removed_from_notice': notice.attachment_file_ids_json = []
            else: db.get(FileObject, int(fid)).biz_id = '999999999'
            db.commit()
        for client in (school, student):
            assert client.get('/api/v1/files/'+fid).status_code == 404
            assert client.get('/api/v1/files/download/'+fid).status_code == 404
