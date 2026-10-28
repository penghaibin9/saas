"""Explicit student plan context; new synthetic schools only, never reset existing data."""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from app.config import settings
from app.db.session import get_engine, get_sessionmaker
from app.main import app
from app.models import InternshipRecord, InternshipBatchPlan, InternshipPlanAssignment, InternshipPlanAck, InternshipPlanTaskProgress
from test_yiyang_write_flows_mysql import seed_flow
from test_yiyang_plan_export_options_mysql import PASSWORD

BASE = '/api/v1/mobile/internship/context'

@pytest.fixture(scope='module')
def workspace():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('requires explicit isolated MySQL opt-in')
    url = make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == 'test'
    assert (url.get_backend_name(), url.host, url.port, url.database) == ('mysql', '127.0.0.1', 3318, 'internship_pr275_test_20261003')
    with get_engine().connect() as connection:
        assert connection.scalar(text('select database()')) == url.database
    ws = seed_flow()
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, int(ws['recordId']))
        ws['otherRecordId'] = str(db.scalar(select(InternshipRecord.id).where(InternshipRecord.tenant_id == int(ws['tenantId']), InternshipRecord.id != record.id)))
        second = InternshipRecord(tenant_id=int(ws['tenantId']), student_id=record.student_id, batch_id=int(ws['batches'][1]['id']), status='READY')
        db.add(second); db.flush(); ws['secondRecordId'] = str(second.id)
        plan = db.get(InternshipBatchPlan, int(ws['batches'][1]['planId']))
        plan.tasks_json = [{'sortOrder':1,'name':'合成跨批次任务','requirement':'记录完成过程'}]
        db.add(InternshipPlanAssignment(tenant_id=int(ws['tenantId']), internship_id=record.id, student_id=record.student_id, plan_id=plan.id, plan_batch_id=plan.batch_id, assignment_source='MANUAL', is_primary=False, status='ACTIVE'))
        db.add(InternshipPlanAck(tenant_id=int(ws['tenantId']), internship_id=record.id, student_id=record.student_id, plan_id=plan.id, status='PENDING',version=0))
        db.commit(); ws['planId'] = str(plan.id)
    yield ws
    with get_engine().connect() as connection:
        assert connection.scalar(text('select database()')) == url.database

def login(ws, role='STUDENT'):
    client=TestClient(app)
    result=client.post('/api/v1/auth/login',json={'tenantCode':ws['tenantCode'],'loginName':role.lower(),'password':PASSWORD,'clientType':'STUDENT_MINI' if role=='STUDENT' else 'TEACHER_MINI'})
    assert result.status_code==200 and result.json()['code']==0,result.text
    client.headers['Authorization']='Bearer '+result.json()['data']['accessToken']
    return client

def ok(response):
    assert response.status_code==200 and response.json()['code']==0,response.text
    return response.json()['data']

def context(ws):
    return {'batchId':ws['batchId'],'internshipId':ws['recordId']}

def test_multi_batch_plan_reads_require_context_and_keep_authorized_cross_batch_assignment(workspace):
    ws=workspace
    with login(ws) as student:
        for path in ['/plans','/plan','/plan/tasks']:
            result=student.get(BASE+path)
            assert result.json().get('bizCode')=='NEED_SELECT',result.text
        rows=ok(student.get(BASE+'/plans',params=context(ws)))
        assert rows['context']==context(ws)
        assert ws['planId'] in {row['planId'] for row in rows['items']}
        for path in ['/plan','/plan/tasks']:
            data=ok(student.get(BASE+path,params={**context(ws),'planId':ws['planId']}))
            assert data['context']==context(ws)
            assert data['planBatchId']==ws['batches'][1]['id'] and data['planBatchId']!=ws['batchId']
        for fields in [{'internshipId':ws['otherRecordId']},{'batchId':ws['batches'][1]['id']},{'batchId':'999999999999'},{'internshipId':'999999999999'}]:
            for path in ['/plans','/plan','/plan/tasks']:
                assert student.get(BASE+path,params={**context(ws),'planId':ws['planId'],**fields}).json()['code']!=0

