"""Normal student/mentor report handoff; only new schools in an opted-in test database."""
import os
import pytest
from sqlalchemy.engine import make_url
from app.config import settings
from test_yiyang_write_flows_mysql import seed_flow,login,context

def ok(response):
    assert response.status_code==200 and response.json()['code']==0,response.text
    return response.json()['data']

@pytest.fixture
def story():
    assert os.environ.get('GAP09_MYSQL_ACCEPTANCE')=='1'
    url=make_url(settings.DATABASE_URL)
    assert settings.APP_ENV=='test' and url.get_backend_name()=='mysql'
    assert (url.host,url.port,url.database) in {('127.0.0.1',3318,'internship_pr275_acceptance_test_20261003'),('127.0.0.1',3306,'internship_employment_test_ci')}
    if url.port==3306:
        assert os.environ.get('GITHUB_ACTIONS')=='true' or os.environ.get('RELEASE_MYSQL_ACCEPTANCE')=='1'
    return seed_flow()

@pytest.mark.parametrize('kind,period',[('DAILY','2026-10-16'),('MONTHLY','2026-10'),('SUMMARY','FINAL')])
def test_period_report_dashboard_handoff_return_resubmit_approve_same_original(story,kind,period):
    with login(story,'STUDENT') as student,login(story,'INTERN_MENTOR') as teacher:
        body={**context(story),'reportType':kind,'periodKey':period,'content':'虚构工作与学习记录，仅用于本地正常身份流程验收。'*30,'expectedVersion':0}
        original=ok(student.post('/api/v1/portal/internship/context/reports',json=body))
        def dashboard():return ok(teacher.get('/api/v1/internship/dashboard',params={'batchId':story['batchId']}))
        before=dashboard();items=[row for row in before['workItems'] if row['kind']==kind+'_REPORT']
        assert len(items)==1 and items[0]['objectId']==original['id']
        assert items[0]['route']==f"/admin/internship/process-reports/{original['id']}?batchId={story['batchId']}"
        assert before['workItemTotal']==1
        review='/api/v1/internship/process-reports/'+original['id']+'/review'
        returned=ok(teacher.post(review,json={'batchId':story['batchId'],'expectedVersion':original['version'],'action':'RETURN','comment':'请补充具体虚构成果及下一步安排'}))
        assert not dashboard()['workItems']
        revised=ok(student.post('/api/v1/portal/internship/context/reports',json={**body,'content':body['content']+'已按意见补充。','expectedVersion':returned['version']}))
        assert revised['id']==original['id'] and dashboard()['workItems'][0]['objectId']==original['id']
        ok(teacher.post(review,json={'batchId':story['batchId'],'expectedVersion':revised['version'],'action':'APPROVE','comment':'虚构成果已补充，原单核对通过','ratingLevel':4,**({'summaryScore':88} if kind=='SUMMARY' else {})}))
        after=dashboard();assert after['workItemTotal']==0 and not after['workItems']
        detail=ok(student.get('/api/v1/portal/internship/context/reports/'+original['id'],params=context(story)))
        assert detail['id']==original['id'] and detail['status']=='APPROVED' and len(detail['immutableVersions'])==2

def test_period_report_dashboard_respects_school_batch_and_review_permission(story,monkeypatch):
    from app.core import permissions
    foreign=seed_flow()
    with login(story,'STUDENT') as student,login(story,'INTERN_MENTOR') as teacher,login(foreign,'INTERN_MENTOR') as outsider:
        original=ok(student.post('/api/v1/portal/internship/context/reports',json={**context(story),'reportType':'DAILY','periodKey':'2026-10-16','content':'虚构范围核验记录。'*10,'expectedVersion':0}))
        own=ok(teacher.get('/api/v1/internship/dashboard',params={'batchId':story['batchId']}));assert own['workItems'][0]['objectId']==original['id']
        other_batch=ok(teacher.get('/api/v1/internship/dashboard',params={'batchId':story['batches'][1]['id']}));assert not other_batch['workItems']
        other_school=outsider.get('/api/v1/internship/dashboard',params={'batchId':story['batchId']});assert other_school.status_code in (400,403,404) or other_school.json()['code']!=0
        original_permission=permissions.has_permission
        monkeypatch.setattr(permissions,'has_permission',lambda user,code:False if code=='internship.report.review' else original_permission(user,code))
        denied=ok(teacher.get('/api/v1/internship/dashboard',params={'batchId':story['batchId']}));assert not denied['workItems'] and denied['workItemTotal']==0
