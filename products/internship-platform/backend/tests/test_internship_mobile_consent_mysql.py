"""Normal-role mobile consent checks in a unique, non-cleaning MySQL school."""
from hashlib import sha256

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, InternshipConsent, InternshipRecord
from test_internship_change_resubmit_mysql import story, data, apply_payload
from test_yiyang_plan_export_options_mysql import login, seed_workspace

MOBILE = '/api/v1/mobile/internship/consents'
PC = '/api/v1/portal/internship/consents'
SCHOOL = '/api/v1/internship/compliance/consents'


def create(ws, *, record_id=None, version='合成正文第一版'):
    with login(ws) as school:
        return data(school.post(SCHOOL, json={
            'internshipId': str(record_id or ws['recordId']), 'consentType': 'STUDENT',
            'contentVersion': version, 'contentSnapshot': '本地合成联调知情材料，仅用于验证本人阅读与确认流程。'+version}))


def payload(row, **extra):
    return {'expectedVersion': row['version'], 'contentVersion': row['contentVersion'],
        'contentHash': row['contentHash'], 'deviceDigest': 'synthetic-device-only', **extra}


def denied(response, status=400):
    assert response.status_code == status, response.text
    assert response.json()['code'] != 0, response.text


def test_mobile_read_confirm_and_pc_reread_use_same_task_and_audit(story):
    created = create(story)
    cid = created['id']
    with login(story, 'STUDENT') as student:
        detail = data(student.get(MOBILE+'/'+cid))
        assert detail['status'] == 'PENDING' and detail['version'] == 0
        assert detail['contentHash'] == sha256(detail['contentSnapshot'].encode()).hexdigest()
        denied(student.post(MOBILE+'/'+cid+'/confirm', json=payload(detail)))
        viewed = data(student.post(MOBILE+'/'+cid+'/view'))
        assert viewed['viewedAt'] and viewed['version'] == 1
        assert viewed['viewedAt'].endswith('+00:00')
        assert data(student.post(MOBILE+'/'+cid+'/view'))['version'] == 1
        denied(student.post(MOBILE+'/'+cid+'/confirm', json=payload(detail)))
        denied(student.post(MOBILE+'/'+cid+'/confirm', json=payload(viewed, contentHash='wrong')))
        valid = data(student.post(MOBILE+'/'+cid+'/confirm', json=payload(viewed)))
        assert valid['status'] == 'VALID' and valid['version'] == 2
        assert data(student.post(MOBILE+'/'+cid+'/confirm', json=payload(viewed)))['version'] == 2
        reread = data(student.get(PC+'/'+cid))
        assert (reread['id'], reread['status'], reread['version']) == (cid, 'VALID', 2)
        assert reread['contentSnapshot'] == detail['contentSnapshot']
        assert reread['confirmedAt'].endswith('+00:00')
    with get_sessionmaker()() as db:
        row = db.get(InternshipConsent, int(cid))
        assert row.confirmed_by_user_id == 'db-'+str(story['users']['STUDENT'])
        assert row.confirmed_student_id == story['studentId']
        assert row.device_digest == sha256(b'synthetic-device-only').hexdigest()
        assert row.client_ip_digest == sha256(b'testclient').hexdigest()
        audit = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == int(story['tenantId']),
            InternshipAuditTrail.target_type == 'INTERNSHIP_CONSENT',
            InternshipAuditTrail.target_id == int(cid)).order_by(InternshipAuditTrail.id)).all()
        assert [r.action for r in audit] == ['CREATE_TASK', 'VIEW', 'CONFIRM']


def test_all_mobile_routes_deny_other_student_school_and_staff(story):
    own = create(story)
    with get_sessionmaker()() as db:
        other_record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.tenant_id == int(story['tenantId']),
            InternshipRecord.batch_id == int(story['batches'][1]['id'])))
        other_id = other_record.id
    other_student = create(story, record_id=other_id)
    foreign = seed_workspace(1)
    with get_sessionmaker()() as db:
        foreign['recordId'] = db.scalar(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == int(foreign['tenantId'])))
    other_school = create(foreign)
    with login(story, 'STUDENT') as student, login(story, 'INTERN_MENTOR') as teacher:
        for client, rows, status in [(student, [other_student, other_school], 404),
                                     (teacher, [own], 403)]:
            for row in rows:
                path = MOBILE+'/'+row['id']
                denied(client.get(path), status)
                denied(client.post(path+'/view'), status)
                denied(client.post(path+'/confirm', json=payload(row)), status)
                denied(client.post(path+'/reject', json={
                    'expectedVersion': row['version'], 'reason': '合成材料内容需要重新核实'}), status)
        denied(student.post(MOBILE+'/'+own['id']+'/reject', json={'expectedVersion': 0, 'reason': '短'}))
        rejected = data(student.post(MOBILE+'/'+own['id']+'/reject', json={
            'expectedVersion': 0, 'reason': '合成材料内容需要重新核实'}))
        assert rejected['status'] == 'REJECTED' and rejected['version'] == 1
        denied(student.post(MOBILE+'/'+own['id']+'/reject', json={
            'expectedVersion': 1, 'reason': '合成材料内容需要重新核实'}))
        assert data(student.get(PC+'/'+own['id']))['status'] == 'REJECTED'
    with get_sessionmaker()() as db:
        for row in [other_student, other_school]:
            saved = db.get(InternshipConsent, int(row['id']))
            assert saved.status == 'PENDING' and saved.version == 0 and saved.viewed_at is None


