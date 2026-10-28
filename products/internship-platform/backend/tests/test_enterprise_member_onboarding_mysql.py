"""New synthetic schools only: invitations, binding and grants are all normal API actions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from uuid import uuid4
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.db.session import get_sessionmaker
from app.main import app
from app.models import EmpCompany, InternshipBatch, InternshipEnterpriseContact, InternshipPosition, InternshipRecord, User
from app.models.audit import SecurityAuditLog
from app.models.internship_enterprise_portal import InternshipCampaignEnterprise, InternshipEnterpriseAccessGrant, InternshipEnterpriseMember
from app.modules.internship.services.internship_placement_snapshot_service import capture_placement_snapshot_in_tx
from test_student_support_story_mysql import result, seed_support
from test_yiyang_plan_export_options_mysql import login, PASSWORD

STAFF='/api/v1/internship'
PORTAL=STAFF+'/enterprise-portal'


def prepare():
    story=seed_support();tid=int(story['tenantId']);now=datetime.utcnow()
    with get_sessionmaker()() as db:
        company=EmpCompany(tenant_id=tid,name='企业开通合成企业',credit_code='91310000'+uuid4().hex[:10].upper(),
            status='ACTIVE',coop_status='ACTIVE',qualification_status='PASSED',access_valid_until=now+timedelta(days=90))
        db.add(company);db.flush()
        contact=InternshipEnterpriseContact(tenant_id=tid,company_id=company.id,name='开通合成企业导师',contact_type='MENTOR',status='ACTIVE')
        position=InternshipPosition(tenant_id=tid,company_id=company.id,company_name=company.name,batch_id=int(story['batchId']),
            title='合成实习岗位',status='PUBLISHED',headcount=10,rights_status='PASSED')
        db.add_all([contact,position]);db.flush()
        position.mentor_contact_id=contact.id;position.mentor_name=contact.name
        record=db.get(InternshipRecord,int(story['recordId']));record.enterprise_id=company.id;record.position_id=position.id
        record.enterprise_name=company.name;record.position_name=position.title;record.mentor_contact_id=contact.id;record.enterprise_mentor_name=contact.name
        from app.core.context import get_tenant,set_tenant
        previous=get_tenant();set_tenant({'tenantId':story['tenantId']})
        try:placement=capture_placement_snapshot_in_tx(db,record=record,company=company,position=position,rights={'passed':True,'ruleVersion':'SYNTHETIC-ONBOARDING-PRECONDITION'})
        finally:set_tenant(previous)
        db.commit()
        story.update(companyId=str(company.id),contactId=str(contact.id),placementId=str(placement.id))
    with login(story) as school:
        campaign=result(school.post(STAFF+'/recruitment-campaigns',json={'batchId':story['batchId'],'campaignCode':'MEMBER-'+uuid4().hex[:12],
            'campaignName':'企业成员开通合成招聘季','roundNo':1,'inviteStartAt':(now-timedelta(days=1)).isoformat()+'Z',
            'inviteEndAt':(now+timedelta(days=5)).isoformat()+'Z','enterpriseAccessEndAt':(now+timedelta(days=20)).isoformat()+'Z'}))
        result(school.post(STAFF+'/recruitment-campaigns/'+campaign['id']+'/open',json={'expectedVersion':campaign['version']}))
    story['campaignId']=campaign['id']
    return story


def members_root(story):return STAFF+'/enterprises/'+story['companyId']+'/members'


def invite_and_accept(story,school,name,role):
    body={'companyId':story['companyId'],'loginName':name,'realName':'合成'+name,'phone':'13800001234','memberRole':role}
    invited=result(school.post(STAFF+'/recruitment-campaigns/'+story['campaignId']+'/enterprises/invite',json=body))
    client=TestClient(app)
    auth=result(client.post(PORTAL+'/auth/browser-invite/accept',headers={'X-Browser-Session-Id':'member-'+uuid4().hex},
        json={'tenantCode':story['tenantCode'],'token':invited['inviteToken'],'phone':body['phone'],'password':PASSWORD}))
    client.headers.update({'Authorization':'Bearer '+auth['accessToken']})
    return invited['memberId'],client


def relogin(story,client,name,member_id):
    auth=result(client.post(PORTAL+'/auth/browser-login',headers={'X-Browser-Session-Id':'member-'+uuid4().hex},
        json={'tenantCode':story['tenantCode'],'loginName':name,'password':PASSWORD,'memberId':member_id}))
    client.headers.update({'Authorization':'Bearer '+auth['accessToken']})


def grant_body(story,version):
    now=datetime.utcnow()
    return {'batchId':story['batchId'],'validFrom':(now-timedelta(minutes=1)).isoformat()+'Z',
        'validUntil':(now+timedelta(days=3)).isoformat()+'Z','expectedMemberVersion':version}


def test_explicit_collaboration_without_recruitment_campaign_is_selectable_but_never_grants_recruitment(record_property):
    story=prepare();record_property('tenantId',story['tenantId'])
    with get_sessionmaker()() as db:
        batch=InternshipBatch(tenant_id=int(story['tenantId']),batch_no='COLLAB-'+uuid4().hex[:12],batch_name='无招聘季的正式实习批次',status='RUNNING')
        db.add(batch);db.commit();batch_id=str(batch.id)
    with login(story) as school:
        member_id,enterprise=invite_and_accept(story,school,'batch_only_admin','COMPANY_ADMIN')
        assert not any(row['batchId']==batch_id for row in result(enterprise.get(PORTAL+'/campaigns')))
        member=next(row for row in result(school.get(members_root(story)))['items'] if row['id']==member_id)
        path=members_root(story)+'/'+member_id
        assert school.post(path+'/collaboration-grants',json={**grant_body(story,member['version']),'batchId':batch_id}).status_code==409
        mentor_id,mentor=invite_and_accept(story,school,'batch_only_mentor','MENTOR')
        mentor_row=next(row for row in result(school.get(members_root(story)))['items'] if row['id']==mentor_id)
        mentor_path=members_root(story)+'/'+mentor_id
        bound=result(school.put(mentor_path+'/contact',json={'contactId':story['contactId'],'expectedVersion':mentor_row['version']}))
        relogin(story,mentor,'batch_only_mentor',mentor_id)
        with get_sessionmaker()() as db:
            position=InternshipPosition(tenant_id=int(story['tenantId']),batch_id=int(batch_id),company_id=int(story['companyId']),
                company_name='企业开通合成企业',title='无招聘季的正式岗位',status='FULL',headcount=1,allocated_count=1)
            db.add(position);db.flush()
            record=InternshipRecord(tenant_id=int(story['tenantId']),batch_id=int(batch_id),student_id=int(story['studentId']),
                enterprise_id=int(story['companyId']),position_id=position.id,enterprise_name='企业开通合成企业',position_name=position.title,
                status='READY',destination_type='ASSIGNED',eligibility_status='QUALIFIED')
            db.add(record);db.flush()
            company=db.get(EmpCompany,int(story['companyId']))
            from app.core.context import get_tenant,set_tenant
            previous=get_tenant();set_tenant({'tenantId':story['tenantId']})
            try:capture_placement_snapshot_in_tx(db,record=record,company=company,position=position,rights={'passed':True,'ruleVersion':'SYNTHETIC-ONBOARDING-PRECONDITION'})
            finally:set_tenant(previous)
            db.commit()
            record_id=record.id
        mentor_body={**grant_body(story,bound['version']),'batchId':batch_id}
        assert school.post(mentor_path+'/collaboration-grants',json=mentor_body).status_code==409
        with get_sessionmaker()() as db:
            db.get(InternshipRecord,record_id).mentor_contact_id=int(story['contactId']);db.commit()
        mentor_grant=result(school.post(mentor_path+'/collaboration-grants',json=mentor_body))
        assert result(mentor.get(PORTAL+'/collaboration-context',params={'batchId':batch_id}))['capabilities']['internshipCollab']
        grant=result(school.post(path+'/collaboration-grants',json={**grant_body(story,member['version']),'batchId':batch_id}))
        rows=result(enterprise.get(PORTAL+'/campaigns'))
        selected=next(row for row in rows if row['batchId']==batch_id)
        assert selected['scopeType']=='BATCH' and selected['id']=='batch:'+batch_id
        assert selected['collaborationAvailable'] is True and selected['recruitmentAvailable'] is False and not selected['campaignId']
        context=result(enterprise.get(PORTAL+'/collaboration-context',params={'batchId':batch_id}))
        assert context['campaignId'] is None and context['capabilities']=={'recruitmentWrite':False,'internshipCollab':True}
        result(school.post(path+'/collaboration-grants/'+grant['id']+'/revoke',json={'expectedVersion':grant['version'],'reason':'虚构协同范围验收撤销'}))
        assert not any(row['batchId']==batch_id for row in result(enterprise.get(PORTAL+'/campaigns')))
        assert enterprise.get(PORTAL+'/collaboration-context',params={'batchId':batch_id}).status_code==403
        result(school.post(mentor_path+'/collaboration-grants/'+mentor_grant['id']+'/revoke',json={'expectedVersion':mentor_grant['version'],'reason':'虚构导师协同范围验收撤销'}))
        assert mentor.get(PORTAL+'/collaboration-context',params={'batchId':batch_id}).status_code==403
        enterprise.close();mentor.close()


def test_school_adds_second_member_then_binding_and_explicit_grant_unlock_same_formal_student(record_property):
    story=prepare();record_property('tenantId',story['tenantId'])
    with login(story) as school:
        first_id,first=invite_and_accept(story,school,'company_admin','COMPANY_ADMIN')
        with get_sessionmaker()() as db:
            first_member=db.get(InternshipEnterpriseMember,int(first_id));first_user=db.get(User,first_member.user_id)
            before=(first_member.member_role,first_member.version,first_user.password_hash)
            participation=db.scalar(select(InternshipCampaignEnterprise).where(InternshipCampaignEnterprise.campaign_id==int(story['campaignId'])))
            participation_before=(participation.status,participation.version,participation.accepted_at)
        mentor_id,mentor=invite_and_accept(story,school,'company_mentor','MENTOR')
        rows=result(school.get(members_root(story)))['items'];assert len(rows)==2
        row=next(item for item in rows if item['id']==mentor_id)
        assert mentor.get(PORTAL+'/evaluation-tasks',params={'batchId':story['batchId']}).status_code==403
        path=members_root(story)+'/'+mentor_id
        assert school.post(path+'/collaboration-grants',json=grant_body(story,row['version'])).status_code==400
        bound=result(school.put(path+'/contact',json={'contactId':story['contactId'],'expectedVersion':row['version']}))
        assert mentor.get(PORTAL+'/campaigns').status_code==401
        relogin(story,mentor,'company_mentor',mentor_id)
        granted=result(school.post(path+'/collaboration-grants',json=grant_body(story,bound['version'])))
        assert granted['grantType']=='INTERNSHIP_COLLAB' and not granted['campaignId']
        assert result(mentor.get(PORTAL+'/collaboration-context',params={'batchId':story['batchId']}))['capabilities']['internshipCollab']
        students=result(mentor.get(PORTAL+'/internship-students',params={'batchId':story['batchId']}))
        assert [item['internshipId'] for item in students['items']]==[story['recordId']]
        task=result(mentor.get(PORTAL+'/evaluation-tasks',params={'batchId':story['batchId'],'internshipId':story['recordId']}))['items'][0]
        assert task['placementSnapshotId']==story['placementId']
        submitted=result(mentor.post(PORTAL+'/evaluation-tasks/'+story['recordId']+'/submit',params={'batchId':story['batchId']},json={
            'expectedPlacementSnapshotId':task['placementSnapshotId'],'attendanceScore':0,'skillScore':80,'attitudeScore':90,
            'collaborationScore':85,'safetyScore':95,'overallComment':'企业成员通过学校正式开通后独立提交，显式零分保留。'}))
        assert result(school.get(STAFF+'/enterprise-evals/'+submitted['id']))['attendanceScore']==0
        result(school.post(path+'/collaboration-grants/'+granted['id']+'/revoke',json={'expectedVersion':granted['version'],'reason':'本次协同验收结束'}))
        assert mentor.get(PORTAL+'/evaluation-tasks',params={'batchId':story['batchId']}).status_code==403
        assert school.post(path+'/collaboration-grants',json=grant_body(story,bound['version'])).status_code==409
        with get_sessionmaker()() as db:
            first_member=db.get(InternshipEnterpriseMember,int(first_id));first_user=db.get(User,first_member.user_id)
            assert (first_member.member_role,first_member.version,first_user.password_hash)==before
            participation=db.scalar(select(InternshipCampaignEnterprise).where(InternshipCampaignEnterprise.campaign_id==int(story['campaignId'])))
            assert (participation.status,participation.version,participation.accepted_at)==participation_before
            count=db.scalar(select(func.count()).select_from(SecurityAuditLog).where(SecurityAuditLog.tenant_id==int(story['tenantId']),SecurityAuditLog.action.in_(
                ['INVITE_RECRUITMENT_ENTERPRISE','ENTERPRISE_INVITE_ACCEPT','ENTERPRISE_MEMBER_CONTACT_BIND','ENTERPRISE_COLLABORATION_GRANT_ISSUE','ENTERPRISE_COLLABORATION_GRANT_REVOKE'])))
            assert count==7
        first.close();mentor.close()


def test_parallel_grants_use_member_lock_and_permission_audit_failures_leave_no_access(monkeypatch,record_property):
    story=prepare();record_property('tenantId',story['tenantId'])
    with login(story) as school,login(story) as other,login(story,'INTERN_MENTOR') as teacher:
        member_id,enterprise=invite_and_accept(story,school,'parallel_admin','COMPANY_ADMIN')
        path=members_root(story)+'/'+member_id
        row=result(school.get(members_root(story)))['items'][0];body=grant_body(story,row['version'])
        assert teacher.get(members_root(story)).status_code==403
        from app.modules.internship.services import internship_enterprise_member_admin_service as admin
        with monkeypatch.context() as patch:
            def failed(*args,**kwargs):raise RuntimeError('synthetic mandatory audit unavailable')
            patch.setattr(admin,'audit_insert_in_session',failed)
            with pytest.raises(RuntimeError):school.post(path+'/collaboration-grants',json=body)
        with get_sessionmaker()() as db:
            assert db.scalar(select(func.count()).select_from(InternshipEnterpriseAccessGrant).where(
                InternshipEnterpriseAccessGrant.member_id==int(member_id),InternshipEnterpriseAccessGrant.grant_type=='INTERNSHIP_COLLAB'))==0
        barrier=Barrier(2)
        def issue(client):barrier.wait(timeout=10);return client.post(path+'/collaboration-grants',json=body)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(issue,client) for client in [school,other]];responses=[f.result(timeout=30) for f in futures]
        assert sorted(r.status_code for r in responses)==[200,409]
        with get_sessionmaker()() as db:
            assert db.scalar(select(func.count()).select_from(InternshipEnterpriseAccessGrant).where(
                InternshipEnterpriseAccessGrant.member_id==int(member_id),InternshipEnterpriseAccessGrant.grant_type=='INTERNSHIP_COLLAB'))==1
            assert db.scalar(select(func.count()).select_from(SecurityAuditLog).where(SecurityAuditLog.tenant_id==int(story['tenantId']),SecurityAuditLog.action=='ENTERPRISE_COLLABORATION_GRANT_ISSUE'))==1
        enterprise.close()