def test_plan_commands_use_same_explicit_record_and_preserve_version_guards(workspace):
    ws=workspace
    with login(ws) as student, login(ws,'INTERN_MENTOR') as teacher:
        assert teacher.get(BASE+'/plans',params=context(ws)).status_code==403
        detail=ok(student.get(BASE+'/plan',params={**context(ws),'planId':ws['planId']}))
        tasks=ok(student.get(BASE+'/plan/tasks',params={**context(ws),'planId':ws['planId']}))
        body={**context(ws),'planId':ws['planId'],'expectedVersion':detail['ackVersion'],'planVersion':detail['version']}
        assert student.post(BASE+'/plan/acknowledge',json={**body,'internshipId':ws['otherRecordId']}).json()['code']!=0
        ack=ok(student.post(BASE+'/plan/acknowledge',json=body));assert ack['version']==detail['ackVersion']+1
        task_body={**context(ws),'planId':ws['planId'],'studentNote':'合成学生记录完成本项实习任务的真实过程','expectedVersion':tasks['tasks'][0]['progressVersion']}
        assert student.post(BASE+'/plan/tasks/1/submit',json={**task_body,'internshipId':ws['secondRecordId']}).json()['code']!=0
        saved=ok(student.post(BASE+'/plan/tasks/1/submit',json=task_body));assert saved['internId']==ws['recordId']
        assert student.post(BASE+'/plan/tasks/1/submit',json=task_body).json()['code']!=0
        latest=ok(student.get(BASE+'/plan/tasks',params={**context(ws),'planId':ws['planId']}))
        assert latest['tasks'][0]['progressStatus']=='SUBMITTED' and latest['tasks'][0]['progressVersion']==task_body['expectedVersion']+1
    foreign=seed_flow()
    with login(foreign) as outsider:
        for path in ['/plans','/plan','/plan/tasks']:
            assert outsider.get(BASE+path,params={**context(ws),'planId':ws['planId']}).json()['code']!=0
        assert outsider.post(BASE+'/plan/tasks/1/submit',json=task_body).json()['code']!=0
        assert outsider.post(BASE+'/plan/acknowledge',json=body).json()['code']!=0
        # Legacy calls remain valid when there is only one current record.
        assert isinstance(ok(outsider.get(BASE+'/plans'))['items'],list)
    with get_sessionmaker()() as db:
        assert not db.scalar(select(InternshipPlanTaskProgress.id).where(InternshipPlanTaskProgress.tenant_id==int(ws['tenantId']),InternshipPlanTaskProgress.internship_id==int(ws['secondRecordId'])))


def test_portal_plan_context_matches_mobile_and_rejects_wrong_record(workspace):
    from test_yiyang_plan_export_options_mysql import login as browser_login
    ws=workspace
    portal='/api/v1/portal/internship/context'
    with browser_login(ws,'STUDENT') as student, login(ws) as mobile:
        for path in ['/plans','/plan','/plan/tasks']:
            params={**context(ws),'planId':ws['planId']}
            assert ok(student.get(portal+path,params=params))==ok(mobile.get(BASE+path,params=params))
            assert student.get(portal+path).json().get('bizCode')=='NEED_SELECT'
            assert student.get(portal+path,params={**params,'internshipId':ws['otherRecordId']}).json()['code']!=0
        detail=ok(student.get(portal+'/plan',params=params))
        body={**context(ws),'planId':ws['planId'],'expectedVersion':detail['ackVersion'],'planVersion':detail['version']}
        assert student.post(portal+'/plan/acknowledge',json={**body,'internshipId':ws['otherRecordId']}).json()['code']!=0
        assert ok(student.post(portal+'/plan/acknowledge',json=body))['status']=='ACKNOWLEDGED'