def test_pc_rejection_reason_reaches_school_and_revised_task_reaches_mobile(story):
    created = create(story)
    reason = '请学校核实合成企业安排与正文说明'
    with login(story, 'STUDENT') as student:
        viewed = data(student.post(PC+'/'+created['id']+'/view'))
        rejected = data(student.post(PC+'/'+created['id']+'/reject', json={
            'expectedVersion': viewed['version'], 'reason': reason}))
        assert rejected['status'] == 'REJECTED' and rejected['rejectionReason'] == reason
        assert data(student.get(PC+'/'+created['id']))['rejectionReason'] == reason
        assert data(student.get(MOBILE+'/'+created['id']))['rejectionReason'] == reason
    with login(story) as school:
        ledger = data(school.get('/api/v1/internship/compliance/workbench/'+story['ctx']['batchId']+'/groups/consents'))
        item = next(x for x in ledger['consents'] if x['id'] == created['id'])
        assert item['rejectionReason'] == reason
    revised = create(story, version='学校修订后的合成正文第二版')
    assert revised['id'] != created['id'] and not revised['rejectionReason']
    with login(story, 'STUDENT') as student:
        viewed = data(student.post(PC+'/'+revised['id']+'/view'))
        valid = data(student.post(PC+'/'+revised['id']+'/confirm', json=payload(viewed)))
        assert valid['status'] == 'VALID' and not valid['rejectionReason']
        assert data(student.get(MOBILE+'/'+revised['id']))['status'] == 'VALID'
        assert data(student.get(PC+'/'+created['id']))['rejectionReason'] == reason
    with get_sessionmaker()() as db:
        old = db.get(InternshipConsent, int(created['id']))
        new = db.get(InternshipConsent, int(revised['id']))
        assert old.revoke_reason == reason and old.status == 'REJECTED'
        assert new.status == 'VALID' and new.internship_id == old.internship_id
        actions = db.scalars(select(InternshipAuditTrail.action).where(
            InternshipAuditTrail.tenant_id == int(story['tenantId']),
            InternshipAuditTrail.target_type == 'INTERNSHIP_CONSENT',
            InternshipAuditTrail.target_id == int(old.id)).order_by(InternshipAuditTrail.id)).all()
        assert actions == ['CREATE_TASK', 'VIEW', 'REJECT']


def test_change_invalidates_old_consent_and_new_mobile_task_can_be_confirmed(story):
    old = create(story)
    with login(story, 'STUDENT') as student, login(story, 'INTERN_MENTOR') as teacher:
        viewed = data(student.post(MOBILE+'/'+old['id']+'/view'))
        valid = data(student.post(MOBILE+'/'+old['id']+'/confirm', json=payload(viewed)))
        change = data(student.post('/api/v1/portal/internship/context/changes', json=apply_payload(story)))
        approved = data(teacher.post('/api/v1/internship/change-requests/'+change['id']+'/review', json={
            'action': 'APPROVE', 'comment': '合成岗位调整条件已核对', 'expectedVersion': change['version'],
            'recordExpectedVersion': change['recordVersionSnapshot']}))
        assert approved['status'] == 'APPROVED'
        superseded = data(student.get(MOBILE+'/'+old['id']))
        assert superseded['status'] == 'SUPERSEDED' and superseded['version'] == valid['version']+1
        denied(student.post(MOBILE+'/'+old['id']+'/confirm', json=payload(valid)))
        denied(student.post(MOBILE+'/'+old['id']+'/confirm', json=payload(superseded)))
        new = create(story, version='合成变更后正文第二版')
        assert new['id'] != old['id']
        viewed_new = data(student.post(MOBILE+'/'+new['id']+'/view'))
        valid_new = data(student.post(MOBILE+'/'+new['id']+'/confirm', json=payload(viewed_new)))
        assert valid_new['status'] == 'VALID' and valid_new['version'] == 2
        assert data(student.get(PC+'/'+old['id']))['status'] == 'SUPERSEDED'
        assert data(student.get(PC+'/'+new['id']))['status'] == 'VALID'
