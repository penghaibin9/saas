"""Evaluation/score stories prepare new schools only; all target actions use normal APIs."""
from datetime import date,datetime,timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (Tenant,User,StudentProfile,InternshipRecord,InternshipBatch,EmpCompany,
    InternshipPosition,InternshipEnterpriseContact,InternshipInsurance,InternshipAgreement,
    InternshipCheckin,WeeklyReport,InternshipProcessReport,InternshipGuidance)
from app.models.internship_enterprise_portal import (InternshipRecruitmentCampaign,
    InternshipCampaignEnterprise,InternshipEnterpriseMember,InternshipEnterpriseAccessGrant)
from app.core.field_crypto import encrypt_sensitive
from app.modules.internship.services.internship_placement_snapshot_service import capture_placement_snapshot_in_tx
from test_student_support_story_mysql import seed_support,context,result
from test_yiyang_plan_export_options_mysql import login,PASSWORD

STAFF='/api/v1/internship'
PORTAL='/api/v1/mobile/internship/context'
ENTERPRISE=STAFF+'/enterprise-portal'


def seed_score_story():
    story=seed_support()
    tid=int(story['tenantId']);now=datetime.utcnow()
    with get_sessionmaker()() as db:
        db.get(Tenant,tid).school_name='评价成绩闭环合成学校'
        record=db.get(InternshipRecord,int(story['recordId']))
        batch=db.get(InternshipBatch,int(story['batchId']))
        batch.batch_name='2026评价成绩验收批次'
        batch.rules_config={'checkin':{'requiredDays':1},'weeklyReport':{'requiredCount':1},
            'processReport':{'monthlyRequiredCount':1,'summaryRequiredCount':1},
            'guidance':{'expectedCount':1},'visit':{'expectedCount':0}}
        student=db.get(StudentProfile,int(story['studentId']))
        student.real_name='成绩验收学生';student.student_no='000000000000000000321'
        digits='43090220050101001'
        weights=[7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
        student.id_card_encrypted=encrypt_sensitive(digits+'10X98765432'[sum(int(v)*w for v,w in zip(digits,weights))%11],'id_card')
        for role,name in [('SCHOOL_ADMIN','成绩验收学校管理员'),('INTERN_MENTOR','成绩验收指导教师'),('STUDENT','成绩验收学生')]:
            db.get(User,story['users'][role]).real_name=name
        company=EmpCompany(tenant_id=tid,name='成绩验收合成企业',credit_code='91310000'+uuid4().hex[:10].upper(),
            status='ACTIVE',coop_status='ACTIVE',qualification_status='PASSED',blacklist=False,access_valid_until=now+timedelta(days=90))
        db.add(company);db.flush()
        campaign=InternshipRecruitmentCampaign(tenant_id=tid,batch_id=batch.id,campaign_code='SCORE-'+uuid4().hex[:8],
            campaign_name='评价成绩验收企业协同',round_no=1,status='OPEN',enterprise_access_end_at=now+timedelta(days=30))
        db.add(campaign);db.flush()
        contact=InternshipEnterpriseContact(tenant_id=tid,company_id=company.id,name='成绩验收企业导师',contact_type='MENTOR',
            phone_encrypted=encrypt_sensitive('13800000000','phone'),status='ACTIVE')
        db.add(contact);db.flush()
        position=InternshipPosition(tenant_id=tid,company_id=company.id,company_name=company.name,
            batch_id=batch.id,campaign_id=campaign.id,title='软件技术实习生',status='PUBLISHED',headcount=2,
            mentor_contact_id=contact.id,mentor_name=contact.name,daily_hours=8,weekly_hours=40,
            night_shift=False,overtime_allowed=False,rest_days_per_week=2,rights_status='PASSED')
        db.add(position);db.flush()
        record.enterprise_id=company.id;record.position_id=position.id;record.enterprise_name=company.name
        record.advisor_name='成绩验收指导教师'
        record.position_name=position.title;record.mentor_contact_id=contact.id;record.enterprise_mentor_name=contact.name
        record.status='ONBOARD';record.intern_start_date=datetime(2026,9,1);record.intern_end_date=datetime(2026,12,31)
        record.agreement_info='SIGNED';record.insurance_info='VALID'
        from app.core.context import set_tenant,get_tenant
        previous_tenant=get_tenant()
        set_tenant({'tenantId':str(tid)})
        try:
            placement=capture_placement_snapshot_in_tx(db,record=record,company=company,position=position,rights={'passed':True,'ruleVersion':'SYNTHETIC-PRECONDITION'})
        finally:
            set_tenant(previous_tenant)
        actor=User(tenant_id=tid,login_name='enterprise_mentor',real_name=contact.name,
            password_hash=db.get(User,story['users']['STUDENT']).password_hash,user_type='ENTERPRISE_MENTOR',
            status='ACTIVE',must_change_password=False,credential_version=0)
        db.add(actor);db.flush()
        member=InternshipEnterpriseMember(tenant_id=tid,company_id=company.id,user_id=actor.id,contact_id=contact.id,
            member_role='MENTOR',status='ACTIVE',accepted_at=now,is_primary=True)
        db.add(member);db.flush()
        db.add(InternshipCampaignEnterprise(tenant_id=tid,campaign_id=campaign.id,company_id=company.id,status='ACCEPTED',invite_source='MANUAL',accepted_at=now))
        for kind,campaign_id in [('INTERNSHIP_COLLAB',None),('RECRUITMENT',campaign.id)]:
            db.add(InternshipEnterpriseAccessGrant(tenant_id=tid,member_id=member.id,company_id=company.id,
                grant_type=kind,campaign_id=campaign_id,batch_id=batch.id,status='ACTIVE',
                valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=30)))
        # These retained process facts are preconditions; no evaluation or final score is seeded.
        db.add_all([
            InternshipInsurance(tenant_id=tid,internship_id=record.id,student_id=student.id,status='VERIFIED',
                effective_date='2026-09-01',expiry_date='2026-12-31',policy_no='SYNTHETIC-SCORE-PRECONDITION'),
            InternshipAgreement(tenant_id=tid,internship_id=record.id,student_id=student.id,batch_id=batch.id,status='EFFECTIVE'),
            InternshipCheckin(tenant_id=tid,internship_id=record.id,checkin_date='2026-10-13',checkin_at=now,result='NORMAL'),
            WeeklyReport(tenant_id=tid,internship_id=record.id,week_number=1,word_count=800,report_version=1,submitted_at=now,status='APPROVED'),
            InternshipProcessReport(tenant_id=tid,internship_id=record.id,report_type='MONTHLY',period_key='2026-09',content='合成历史过程报告前置资料',status='APPROVED'),
            InternshipProcessReport(tenant_id=tid,internship_id=record.id,report_type='SUMMARY',period_key='2026-10',content='合成历史总结前置资料',status='APPROVED'),
            InternshipGuidance(tenant_id=tid,internship_id=record.id,student_id=student.id,
                advisor_name='成绩验收指导教师',guidance_date=date(2026,10,13),content='合成历史指导前置资料',status='NORMAL')])
        db.commit()
        story.update(companyId=str(company.id),campaignId=str(campaign.id),memberId=str(member.id),
            placementId=str(placement.id),enterpriseUserId=str(actor.id))
    return story


