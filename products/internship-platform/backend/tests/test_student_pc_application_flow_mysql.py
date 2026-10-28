"""Explicit PC applications use normal roles and newly created isolated school records."""
from datetime import date,datetime,timedelta
import pytest
from app.db.session import get_sessionmaker
from app.models import InternshipRecord,StudentProfile,EmpCompany,InternshipPosition
from test_student_pc_dashboard_reports_mysql import story,ok
from test_yiyang_write_flows_mysql import login,context,upload
from test_yiyang_gap09_minimum_age import encrypted_student

@pytest.fixture
def ready(story):
    with get_sessionmaker()() as db:
        row=db.get(InternshipRecord,int(story['recordId']));row.status='READY';row.destination_type='NONE'
        db.get(StudentProfile,int(story['studentId'])).id_card_encrypted=encrypted_student(date(2000,1,1)).id_card_encrypted
        db.commit()
    return story

def approve(school,story,row):
    record=ok(school.get('/api/v1/internship/intern-students/'+story['recordId']))
    return ok(school.post('/api/v1/internship/applications/'+row['id']+'/review',json={'action':'APPROVE','batchId':story['batchId'],'expectedVersion':row['version'],'recordExpectedVersion':record['version']}))

def test_pc_position_application_approval_uses_canonical_assignment_and_capacity(ready):
    with get_sessionmaker()() as db:
        company=EmpCompany(tenant_id=int(ready['tenantId']),name='虚构正式岗位企业',status='ACTIVE',coop_status='ACTIVE',qualification_status='PASSED',blacklist=False,access_valid_until=datetime.utcnow()+timedelta(days=90));db.add(company);db.flush()
        position=InternshipPosition(tenant_id=int(ready['tenantId']),batch_id=int(ready['batchId']),company_id=company.id,title='虚构正式技术岗位',status='PUBLISHED',headcount=1,allocated_count=0,work_location='虚构岗位地址一号',work_content='核对资料与完成岗位实践',daily_hours=8,weekly_hours=40,night_shift=False,overtime_allowed=False,rest_days_per_week=2,remuneration_type='MONTHLY',remuneration_amount=2000,remuneration_cycle='MONTHLY',accommodation_provided=True,meal_provided=True,hazardous_flag=False);db.add(position);db.commit();position_id=str(position.id)
    with login(ready,'STUDENT') as student,login(ready) as school:
        draft=ok(student.put('/api/v1/portal/internship/context/applications',json={**context(ready),'applicationType':'POSITION','positionId':position_id,'applicationNote':'合成学生申请已发布的校内岗位','expectedVersion':0}))
        submitted=ok(student.post('/api/v1/portal/internship/context/applications/'+draft['id']+'/submit',json={**context(ready),'expectedVersion':draft['version']}))
        result=approve(school,ready,submitted);assert result['id']==draft['id'] and result['status']=='APPROVED'
        read=ok(student.get('/api/v1/portal/internship/my',params={'batchId':ready['batchId']}));assert read['destinationType']=='ASSIGNED'
    with get_sessionmaker()() as db:
        assert db.get(InternshipRecord,int(ready['recordId'])).position_id==int(position_id)
        assert db.get(InternshipPosition,int(position_id)).allocated_count==1

def test_pc_self_arranged_return_resubmit_keeps_complete_fields_zero_values_and_files(ready):
    with login(ready,'STUDENT') as student,login(ready) as school:
        file=upload(student,biz='INTERNSHIP_APPLICATION_EVIDENCE')
        body={**context(ready),'applicationType':'SELF_ARRANGED','companyName':'合成自主实习企业','companyCreditCode':'91310000MA1K000001','companyPrincipal':'合成负责人','companyScale':'小型','companyPhone':'13800138000','companyEmail':'test@example.invalid','companyNature':'民营企业','companyIndustry':'软件服务','companyRegisteredAddress':'合成注册地址一号','companyProvince':'湖南省','companyCity':'益阳市','companyDistrict':'赫山区','companyPostalCode':'413000','contactName':'合成联系人','contactPhone':'13800138000','internshipDepartment':'技术部','positionName':'合成技术岗位','positionCategory':'信息技术','workContent':'完成合成岗位资料核对和技术练习','enterpriseMentorName':'合成企业老师','enterpriseMentorPhone':'13800138000','workCountry':'中国','workProvince':'湖南省','workCity':'益阳市','workDistrict':'赫山区','workAddress':'合成岗位地址一号','internshipStartDate':'2026-09-01','internshipEndDate':'2026-12-30','internshipMode':'自主实习','majorMatch':False,'agreedSalary':0,'evidenceFileId':file['fileId'],'agreementFileIds':[],'applicationNote':'合成自主实习申请说明','expectedVersion':0}
        draft=ok(student.put('/api/v1/portal/internship/context/applications',json=body));path='/api/v1/portal/internship/context/applications/'+draft['id']
        submitted=ok(student.post(path+'/submit',json={**context(ready),'expectedVersion':draft['version']}))
        returned=ok(school.post('/api/v1/internship/applications/'+draft['id']+'/review',json={'action':'REJECT','comment':'请补充合成岗位任务说明','batchId':ready['batchId'],'expectedVersion':submitted['version']}))
        saved=ok(student.put('/api/v1/portal/internship/context/applications',json={**body,'id':draft['id'],'expectedVersion':returned['version'],'applicationNote':'已按学校意见补充合成岗位任务说明'}))
        resubmitted=ok(student.post(path+'/submit',json={**context(ready),'expectedVersion':saved['version']}));approved=approve(school,ready,resubmitted)
        assert approved['id']==draft['id'] and approved['status']=='APPROVED'
        rows=ok(student.get('/api/v1/portal/internship/context/applications',params=context(ready)));row=next(item for item in rows if item['id']==draft['id'])
        assert row['majorMatch'] is False and row['agreedSalary']==0 and row['evidenceFileId']==file['fileId']
        assert row['companyCreditCode']==body['companyCreditCode'] and row['workAddress']==body['workAddress']
        assert ok(student.get('/api/v1/portal/internship/my',params={'batchId':ready['batchId']}))['destinationType']=='SELF_ARRANGED'
