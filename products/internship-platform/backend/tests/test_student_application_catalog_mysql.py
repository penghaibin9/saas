"""Non-cleaning first-placement catalog checks in a new isolated synthetic school."""
from datetime import datetime, timedelta
import os
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from app.config import settings
from app.db.session import get_engine, get_sessionmaker
from app.models import College, Major, StudentProfile, InternshipRecord, InternshipPosition, EmpCompany, InternshipEnterpriseCollegeScope
from test_yiyang_write_flows_mysql import seed_flow, login


@pytest.fixture(scope='module')
def catalog():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('requires explicit isolated MySQL test opt-in')
    url=make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == 'test'
    assert url.get_backend_name() == 'mysql'
    assert (url.host, url.port, url.database) in {
        ('127.0.0.1', 3318, 'internship_pr275_test_20261003'),
        ('127.0.0.1', 3306, 'internship_employment_test_ci'),
    }
    with get_engine().connect() as db:
        assert db.scalar(text('SELECT DATABASE()')) == url.database
    ws=seed_flow();tid=int(ws['tenantId']);bid=int(ws['batchId'])
    with get_sessionmaker()() as db:
        student=db.get(StudentProfile,int(ws['studentId']));record=db.get(InternshipRecord,int(ws['recordId']))
        record.status='READY'
        other_record=db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id==tid,InternshipRecord.student_id!=student.id))
        other_record.batch_id=bid;ws['otherRecordId']=str(other_record.id)
        college=College(tenant_id=tid,college_name='目录本院',status='ACTIVE');other=College(tenant_id=tid,college_name='目录外院',status='ACTIVE')
        db.add_all([college,other]);db.flush()
        major=Major(tenant_id=tid,college_id=college.id,major_name='软件技术',status='ACTIVE');db.add(major);db.flush()
        student.college_id=college.id;student.major_id=major.id
        company=EmpCompany(tenant_id=tid,name='公开目录合成企业',coop_status='ACTIVE',blacklist=False)
        foreign=EmpCompany(tenant_id=tid,name='外院专用合成企业',coop_status='ACTIVE',blacklist=False)
        expired=EmpCompany(tenant_id=tid,name='准入过期企业',coop_status='ACTIVE',blacklist=False,access_valid_until=datetime.utcnow()-timedelta(days=1))
        db.add_all([company,foreign,expired]);db.flush()
        db.add_all([InternshipEnterpriseCollegeScope(tenant_id=tid,company_id=company.id,college_id=college.id),InternshipEnterpriseCollegeScope(tenant_id=tid,company_id=foreign.id,college_id=other.id)])
        values=dict(tenant_id=tid,batch_id=bid,company_id=company.id,status='PUBLISHED',headcount=3,allocated_count=0,work_location='合成岗位地址',work_content='岗位工作内容',daily_hours=8,weekly_hours=40,night_shift=False,overtime_allowed=False,rest_days_per_week=2,remuneration_type='UNPAID',accommodation_provided=False,meal_provided=False,hazardous_flag=False)
        visible=[]
        for index in range(23):
            position=InternshipPosition(**values,title=f'目录岗位{index:02}',major_requirement='软件技术');db.add(position);db.flush();visible.append(str(position.id))
        for label,overrides in [('未发布',{'status':'DRAFT'}),('删除',{'is_deleted':True}),('满额',{'allocated_count':3}),('招聘季',{'campaign_id':999999}),('其他批次',{'batch_id':int(ws['batches'][1]['id'])}),('其他院系',{'company_id':foreign.id}),('其他专业',{'major_requirement':'护理'}),('准入过期',{'company_id':expired.id})]:
            db.add(InternshipPosition(**{**values,**overrides},title=label))
        db.commit();ws['visible']=visible
    return ws


def read(client,path,params):
    response=client.get(path,params=params)
    assert response.status_code==200 and response.json()['code']==0,response.text
    return response.json()['data']


def test_mobile_and_pc_catalog_share_scoped_paginated_non_campaign_rows(catalog):
    params={'batchId':catalog['batchId'],'internshipId':catalog['recordId'],'pageSize':20}
    with login(catalog,'STUDENT') as client:
        for prefix in ['/api/v1/mobile/internship','/api/v1/portal/internship']:
            path=prefix+'/context/applications/positions'
            first=read(client,path,params);second=read(client,path,{**params,'page':2})
            assert first['total']==second['total']==23
            assert len(first['items'])==20 and first['hasMore'] is True and len(second['items'])==3 and second['hasMore'] is False
            assert {r['id'] for r in first['items']+second['items']}==set(catalog['visible'])
            assert all(set(r)=={'id','title','companyName','workLocation','remaining','canSelect','selectionReason'} for r in first['items'])
            assert all(r['canSelect'] or r['selectionReason'] for r in first['items'])
            assert read(client,path,{**params,'keyword':'目录岗位22'})['total']==1
            assert read(client,path,{**params,'keyword':'%'})['total']==0


def test_catalog_rejects_wrong_context_cross_school_and_staff(catalog):
    foreign=seed_flow()
    with login(catalog,'STUDENT') as student,login(catalog,'INTERN_MENTOR') as staff,login(foreign,'STUDENT') as outsider:
        for prefix in ['/api/v1/mobile/internship','/api/v1/portal/internship']:
            path=prefix+'/context/applications/positions';params={'batchId':catalog['batchId'],'internshipId':catalog['recordId']}
            assert staff.get(path,params=params).status_code in (400,401,403)
            assert outsider.get(path,params=params).status_code in (400,403,404,409)
            assert student.get(path,params={**params,'internshipId':foreign['recordId']}).status_code in (400,403,404,409)
            assert student.get(path,params={**params,'internshipId':catalog['otherRecordId']}).status_code in (400,403,404,409)
            assert student.get(path,params={'batchId':catalog['batchId']}).status_code==422
            assert student.get(path,params={**params,'pageSize':51}).status_code==422