def enter_assessment(school,story):
    record=result(school.get(STAFF+'/intern-students/'+story['recordId']))
    return result(school.post(STAFF+'/intern-students/'+story['recordId']+'/status',json={
        'action':'ASSESS','reason':'本轮评价成绩正常办理验收','expectedVersion':record['version']}))


def enterprise_login(story):
    from fastapi.testclient import TestClient
    from app.main import app
    client=TestClient(app)
    response=client.post(ENTERPRISE+'/auth/browser-login',json={'tenantCode':story['tenantCode'],
        'loginName':'enterprise_mentor','password':PASSWORD,'memberId':story['memberId']},headers={'X-Browser-Session-Id':'score-'+uuid4().hex})
    auth=result(response)
    client.headers.update({'Authorization':'Bearer '+auth['accessToken']})
    return client


@pytest.fixture
def story(record_property):
    value=seed_score_story();record_property('tenantId',value['tenantId']);return value


def test_normal_roles_can_enter_assessment_and_missing_sources_block_publication(story):
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student:
        assessed=enter_assessment(school,story);assert assessed['status']=='ASSESSING'
        draft=result(teacher.post(STAFF+'/scores/compute',json={'internshipId':story['recordId']}))
        assert draft['incomplete'] and draft['total'] is None
        assert not draft['sourceReadiness']['enterpriseEvaluation'] and not draft['sourceReadiness']['studentSelfEvaluation']
        denied=school.post(STAFF+'/scores/'+draft['id']+'/review',json={'expectedVersion':draft['version']})
        assert denied.status_code==400 and denied.json()['bizCode']=='DATA_CONFLICT'
        dashboard=result(student.get('/api/v1/mobile/internship/context/my',params={'batchId':story['batchId']}))
        assert dashboard.get('score') is None


