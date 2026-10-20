"""Real HTTP/MySQL repair tests; no dependency-overridden enterprise authorization.

Frozen-state fixtures characterize the writer; they are not evidence that the entire
score publication/archive business journey ran. The placement-switch test separately
uses the production assignment command and immutable snapshot authority.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.context import set_tenant, set_current_user
from app.core.security import create_access_token, hash_password
from app.db.session import get_sessionmaker
from app.models import (EmpCompany, InternshipArchive, InternshipAuditTrail, InternshipEnterpriseEval,
                        InternshipFinalScore, InternshipRecord, Tenant, User)
from app.models.internship_enterprise_portal import InternshipEnterpriseMember, InternshipEnterpriseAccessGrant
from app.modules.internship.services import internship_enterprise_auth_service as auth
from tests.test_internship_enterprise_eval import _seed

TID=1000000000000000001
ROOT='/api/v1/internship/enterprise-portal'


def identity_for(record_id):
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,record_id)
        company=db.get(EmpCompany,record.enterprise_id)
        company.status='ACTIVE'; company.coop_status='ACTIVE'; company.qualification_status='PASSED'
        tenant=db.get(Tenant,TID)
        if not tenant:
            tenant=Tenant(id=TID,tenant_code='demo',school_name='Repair fixture school',status='ACTIVE')
            db.add(tenant)
        user=User(tenant_id=TID,login_name='repair-'+uuid4().hex[:8],real_name='Repair HR',
                  password_hash=hash_password(uuid4().hex),user_type='ENTERPRISE_MENTOR',status='ACTIVE')
        db.add(user);db.flush()
        member=InternshipEnterpriseMember(tenant_id=TID,company_id=company.id,user_id=user.id,member_role='HR',status='ACTIVE')
        db.add(member);db.flush()
        now=datetime.utcnow()
        grant=InternshipEnterpriseAccessGrant(tenant_id=TID,member_id=member.id,company_id=company.id,
            grant_type='INTERNSHIP_COLLAB',batch_id=record.batch_id,status='ACTIVE',
            valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=30))
        db.add(grant);db.commit()
        token=create_access_token(auth._claims(tenant=tenant,user=user,member=member))
        return {'headers':{'Authorization':'Bearer '+token},'record':record_id,'batch':record.batch_id,
                'placement':str(record.current_placement_snapshot_id),'member':member.id,'grant':grant.id}


@pytest.fixture
def case(db_mode):
    ids=_seed(db_mode)
    return identity_for(ids['rec_a'])


def payload(case, **overrides):
    return {'attendanceScore':90,'skillScore':88,'attitudeScore':92,'collaborationScore':91,'safetyScore':95,
            'overallComment':'独立完成岗位训练，提交真实企业评价。','recommendHire':True,
            'expectedPlacementSnapshotId':case['placement'],**overrides}


def post(client,case,body):
    return client.post(f"{ROOT}/evaluation-tasks/{case['record']}/submit",params={'batchId':case['batch']},
                       headers=case['headers'],json=body)


def counts(case):
    with get_sessionmaker()() as db:
        evals=db.scalars(select(InternshipEnterpriseEval).where(
            InternshipEnterpriseEval.tenant_id==TID,InternshipEnterpriseEval.internship_id==case['record'])).all()
        audit=db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id==TID,InternshipAuditTrail.action=='ENTERPRISE_ONLINE_SUBMIT'))
        return len(evals),int(audit or 0)


def test_first_submit_persists_exact_placement_and_one_audit(client,case):
    tasks=client.get(ROOT+'/evaluation-tasks',headers=case['headers'],params={'batchId':case['batch']})
    assert tasks.status_code==200,tasks.text
    task=next(t for t in tasks.json()['data']['items'] if t['id']==str(case['record']))
    assert task['placementSnapshotId']==case['placement']
    response=post(client,case,payload(case,sourceType='FORGED',recordedByUserId='other'))
    assert response.status_code==200,response.text
    with get_sessionmaker()() as db:
        row=db.get(InternshipEnterpriseEval,int(response.json()['data']['id']))
        assert str(row.placement_snapshot_id)==case['placement']
        assert row.source_type=='ENTERPRISE_ONLINE'
        assert row.recorded_by_user_id!='other'
    assert counts(case)==(1,1)
    assert post(client,case,payload(case)).status_code==409
    assert counts(case)==(1,1)


@pytest.mark.parametrize('value',[None,0,True,'','0','01','1e3',' 1','１',9007199254740993])
def test_invalid_expected_placement_cannot_write(client,case,value):
    before=counts(case)
    body=payload(case,expectedPlacementSnapshotId=value)
    if value is None:body.pop('expectedPlacementSnapshotId')
    response=post(client,case,body)
    assert response.status_code in {400,422},response.text
    assert counts(case)==before


def test_stale_placement_cannot_write(client,case):
    assert post(client,case,payload(case,expectedPlacementSnapshotId=str(int(case['placement'])+1))).status_code==409
    assert counts(case)==(0,0)


def test_returned_resubmit_preserves_exact_version_cas(client,case):
    response=post(client,case,payload(case));assert response.status_code==200,response.text
    eid=int(response.json()['data']['id'])
    # Initial review state fixture, not a claim to have run school's entire review workflow.
    with get_sessionmaker()() as db:
        row=db.get(InternshipEnterpriseEval,eid);row.school_review_status='RETURNED';row.version=3;db.commit()
    before=counts(case)
    for version in [None,2]:
        body=payload(case)
        if version is not None:body['expectedVersion']=version
        assert post(client,case,body).status_code==409
    assert counts(case)==before
    ok=post(client,case,payload(case,expectedVersion=3))
    assert ok.status_code==200,ok.text
    assert ok.json()['data']['version']==4
    assert counts(case)==(1,2)


@pytest.mark.parametrize('frozen',['PUBLISHED','ARCHIVE','RECORD_ARCHIVED'])
def test_frozen_source_facts_reject_direct_enterprise_write(client,case,frozen):
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,case['record'])
        if frozen=='PUBLISHED':
            db.add(InternshipFinalScore(tenant_id=TID,internship_id=record.id,student_id=record.student_id,
                batch_id=record.batch_id,status='PUBLISHED'))
        elif frozen=='ARCHIVE':
            db.add(InternshipArchive(tenant_id=TID,internship_id=record.id,student_id=record.student_id,
                batch_id=record.batch_id,status='ARCHIVED'))
        else:record.status='ARCHIVED'
        db.commit()
    before=counts(case)
    assert post(client,case,payload(case)).status_code==409
    assert counts(case)==before


def test_revoked_member_and_other_batch_cannot_write(client,case):
    bad=client.post(f"{ROOT}/evaluation-tasks/{case['record']}/submit",params={'batchId':int(case['batch'])+123},
                    headers=case['headers'],json=payload(case))
    assert bad.status_code in {401,403,404},bad.text
    with get_sessionmaker()() as db:
        member=db.get(InternshipEnterpriseMember,case['member']);member.status='DISABLED';db.commit()
    assert post(client,case,payload(case)).status_code in {401,403}
    assert counts(case)==(0,0)


def test_two_real_http_submissions_have_single_winner(client,case):
    from fastapi.testclient import TestClient
    from app.main import app
    barrier=Barrier(2)
    def send():
        # Separate HTTP client and separate request-local database sessions.
        with TestClient(app) as browser:
            barrier.wait(timeout=10)
            return post(browser,case,payload(case)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(lambda _:send(),range(2)))
    assert sorted(result)==[200,409],result
    assert counts(case)==(1,1)


def test_form_open_before_same_company_formal_position_switch_cannot_bind_new_placement(client,auth_headers,db_mode):
    from tests.test_internship_p1_acceptance import _credit,_mk_running_batch,_mk_student,_uniq,ENT,IST
    from tests.test_internship_placement_snapshot_mysql import _position
    from app.modules.internship.services import internship_student_service as student_svc
    batch=_mk_running_batch(client,auth_headers);student,_=_mk_student(client,auth_headers)
    result=client.post(IST,headers=auth_headers,json={'studentId':student,'batchId':batch}).json()
    assert result['code']==0,result
    rid=int(result['data']['id'])
    company=client.post(ENT,headers=auth_headers,json={'name':_uniq('安置企业'),'creditCode':_credit()}).json()
    assert company['code']==0,company
    cid=company['data']['id']
    reviewed=client.post(f"{ENT}/{cid}/review",headers=auth_headers,json={'action':'APPROVE','expectedVersion':company['data'].get('version',0)}).json()
    assert reviewed['code']==0,reviewed
    p1=_position(client,auth_headers,batch,cid,_uniq('岗位A'),3500,'长沙A园区')
    p2=_position(client,auth_headers,batch,cid,_uniq('岗位B'),4200,'长沙B园区')
    admin={'userId':'1','realName':'school_admin01','loginName':'school_admin01','currentRoleCode':'SCHOOL_ADMIN','userType':'TEACHER'}
    set_tenant({'tenantId':str(TID)});set_current_user(admin)
    first=student_svc.assign_position(rid,p1,expected_version=0,user=admin)
    case=identity_for(rid);old_payload=payload(case)
    tasks=client.get(ROOT+'/evaluation-tasks',headers=case['headers'],params={'batchId':batch})
    assert tasks.status_code==200,tasks.text
    set_tenant({'tenantId':str(TID)});set_current_user(admin)
    student_svc.assign_position(rid,p2,expected_version=int(first['version']),user=admin)
    stale=post(client,case,old_payload)
    assert stale.status_code==409,stale.text
    assert counts(case)==(0,0)
    with get_sessionmaker()() as db:
        current=str(db.get(InternshipRecord,rid).current_placement_snapshot_id)
    assert current!=case['placement']
    ok=post(client,case,payload(case,expectedPlacementSnapshotId=current))
    assert ok.status_code==200,ok.text
    assert counts(case)==(1,1)
