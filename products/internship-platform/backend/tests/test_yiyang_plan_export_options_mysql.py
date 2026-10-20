"""Real-MySQL plan-picker tests use a unique synthetic school; no shared fixtures deleted."""
import os
from uuid import uuid4
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from app.config import settings
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.main import app
from app.models import Tenant, Role, User, UserRole, StudentProfile, InternshipRecord, InternshipBatch, InternshipBatchPlan

PASSWORD = 'Bulk-Tests-Only-2026!'
ROOT = '/api/v1/internship/plans'

def seed_workspace(count=23):
    assert settings.APP_ENV == 'test' and make_url(settings.DATABASE_URL).get_backend_name() == 'mysql'
    assert 'test' in (make_url(settings.DATABASE_URL).database or '')
    code = 'BULK-' + uuid4().hex[:12]
    with get_sessionmaker()() as db:
        tenant = Tenant(tenant_code=code, school_name='批量导出验收学校', deploy_mode='SAAS', db_mode='SHARED', status='ACTIVE')
        db.add(tenant); db.flush()
        users = {}
        for role_code, user_type in [('SCHOOL_ADMIN','SCHOOL_ADMIN'),('INTERN_MENTOR','TEACHER'),('STUDENT','STUDENT')]:
            role = Role(tenant_id=tenant.id, role_code=role_code, role_name=role_code, role_type='SYSTEM', status='ACTIVE')
            user = User(tenant_id=tenant.id, login_name=role_code.lower(), real_name='批量验收'+role_code,
                        password_hash=hash_password(PASSWORD), user_type=user_type, status='ACTIVE', credential_version=0, must_change_password=False)
            db.add_all([role,user]); db.flush()
            db.add(UserRole(tenant_id=tenant.id,user_id=user.id,role_id=role.id,status='ACTIVE')); users[role_code] = user.id
        batches = []
        for index in range(count):
            batch = InternshipBatch(tenant_id=tenant.id,batch_name=f'批量验收批次{index:02}',batch_no=f'{code}-{index}',status='RUNNING',
                start_date=datetime(2026,9,1),end_date=datetime(2026,9,30),rules_version=1)
            student = StudentProfile(tenant_id=tenant.id,student_no=f'S{index}',real_name='合成验收学生',current_stage='ENROLLED',student_status='NORMAL',status='ACTIVE')
            db.add_all([batch,student]); db.flush()
            db.add(InternshipRecord(tenant_id=tenant.id,student_id=student.id,batch_id=batch.id,status='READY',
                advisor_user_id=users['INTERN_MENTOR'] if index == 0 else users['SCHOOL_ADMIN'],advisor_name='批量验收教师'))
            plan = InternshipBatchPlan(tenant_id=tenant.id,batch_id=batch.id,title=f'岗位实习计划{index:02}',
                plan_no=f'00000000000000{index:04}',major_name='软件技术',education_level='高职专科',subsidy_standard='按学校标准',
                content='完成安全教育、真实岗位实践、指导交流、过程报告以及实习总结。',internship_type='POST',
                target_audience='2024级学生',objectives='完成岗位实习培养目标',plan_requirements='遵守实习安全要求',
                assessment_content='按过程与校企评价考核',responsible_name='验收负责人',
                tasks_json=[{'name':'岗位总结','requirement':'提交真实岗位实习总结','deadline':'2026-09-30'}],
                basic_snapshot_json={'batchName':batch.batch_name,'startDate':'2026-09-01','endDate':'2026-09-30'},
                rules_snapshot_json={'requiredCheckinDays':0,'weeklyRequiredCount':0,'monthlyRequiredCount':1,'summaryRequiredCount':1},
                status='PUBLISHED',version=2,published_at=datetime(2026,9,1))
            db.add(plan); db.flush(); batches.append({'id':str(batch.id),'planId':str(plan.id),'planNo':plan.plan_no,'title':plan.title})
        db.commit()
        return {'tenantCode':code,'tenantId':str(tenant.id),'users':users,'batches':batches}


def login(workspace, role='SCHOOL_ADMIN'):
    client = TestClient(app)
    response = client.post('/api/v1/auth/browser-login',json={'tenantCode':workspace['tenantCode'],
        'loginName':role.lower(),'password':PASSWORD,'clientType':'STUDENT_PC' if role == 'STUDENT' else 'PC'},
        headers={'X-Browser-Session-Id':'bulk-'+uuid4().hex})
    assert response.status_code == 200, response.text
    client.headers.update({'Authorization':'Bearer '+response.json()['data']['accessToken']})
    return client


@pytest.fixture(scope='module')
def workspace():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('requires explicit isolated MySQL test opt-in')
    return seed_workspace()


def test_options_are_paginated_searchable_and_only_current_school(workspace):
    with login(workspace) as client:
        first = client.get(ROOT+'/export-options',params={'page':1,'pageSize':20}).json()['data']
        second = client.get(ROOT+'/export-options',params={'page':2,'pageSize':20}).json()['data']
        assert len(first['items']) == 20 and first['hasMore'] is True
        assert len(second['items']) == 3 and second['hasMore'] is False
        assert {x['id'] for x in first['items']+second['items']} == {x['id'] for x in workspace['batches']}
        needle = workspace['batches'][0]['planNo']
        searched = client.get(ROOT+'/export-options',params={'keyword':needle}).json()['data']
        assert len(searched['items']) == 1 and searched['items'][0]['planNo'] == needle
        assert not client.get(ROOT+'/export-options',params={'keyword':'%'}).json()['data']['items']