def evaluation_body(story,version=None):
    return {'expectedPlacementSnapshotId':story['placementId'],'attendanceScore':90,'skillScore':80,
        'attitudeScore':85,'collaborationScore':95,'safetyScore':90,
        'overallComment':'合成验收：学生能够完成岗位任务，企业独立账号如实评价。',
        **({'expectedVersion':version} if version is not None else {})}


def complete_evaluations(story,school,teacher,student,enterprise):
    enter_assessment(school,story)
    task=result(enterprise.get(ENTERPRISE+'/evaluation-tasks',params={'batchId':story['batchId']}))
    assert len(task['items'])==1
    evaluation=result(enterprise.post(ENTERPRISE+'/evaluation-tasks/'+story['recordId']+'/submit',
        params={'batchId':story['batchId']},json=evaluation_body(story)))
    result(school.post(STAFF+'/enterprise-evals/'+evaluation['id']+'/review',json={
        'action':'APPROVE','comment':'学校核对企业独立评价','expectedVersion':evaluation['version']}))
    self_eval=result(student.post(PORTAL+'/self-eval',json={**context(story),
        'selfSummary':'合成验收：本人在实习中完成岗位工作，掌握工作流程，认识到需要持续改进沟通与协作。',
        'enterpriseRating':4,'positionRating':4}))
    commented=result(teacher.post(STAFF+'/student-evals/'+self_eval['id']+'/advisor-comment',json={
        'advisorOpinion':'合成验收：学生实习表现良好，能够按要求完成任务。','expectedVersion':self_eval['version']}))
    result(school.post(STAFF+'/student-evals/'+self_eval['id']+'/review',json={
        'action':'APPROVE','comment':'学校核对当前学生自评与指导意见','expectedVersion':commented['version']}))
    return evaluation,self_eval


