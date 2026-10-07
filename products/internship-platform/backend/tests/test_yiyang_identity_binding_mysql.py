"""Actual browser-login identities must remain bound to their current school student."""
import pytest
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import StudentAccountLink, User
from test_yiyang_gap09_minimum_age_mysql import admin, scenario
from test_yiyang_sp06_sp07_formal_document_mysql import own_client
from test_standalone_browser_auth_mysql import TENANT_ID

READS = ['/context/weekly-reports','/context/reports','/context/self-eval','/insurance','/score/appeal']
BASE = '/api/v1/portal/internship'


@pytest.mark.parametrize('path', READS)
def test_alias_login_reads_own_selected_context(scenario, path):
    s = scenario(years=20)
    with get_sessionmaker()() as db:
        user = db.scalar(select(User).where(User.tenant_id==TENANT_ID, User.login_name==s['login']))
        user.login_name = 'alias-'+s['login']
        s['login'] = user.login_name
        db.commit()
    with own_client(s) as client:
        response = client.get(BASE+path,params={'batchId':s['batchId'],'internshipId':s['id']})
        assert response.status_code==200 and response.json()['code']==0,response.text


@pytest.mark.parametrize('path', READS)
def test_existing_session_loses_access_after_binding_revoked(scenario, path):
    s = scenario(years=20)
    with own_client(s) as client:
        with get_sessionmaker()() as db:
            link=db.scalar(select(StudentAccountLink).where(StudentAccountLink.tenant_id==TENANT_ID,
                           StudentAccountLink.student_id==int(s['studentId']),StudentAccountLink.link_status=='ACTIVE'))
            link.link_status='REVOKED'
            db.commit()
        response=client.get(BASE+path,params={'batchId':s['batchId'],'internshipId':s['id']})
        assert response.status_code in (403,404),response.text
        assert response.json()['code'] != 0


@pytest.mark.parametrize('path', READS)
def test_other_student_context_is_not_accessible(scenario, path):
    first,second=scenario(years=20),scenario(years=20)
    with own_client(first) as client:
        response=client.get(BASE+path,params={'batchId':second['batchId'],'internshipId':second['id']})
        assert response.status_code in (400,403,404),response.text
        assert response.json()['code'] != 0