def test_scoped_teacher_picker_matches_actual_export_scope(workspace):
    with login(workspace, 'INTERN_MENTOR') as client:
        response = client.get(ROOT+'/export-options',params={'pageSize':50})
        assert response.status_code == 200, response.text
        items = response.json()['data']['items']
        assert [item['id'] for item in items] == [workspace['batches'][0]['id']]
        denied = client.post(ROOT+'/bulk-export.xlsx',json={'batchIds':[workspace['batches'][1]['id']]})
        assert denied.status_code == 403 and 'contentBase64' not in denied.text


def test_student_cannot_use_picker(workspace):
    with login(workspace, 'STUDENT') as client:
        response = client.get(ROOT+'/export-options')
        assert response.status_code == 403, response.text


def test_other_school_plan_not_exposed_or_exported(workspace):
    other = seed_workspace(1)
    with login(workspace) as client:
        foreign = other['batches'][0]
        response = client.post(ROOT+'/bulk-export.pdf',json={'batchIds':[foreign['id']]})
        assert response.json()['code'] != 0 and 'contentBase64' not in response.text
        listed = client.get(ROOT+'/export-options',params={'pageSize':50}).json()['data']['items']
        assert foreign['id'] not in {x['id'] for x in listed}


@pytest.mark.parametrize('params',[{'page':0},{'pageSize':51},{'keyword':'x'*101}])
def test_invalid_picker_parameters_rejected(workspace, params):
    with login(workspace) as client:
        assert client.get(ROOT+'/export-options',params=params).status_code == 422


def test_picker_selection_feeds_both_real_document_exporters(workspace):
    import base64
    with login(workspace) as client:
        ids = [x['id'] for x in client.get(ROOT+'/export-options',params={'pageSize':2}).json()['data']['items']]
        for suffix, signature in [('pdf',b'%PDF'),('xlsx',b'PK')]:
            result = client.post(ROOT+'/bulk-export.'+suffix,json={'batchIds':ids})
            assert result.status_code == 200 and result.json()['code'] == 0, result.text
            assert base64.b64decode(result.json()['data']['contentBase64']).startswith(signature)


@pytest.mark.parametrize('format_code',['pdf','xlsx'])
def test_export_receipt_matches_actual_file_and_actor(workspace, format_code):
    import base64
    from hashlib import sha256
    from sqlalchemy import select
    from app.models import InternshipAuditTrail
    from app.models.audit_outbox import AuditOutbox
    ids = [x['id'] for x in workspace['batches'][:2]]
    with login(workspace) as client:
        response = client.post(ROOT+'/bulk-export.'+format_code,json={'batchIds':ids})
        assert response.status_code == 200, response.text
        data = response.json()['data']
    with get_sessionmaker()() as db:
        event = db.scalar(select(AuditOutbox).where(AuditOutbox.event_id == data['auditEventId']))
        assert event is not None and str(event.tenant_id) == workspace['tenantId']
        payload = event.payload_json
        assert payload['actorUserId'] == 'db-'+str(workspace['users']['SCHOOL_ADMIN'])
        # The canonical outbox wraps the full InternshipAuditTrail detail envelope.
        detail = payload['detailJson']['detailJson']
        assert detail['batchIds'] == ids
        assert detail['fileSha256'] == sha256(base64.b64decode(data['contentBase64'])).hexdigest()
        trail = db.scalar(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(workspace['tenantId']),
                          InternshipAuditTrail.action == 'PLAN_BULK_EXPORT').order_by(InternshipAuditTrail.id.desc()))
        assert trail.detail_json['detailJson']['fileSha256'] == detail['fileSha256']


def test_audit_storage_failure_does_not_release_a_file(workspace, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from app.modules.internship.services import internship_plan_export_options as export_svc
    def unavailable():
        raise SQLAlchemyError('simulated isolated audit storage failure')
    monkeypatch.setattr(export_svc,'session',unavailable)
    with login(workspace) as client:
        response = client.post(ROOT+'/bulk-export.pdf',json={'batchIds':[workspace['batches'][0]['id']]})
        assert response.status_code == 503, response.text
        assert response.json()['bizCode'] == 'AUDIT_UNAVAILABLE'
        assert 'contentBase64' not in response.text


def test_single_selected_plan_pdf_has_no_separator_only_trailing_page(workspace):
    import base64
    from io import BytesIO
    from pypdf import PdfReader
    with login(workspace) as client:
        response=client.post(ROOT+'/bulk-export.pdf',json={'batchIds':[workspace['batches'][0]['id']]})
        assert response.status_code==200,response.text
        reader=PdfReader(BytesIO(base64.b64decode(response.json()['data']['contentBase64'])))
        assert len(reader.pages)==1
        assert '计划编号' in reader.pages[0].extract_text()