def test_enterprise_self_advisor_manual_score_independent_review_publish_student_readback(story):
    from test_yiyang_write_flows_mysql import upload
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student,enterprise_login(story) as enterprise:
        evaluation,self_eval=complete_evaluations(story,school,teacher,student,enterprise)
        evidence=upload(teacher,biz='INTERNSHIP_SCORE_ADJUSTMENT')
        computed=result(teacher.post(STAFF+'/scores/compute',json={'internshipId':story['recordId'],
            'manualAdjustments':{'school':-5},'adjustmentReason':'合成评分标准：沟通协作仍需改进，校内评价扣五分',
            'adjustmentEvidenceFileIds':[evidence['fileId']]}))
        assert computed['total']==95.4 and not computed['incomplete'] and all(computed['sourceReadiness'].values())
        assert result(teacher.get(STAFF+'/scores/'+computed['id']))['allowedActions']==[]
        assert 'review' in result(school.get(STAFF+'/scores/'+computed['id']))['allowedActions']
        assert teacher.post(STAFF+'/scores/'+computed['id']+'/review',json={'expectedVersion':computed['version']}).status_code==403
        assert teacher.post(STAFF+'/scores/'+computed['id']+'/publish',json={'expectedVersion':computed['version']}).status_code==403
        before=result(student.get('/api/v1/mobile/internship/context/my',params={'batchId':story['batchId']}))
        assert before.get('score') is None
        reviewed=result(school.post(STAFF+'/scores/'+computed['id']+'/review',json={'expectedVersion':computed['version']}))
        assert reviewed['status']=='PENDING_PUBLISH'
        assert result(school.get(STAFF+'/scores/'+computed['id']))['allowedActions']==['return','publish']
        published=result(school.post(STAFF+'/scores/'+computed['id']+'/publish',json={'expectedVersion':reviewed['version']}))
        assert published['status']=='PUBLISHED'
        after=result(student.get('/api/v1/mobile/internship/context/my',params={'batchId':story['batchId']}))
        assert after['score']['totalScore']==95.4 and after['score']['enterpriseScore']==88 and after['score']['schoolScore']==95
        detail=result(school.get(STAFF+'/scores/'+computed['id']))
        assert detail['manualAdjustments']['school']==-5 and detail['adjustmentReviewStatus']=='APPROVED'
        blocked=enterprise.post(ENTERPRISE+'/evaluation-tasks/'+story['recordId']+'/submit',params={'batchId':story['batchId']},json=evaluation_body(story))
        assert blocked.status_code in (400,409) and blocked.json()['bizCode']=='DATA_CONFLICT'


def test_returned_self_evaluation_keeps_id_and_requires_new_advisor_opinion(story):
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student:
        first=result(student.post(PORTAL+'/self-eval',json={**context(story),'selfSummary':'学生实际填写完整的实习自评内容，记录岗位成果和改进方向。'}))
        opinion=result(teacher.post(STAFF+'/student-evals/'+first['id']+'/advisor-comment',json={
            'expectedVersion':first['version'],'advisorOpinion':'导师核对原始自评意见。'}))
        returned=result(school.post(STAFF+'/student-evals/'+first['id']+'/review',json={
            'action':'RETURN','comment':'请补充具体岗位成果','expectedVersion':opinion['version']}))
        revised=result(student.post(PORTAL+'/self-eval',json={**context(story),'expectedVersion':returned['version'],
            'selfSummary':'按学校意见补充岗位工作成果和实际完成情况，明确了后续改进措施与责任。'}))
        assert revised['id']==first['id'] and not revised['advisorOpinion']
        denied=school.post(STAFF+'/student-evals/'+first['id']+'/review',json={'action':'APPROVE','expectedVersion':revised['version']})
        assert denied.json()['bizCode']=='DATA_CONFLICT'
        stale=teacher.post(STAFF+'/student-evals/'+first['id']+'/advisor-comment',json={
            'expectedVersion':opinion['version'],'advisorOpinion':'旧页面提交不能覆盖新自评。'})
        assert stale.json()['bizCode']=='DATA_CONFLICT'


def test_returned_enterprise_evaluation_reuses_original_and_explicit_zero(story):
    with login(story) as school,enterprise_login(story) as enterprise:
        enter_assessment(school,story)
        first=result(enterprise.post(ENTERPRISE+'/evaluation-tasks/'+story['recordId']+'/submit',params={'batchId':story['batchId']},json=evaluation_body(story)))
        returned=result(school.post(STAFF+'/enterprise-evals/'+first['id']+'/review',json={
            'action':'RETURN','comment':'请核对实际表现后重交','expectedVersion':first['version']}))
        body=evaluation_body(story,returned['version']);body['skillScore']=0
        second=result(enterprise.post(ENTERPRISE+'/evaluation-tasks/'+story['recordId']+'/submit',params={'batchId':story['batchId']},json=body))
        assert first['id']==second['id']
        detail=result(school.get(STAFF+'/enterprise-evals/'+first['id']))
        assert detail['skillScore']==0 and detail['source']=='ENTERPRISE_ONLINE'
        duplicate=enterprise.post(ENTERPRISE+'/evaluation-tasks/'+story['recordId']+'/submit',params={'batchId':story['batchId']},json=body)
        assert duplicate.json()['bizCode']=='DATA_CONFLICT'


