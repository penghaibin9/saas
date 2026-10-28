"""Normal-role expired-policy renewal in a unique, non-cleaning MySQL school."""
from datetime import datetime, timedelta

from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, InternshipBatch, InternshipRecord
from test_internship_change_resubmit_mysql import story, data
from test_yiyang_plan_export_options_mysql import login
from test_yiyang_write_flows_mysql import upload, insurance_body

PC = '/api/v1/portal/internship/insurance'
MOBILE = '/api/v1/mobile/internship/insurance'
SCHOOL = '/api/v1/internship/insurances'


def test_expired_verified_policy_can_renew_same_record_and_preserve_review(story):
    today = datetime.utcnow().date()
    start, end = today-timedelta(days=60), today-timedelta(days=10)
    story['batchId'] = story['ctx']['batchId']
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, story['recordId'])
        batch = db.get(InternshipBatch, int(story['batchId']))
        # Initial isolated history; all subsequent policy actions use normal APIs.
        record.intern_start_date = batch.start_date = datetime.combine(start, datetime.min.time())
        record.intern_end_date = batch.end_date = datetime.combine(end, datetime.min.time())
        db.commit()
    with login(story, 'STUDENT') as student, login(story) as school:
        first = upload(student)
        body = insurance_body(story, first['fileId'])
        body.update(effectiveDate=start.isoformat(), expiryDate=(today-timedelta(days=1)).isoformat())
        pending = data(student.post(PC, json=body))
        approved = data(school.post(SCHOOL+'/'+pending['id']+'/verify', json={
            'action': 'APPROVE', 'comment': '合成历史保单核验', 'expectedVersion': pending['version']}))
        read = data(student.get(MOBILE, params=story['ctx']))
        assert read['coverageStatus'] == 'EXPIRED' and read['canRenew'] is True
        assert data(student.get(PC, params=story['ctx']))['canRenew'] is True
        second = upload(student, name='synthetic-renewed-policy.png')
        body.update(fileId=second['fileId'], expiryDate=(today+timedelta(days=60)).isoformat(), expectedVersion=approved['version'])
        renewed = data(student.post(MOBILE, json=body))
        assert renewed['id'] == approved['id'] and renewed['status'] == 'PENDING_VERIFY'
        assert renewed['version'] == approved['version']+1 and not renewed['canRenew']
        stale = student.post(PC, json=body)
        assert stale.status_code == 400 and stale.json()['bizCode'] == 'DATA_CONFLICT'
        final = data(school.post(SCHOOL+'/'+renewed['id']+'/verify', json={
            'action': 'APPROVE', 'comment': '合成续保重新核验', 'expectedVersion': renewed['version']}))
        reread = data(student.get(PC, params=story['ctx']))
        assert reread['coverageStatus'] == 'VALID' and not reread['canRenew']
        assert (reread['id'], reread['version'], reread['fileId']) == (approved['id'], final['version'], second['fileId'])
    with get_sessionmaker()() as db:
        audits = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(story['tenantId']),
            InternshipAuditTrail.target_type == 'INSURANCE', InternshipAuditTrail.target_id == int(approved['id']))
            .order_by(InternshipAuditTrail.id)).all()
        assert [x.action for x in audits] == ['SUBMIT','VERIFY_APPROVE','RENEW','VERIFY_APPROVE']
        previous = audits[2].detail_json['previousPolicy']
        assert previous['fileId'] == first['fileId'] and previous['version'] == approved['version']
        assert previous['verifiedByName'] and previous['expiryDate'] == (today-timedelta(days=1)).isoformat()
