"""Real browser-login/MySQL regressions for the student result page, no auth overrides."""
from __future__ import annotations
import pytest
from app.db.session import get_sessionmaker
from app.models import StudentAccountLink, User
from sqlalchemy import select
from test_yiyang_gap09_minimum_age_mysql import admin, scenario
from test_yiyang_sp06_sp07_formal_document_mysql import own_client

PORTAL = '/api/v1/portal/internship'
READS = ('/context/weekly-reports', '/context/reports', '/context/self-eval',
         '/insurance', '/score/appeal')

@pytest.mark.parametrize('suffix', READS)
def test_bound_student_reads_result_page_without_400_or_404(scenario, suffix):
    s = scenario(years=20)
    with own_client(s) as client:
        response = client.get(PORTAL + suffix, params={'batchId':s['batchId'], 'internshipId':s['id']})
        assert response.status_code == 200, response.text
        assert response.json()['code'] == 0, response.text

@pytest.mark.parametrize('suffix', READS)
def test_result_page_never_reads_other_students_record(scenario, suffix):
    first, second = scenario(years=20), scenario(years=20)
    with own_client(first) as client:
        response = client.get(PORTAL + suffix, params={'batchId':second['batchId'], 'internshipId':second['id']})
        assert response.status_code != 404 or response.json().get('bizCode'), response.text
        assert response.json()['code'] != 0, response.text


@pytest.mark.parametrize('approve',[False,True])
def test_score_appeal_portal_student_to_school_and_back(admin,scenario,approve):
    from datetime import datetime
    from app.models import InternshipRecord, InternshipFinalScore, InternshipAuditTrail
    from test_standalone_browser_auth_mysql import TENANT_ID
    s=scenario(years=20)
    with get_sessionmaker()() as db:
        db.get(InternshipRecord,int(s['id'])).status='ASSESSING'
        score=InternshipFinalScore(tenant_id=TENANT_ID,internship_id=int(s['id']),
            student_id=int(s['studentId']),batch_id=int(s['batchId']),
            status='PUBLISHED',incomplete=False,total_score=75,is_pass=True,
            published_at=datetime.utcnow(),published_by_name='验收教师')
        db.add(score); db.commit(); score_id=score.id
    body={'batchId':s['batchId'],'internshipId':s['id'],'reason':'请核实岗位实习考核成绩依据'}
    with own_client(s) as client:
        response=client.post(PORTAL+'/score/appeal',json=body)
        assert response.status_code==200 and response.json()['code']==0,response.text
        appeal=response.json()['data']
        duplicate=client.post(PORTAL+'/score/appeal',json=body)
        assert duplicate.json()['code']!=0
        endpoint=f"/api/v1/internship/score-appeals/{appeal['id']}/"+('approve' if approve else 'reject')
        handled=admin.post(endpoint,json={'expectedVersion':appeal['version'],'reason':'经核实需要重新核算该成绩' if approve else '经核实原始成绩依据准确无误'})
        assert handled.json()['code']==0,handled.text
        latest=client.get(PORTAL+'/score/appeal',params={'batchId':s['batchId'],'internshipId':s['id']})
        assert latest.status_code==200 and latest.json()['code']==0,latest.text
        assert latest.json()['data']['id']==appeal['id']
    with get_sessionmaker()() as db:
        saved=db.get(InternshipFinalScore,score_id)
        assert saved.total_score==75
        assert saved.status==('WITHDRAWN' if approve else 'PUBLISHED')
        actions=set(db.scalars(select(InternshipAuditTrail.action).where(
            InternshipAuditTrail.tenant_id==TENANT_ID,InternshipAuditTrail.target_id==int(s['id']),
            InternshipAuditTrail.target_type=='SCORE_APPEAL')).all())
        assert 'SUBMIT' in actions
        assert ('APPROVE_WITHDRAW_SCORE' if approve else 'REJECT') in actions


def test_school_account_cannot_use_student_score_appeal_portal(admin,scenario):
    s=scenario(years=20)
    response=admin.get(PORTAL+'/score/appeal',params={'batchId':s['batchId'],'internshipId':s['id']})
    assert response.status_code==403,response.text