def test_source_rule_change_after_review_blocks_stale_publication(story):
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student,enterprise_login(story) as enterprise:
        complete_evaluations(story,school,teacher,student,enterprise)
        computed=result(teacher.post(STAFF+'/scores/compute',json={'internshipId':story['recordId']}))
        reviewed=result(school.post(STAFF+'/scores/'+computed['id']+'/review',json={'expectedVersion':computed['version']}))
        result(school.post(STAFF+'/scores/config',json={'checkinWeight':20,'weeklyWeight':20,'monthlyWeight':10,'enterpriseWeight':30,'schoolWeight':20,'passLine':60}))
        denied=school.post(STAFF+'/scores/'+computed['id']+'/publish',json={'expectedVersion':reviewed['version']})
        assert denied.json()['bizCode']=='DATA_CONFLICT' and '来源' in denied.json()['message']
        dashboard=result(student.get('/api/v1/mobile/internship/context/my',params={'batchId':story['batchId']}))
        assert dashboard.get('score') is None


def test_new_mentor_capabilities_still_deny_other_students_and_school_review(story):
    from app.models import Role,UserRole
    with login(story,'STUDENT') as student:
        row=result(student.post(PORTAL+'/self-eval',json={**context(story),'selfSummary':'用于跨教师与学校审核权限拒绝的完整合成学生自评资料。'}))
    with get_sessionmaker()() as db:
        tid=int(story['tenantId'])
        actor=User(tenant_id=tid,login_name='other_mentor',real_name='无关联指导教师',
            password_hash=db.get(User,story['users']['INTERN_MENTOR']).password_hash,user_type='TEACHER',status='ACTIVE',credential_version=0,must_change_password=False)
        db.add(actor);db.flush();role=db.scalar(select(Role).where(Role.tenant_id==tid,Role.role_code=='INTERN_MENTOR'))
        db.add(UserRole(tenant_id=tid,user_id=actor.id,role_id=role.id,status='ACTIVE'));db.commit()
    with login(story,'INTERN_MENTOR') as owner,login(story,'OTHER_MENTOR') as other:
        assert result(owner.get(STAFF+'/student-evals/'+row['id']))['id']==row['id']
        assert other.get(STAFF+'/student-evals/'+row['id']).status_code==403
        assert other.post(STAFF+'/student-evals/'+row['id']+'/advisor-comment',json={'expectedVersion':row['version'],'advisorOpinion':'无关联教师尝试意见'}).status_code==403
        assert owner.post(STAFF+'/student-evals/'+row['id']+'/review',json={'action':'APPROVE','expectedVersion':row['version']}).status_code==403
    foreign=seed_score_story()
    with login(foreign) as other_school:
        assert other_school.get(STAFF+'/student-evals/'+row['id']).status_code==404


def test_manual_adjuster_cannot_review_their_own_adjustment(story):
    from test_yiyang_write_flows_mysql import upload
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student,enterprise_login(story) as enterprise:
        complete_evaluations(story,school,teacher,student,enterprise)
        evidence=upload(school,biz='INTERNSHIP_SCORE_ADJUSTMENT')
        computed=result(school.post(STAFF+'/scores/compute',json={'internshipId':story['recordId'],
            'manualAdjustments':{'school':-5},'adjustmentReason':'验证人工调整必须由另一授权人复核','adjustmentEvidenceFileIds':[evidence['fileId']]}))
        assert 'review' not in result(school.get(STAFF+'/scores/'+computed['id']))['allowedActions']
        denied=school.post(STAFF+'/scores/'+computed['id']+'/review',json={'expectedVersion':computed['version']})
        assert denied.json()['bizCode']=='DATA_CONFLICT' and '不同用户' in denied.json()['message']
