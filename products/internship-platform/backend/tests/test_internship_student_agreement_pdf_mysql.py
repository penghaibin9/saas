"""Non-cleaning normal-role checks for the student's exact agreement print snapshot."""
import base64
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipAgreementTemplate, InternshipAuditTrail, InternshipRecord
from test_internship_change_resubmit_mysql import story, data
from test_yiyang_plan_export_options_mysql import login, seed_workspace

PC = '/api/v1/portal/internship/context/agreements'
SCHOOL = '/api/v1/internship/agreements'
BODY = '合成协议正文，仅供本地联调，不构成合同、承诺或真实签署。\n企业：{{companyName}}\n岗位：{{positionName}}\n<script>合成危险文本仍作为正文显示</script>'


def test_student_pdf_uses_read_version_body_owner_context_and_persistent_audit(story):
    with get_sessionmaker()() as db:
        template = InternshipAgreementTemplate(tenant_id=int(story['tenantId']), name='非约束合成协议',
            template_version='合成联调版', category='TRIPARTITE', body=BODY, status='ENABLED',
            scope_batch_ids=[int(story['ctx']['batchId'])])
        db.add(template); db.commit(); template_id = str(template.id)
        other_record = db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id == int(story['tenantId']),
            InternshipRecord.batch_id == int(story['batches'][1]['id'])))
        other_record_id = str(other_record.id)
    with login(story) as school:
        own = data(school.post(SCHOOL, json={'internshipId': str(story['recordId']), 'templateId': template_id}))
        issued = data(school.post(SCHOOL+'/'+own['id']+'/issue', json={'expectedVersion': own['version']}))
        other = data(school.post(SCHOOL, json={'internshipId': other_record_id}))
    foreign = seed_workspace(1)
    with get_sessionmaker()() as db:
        foreign_id = str(db.scalar(select(InternshipRecord.id).where(InternshipRecord.tenant_id == int(foreign['tenantId']))))
    with login(foreign) as school:
        outside = data(school.post(SCHOOL, json={'internshipId': foreign_id}))
    path = PC+'/'+own['id']+'/pdf'
    payload = {**story['ctx'], 'expectedVersion': issued['version']}
    with login(story, 'STUDENT') as student, login(story, 'INTERN_MENTOR') as teacher:
        detail = data(student.get(PC+'/'+own['id']))
        assert detail['renderedBody'].startswith('合成协议正文')
        assert '<script>' in detail['renderedBody'] and '{{companyName}}' not in detail['renderedBody']
        printed = data(student.post(path, json=payload))
        content = base64.b64decode(printed['contentBase64'])
        assert printed['mediaType'] == 'application/pdf' and content.startswith(b'%PDF-')
        text = ''.join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
        assert '不构成合同' in text and detail['enterpriseName'] in text and '<script>' in text
        assert (printed['agreementId'],printed['agreementVersion'],printed['batchId'],printed['internshipId']) == (own['id'],issued['version'],story['ctx']['batchId'],story['ctx']['internshipId'])
        assert printed['bodySha256'] == sha256(detail['renderedBody'].strip().encode()).hexdigest()
        assert teacher.post(path, json=payload).status_code == 403
        assert student.post(PC+'/'+other['id']+'/pdf', json=payload).status_code == 403
        assert student.post(PC+'/'+outside['id']+'/pdf', json=payload).status_code == 404
        assert student.post(path, json={**payload,'internshipId':other_record_id}).status_code == 409
        missing = student.post(path,json=story['ctx'])
        assert missing.status_code == 400 and missing.json()['bizCode'] == 'VALIDATION_ERROR'
        confirmed = data(student.post(PC+'/'+own['id']+'/confirm',json={**payload,'action':'CONFIRM'}))
        assert confirmed['status'] == 'PENDING_ENTERPRISE'
        stale = student.post(path,json=payload)
        assert stale.status_code == 400 and stale.json()['bizCode'] == 'DATA_CONFLICT'
        fresh = data(student.post(path,json={**payload,'expectedVersion':confirmed['version']}))
        assert fresh['agreementVersion'] == confirmed['version']
    with get_sessionmaker()() as db:
        rows = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(story['tenantId']),
            InternshipAuditTrail.target_type == 'AGREEMENT',InternshipAuditTrail.target_id == int(own['id']),
            InternshipAuditTrail.action == 'DOWNLOAD_PDF').order_by(InternshipAuditTrail.id)).all()
        assert [row.detail_json['version'] for row in rows] == [issued['version'],confirmed['version']]
        assert all(row.detail_json['bodySha256'] == printed['bodySha256'] for row in rows)
        assert all(row.detail_json['internshipId'] == story['ctx']['internshipId'] for row in rows)
