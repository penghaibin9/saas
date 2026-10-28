"""Normal-role material submission/version tests in the explicitly isolated MySQL."""
import os
from contextlib import contextmanager
from uuid import uuid4
import pytest
from sqlalchemy import delete, select, func, event
from sqlalchemy.engine import make_url
from app.config import settings
from app.db.session import get_sessionmaker, get_engine
from app.models import InternshipMaterialSubmission, InternshipAuditTrail, InternshipRecord, StudentProfile
from app.models import User, UserRole, Role, StudentAccountLink
from app.models.file import FileObject, FileJob, FileVersion
from test_yiyang_write_flows_mysql import seed_flow, login, upload, context, png_bytes
from test_yiyang_write_flows_mysql import insurance_body

STAFF='/api/v1/internship'
MOBILE='/api/v1/mobile/internship/context/material-requirements'

@pytest.fixture
def flow():
    assert os.environ.get('GAP09_MYSQL_ACCEPTANCE')=='1'
    target=make_url(settings.DATABASE_URL)
    assert settings.APP_ENV=='test' and target.get_backend_name()=='mysql'
    allowed={('127.0.0.1',3318,'internship_pr275_acceptance_test_20261003'),
             ('127.0.0.1',3306,'internship_employment_test_ci')}
    assert (target.host,target.port,target.database) in allowed
    if target.port==3306:
        assert os.environ.get('GITHUB_ACTIONS')=='true'
    return seed_flow()

def data(response):
    assert response.status_code==200 and response.json()['code']==0,response.text
    return response.json()['data']

def requirement(flow, school, **options):
    req=data(school.post(STAFF+'/material-requirements',json={
        'batchId':flow['batchId'],'materialCode':'ACCEPTANCE_'+uuid4().hex[:8].upper(),
        'materialName':'合成企业接收函','isRequired':True,'minFiles':1,'maxFiles':2,'allowedExtensions':['png','pdf'],**options}))
    template=upload(school,biz='INTERNSHIP_MATERIAL_TEMPLATE')
    data(school.post(STAFF+'/material-requirements/'+req['id']+'/template',json={'fileId':template['fileId']}))
    data(school.post(STAFF+'/material-requirements/'+req['id']+'/publish'))
    return req

def submit(flow, student, req, file, version=0):
    return student.post(MOBILE+'/'+req['id']+'/submit',json={**context(flow),'fileIds':[file['fileId']],'expectedVersion':version,'comment':'合成材料办理，非真实学生数据'})

def test_pending_scan_cannot_submit_or_bind_custom_material(flow,monkeypatch):
    with login(flow) as school,login(flow,'STUDENT') as student:
        req=requirement(flow,school)
        monkeypatch.setenv('FILE_SCAN_REQUIRED','true')
        file=data(student.post('/api/v1/files',params={'bizType':'INTERNSHIP_CUSTOM_MATERIAL'},files={'file':('待扫描接收函.pdf',b'%PDF-1.4\n% synthetic material\n%%EOF\n','application/pdf')}))
        assert file['readyForBusiness'] is False and file['status']=='QUARANTINED'
        try:
            denied=submit(flow,student,req,file)
            assert denied.status_code!=200 or denied.json()['code']!=0
            assert student.get('/api/v1/files/download/'+file['fileId']).status_code==404
            with get_sessionmaker()() as db:
                assert db.scalar(select(func.count()).select_from(InternshipMaterialSubmission).where(InternshipMaterialSubmission.requirement_id==int(req['id'])))==0
        finally:
            # Only this test's unbound synthetic pending upload, never the retained daily database.
            with get_sessionmaker()() as db:
                db.execute(delete(FileJob).where(FileJob.file_id==int(file['fileId'])))
                db.execute(delete(FileObject).where(FileObject.id==int(file['fileId']),FileObject.tenant_id==int(flow['tenantId'])))
                db.commit()

def test_return_resubmit_same_material_preserves_history_and_rejects_stale_version(flow):
    with login(flow) as school,login(flow,'STUDENT') as student,login(flow,'INTERN_MENTOR') as teacher:
        req=requirement(flow,school)
        first_file=upload(student,biz='INTERNSHIP_CUSTOM_MATERIAL')
        assert teacher.get('/api/v1/files/'+first_file['fileId']).status_code==404
        first=data(submit(flow,student,req,first_file))
        queue=STAFF+'/material-requirements/'+req['id']+'/students'
        assert data(teacher.get(queue,params={'state':'PENDING_REVIEW'}))['items'][0]['submission']['id']==first['id']
        assert data(teacher.get('/api/v1/files/'+first_file['fileId']))['readyForBusiness'] is True
        assert teacher.get('/api/v1/files/download/'+first_file['fileId']).content==png_bytes()
        returned=data(teacher.post(STAFF+'/material-submissions/'+first['id']+'/review',json={'action':'RETURN','comment':'请补充清晰完整的企业接收函','expectedVersion':first['version']}))
        assert returned['status']=='RETURNED'
        secondFile=upload(student,name='补充接收函.png',biz='INTERNSHIP_CUSTOM_MATERIAL')
        for invalid in (None,True,'2'):
            body={**context(flow),'fileIds':[secondFile['fileId']]}
            if invalid is not None:
                body['expectedVersion']=invalid
            assert student.post(MOBILE+'/'+req['id']+'/submit',json=body).status_code==409
        stale=submit(flow,student,req,secondFile,version=first['version'])
        assert stale.status_code==409,stale.text
        second=data(submit(flow,student,req,secondFile,version=returned['version']))
        assert second['id']==first['id'] and second['files'][0]['versionNo']==2
        approved=data(teacher.post(STAFF+'/material-submissions/'+second['id']+'/review',json={'action':'APPROVE','comment':'接收函材料审核通过','expectedVersion':second['version']}))
        assert approved['status']=='APPROVED'
        assert data(teacher.get(queue,params={'state':'PENDING_REVIEW'}))['items']==[]
        assert data(teacher.get(queue,params={'state':'SUBMITTED'}))['items'][0]['submission']['status']=='APPROVED'
        reread=data(student.get(MOBILE,params=context(flow)))
        assert next(item for item in reread if item['id']==req['id'])['submission']['id']==first['id']
        with get_sessionmaker()() as db:
            old=db.get(FileVersion,int(first['files'][0]['fileVersionId']))
            current=db.get(FileVersion,int(second['files'][0]['fileVersionId']))
            assert old.version_no==1 and old.is_current is False
            old_object=db.get(FileObject,old.file_object_id)
            assert old.file_object_id==int(first_file['fileId'])
            assert old_object.sha256==first['files'][0]['sha256']
            assert current.version_no==2 and current.is_current is True and current.status=='APPROVED'
            actions=db.scalars(select(InternshipAuditTrail.action).where(InternshipAuditTrail.tenant_id==int(flow['tenantId']),InternshipAuditTrail.target_id==int(req['id']))).all()
            assert actions.count('MATERIAL_SUBMIT')==2 and actions.count('MATERIAL_RETURN')==1 and actions.count('MATERIAL_APPROVE')==1

def test_mobile_insurance_uses_explicit_context_and_same_authority_as_student_pc(flow):
    path='/api/v1/mobile/internship/insurance'
    with login(flow,'STUDENT') as student,login(flow,'INTERN_MENTOR') as teacher:
        assert data(student.get(path,params=context(flow)))['status']=='NOT_SUBMITTED'
        file=upload(student)
        policy=data(student.post(path,json=insurance_body(flow,file['fileId'])))
        assert data(student.get(path,params=context(flow)))['id']==policy['id']
        assert data(student.get('/api/v1/portal/internship/insurance',params=context(flow)))['id']==policy['id']
        wrong={**context(flow),'batchId':flow['batches'][1]['id']}
        assert student.get(path,params=wrong).status_code in (400,403,404,409)
        assert student.get(path).status_code==422
        assert teacher.get(path,params=context(flow)).status_code==403


@contextmanager
def recorded_sql():
    statements=[]
    engine=get_engine()
    def record(_connection,_cursor,statement,_parameters,_context,_many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    event.listen(engine,'before_cursor_execute',record)
    try:
        yield statements
    finally:
        event.remove(engine,'before_cursor_execute',record)


def seed_material_targets(flow,count=43):
    """Unsubmitted synthetic students; no approval or terminal-state shortcut."""
    with get_sessionmaker()() as db:
        original=db.get(InternshipRecord,int(flow['recordId']))
        targets=[]
        for index in range(count):
            profile=StudentProfile(tenant_id=int(flow['tenantId']),student_no='MAT'+uuid4().hex[:16],
                real_name=f'分页材料学生{index:02}',current_stage='INTERNSHIP',student_status='NORMAL',status='ACTIVE')
            db.add(profile);db.flush()
            row=InternshipRecord(tenant_id=int(flow['tenantId']),student_id=profile.id,batch_id=original.batch_id,
                advisor_user_id=original.advisor_user_id,status='READY',enterprise_name='合成材料企业')
            db.add(row);db.flush()
            targets.append((str(row.id),str(profile.id)))
        db.commit()
        return targets


def test_material_collection_filters_pages_and_coverage_in_database(flow):
    targets=seed_material_targets(flow)
    with login(flow) as school,login(flow,'INTERN_MENTOR') as teacher:
        req=requirement(flow,school)
        queue=STAFF+'/material-requirements/'+req['id']+'/students'
        with recorded_sql() as statements:
            first=data(teacher.get(queue,params={'page':1,'pageSize':20,'state':'MISSING'}))
            second=data(teacher.get(queue,params={'page':2,'pageSize':20,'state':'MISSING'}))
            last=data(teacher.get(queue,params={'page':3,'pageSize':20,'state':'MISSING'}))
        all_ids=[str(flow['recordId']),*[row[0] for row in targets]]
        actual=[row['internshipId'] for page in (first,second,last) for row in page['items']]
        assert actual==sorted(all_ids,key=int)
        assert len(first['items'])==20 and len(second['items'])==20 and len(last['items'])==4
        assert first['total']==second['total']==last['total']==44
        record_reads=[sql for sql in statements if sql.lstrip().upper().startswith('SELECT T_INTERNSHIP_RECORD.')]
        assert len(record_reads)==3 and all('LIMIT' in sql.upper() for sql in record_reads),'Each page must fetch only its database slice'
        assert data(teacher.get(queue,params={'keyword':'材料学生07'}))['total']==1
        assert data(teacher.get(queue,params={'keyword':'%'}))['items']==[]
        assert data(teacher.get(queue,params={'keyword':'_'}))['items']==[]
        with recorded_sql() as statements:
            summary=data(teacher.get(STAFF+'/material-requirements/'+req['id']+'/coverage'))
        assert summary['requiredStudents']==44 and summary['missingStudents']==44
        assert any('GROUP BY' in sql.upper() for sql in statements),'Coverage must aggregate in the database'
        assert not any(sql.lstrip().upper().startswith('SELECT T_INTERNSHIP_RECORD.') for sql in statements)


def test_material_audience_and_current_advisor_scope_match_counts(flow):
    targets=seed_material_targets(flow,4)
    with get_sessionmaker()() as db:
        outside=db.get(InternshipRecord,int(targets[-1][0]))
        outside.advisor_user_id=flow['users']['SCHOOL_ADMIN']
        db.commit()
    with login(flow) as school,login(flow,'INTERN_MENTOR') as teacher:
        chosen=[flow['studentId'],targets[0][1],targets[-1][1]]
        for kind in ('SELECTED_STUDENTS','FILTERED'):
            req=requirement(flow,school,audienceType=kind,audienceFilter={'studentIds':chosen})
            queue=STAFF+'/material-requirements/'+req['id']
            assert data(teacher.get(queue+'/students'))['total']==2
            assert data(teacher.get(queue+'/coverage'))['requiredStudents']==2
            assert data(school.get(queue+'/students'))['total']==3
            assert data(school.get(queue+'/coverage'))['requiredStudents']==3
        empty=requirement(flow,school,audienceType='FILTERED',audienceFilter={})
        assert data(school.get(STAFF+'/material-requirements/'+empty['id']+'/students'))['items']==[]
        assert data(school.get(STAFF+'/material-requirements/'+empty['id']+'/coverage'))['requiredStudents']==0


def test_material_page_loads_file_versions_in_one_query_for_normal_submissions(flow):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_yiyang_plan_export_options_mysql import PASSWORD
    targets=seed_material_targets(flow,5)
    names=[]
    with get_sessionmaker()() as db:
        role=db.scalar(select(Role).where(Role.tenant_id==int(flow['tenantId']),Role.role_code=='STUDENT'))
        original=db.get(User,flow['users']['STUDENT'])
        for _record_id,student_id in targets:
            profile=db.get(StudentProfile,int(student_id))
            name='material-'+uuid4().hex[:12]
            user=User(tenant_id=int(flow['tenantId']),login_name=name,real_name=profile.real_name,
                password_hash=original.password_hash,user_type='STUDENT',status='ACTIVE',
                credential_version=0,must_change_password=False)
            db.add(user);db.flush()
            db.add(UserRole(tenant_id=int(flow['tenantId']),user_id=user.id,role_id=role.id,status='ACTIVE'))
            db.add(StudentAccountLink(tenant_id=int(flow['tenantId']),student_id=profile.id,user_id=user.id,
                link_status='ACTIVE',source='IDENTITY_IMPORT',bound_student_no=profile.student_no,bound_login_name=name))
            names.append(name)
        db.commit()
    with login(flow) as school,login(flow,'INTERN_MENTOR') as teacher:
        req=requirement(flow,school)
        expected=[]
        for name,(record_id,_student_id) in zip(names,targets):
            with TestClient(app) as student:
                authenticated=student.post('/api/v1/auth/browser-login',json={
                    'tenantCode':flow['tenantCode'],'loginName':name,'password':PASSWORD,'clientType':'STUDENT_PC'},
                    headers={'X-Browser-Session-Id':'material-'+uuid4().hex})
                assert authenticated.status_code==200
                student.headers['Authorization']='Bearer '+authenticated.json()['data']['accessToken']
                file=upload(student,name='分页合成接收函.png',biz='INTERNSHIP_CUSTOM_MATERIAL')
                result=data(student.post(MOBILE+'/'+req['id']+'/submit',json={
                    'batchId':flow['batchId'],'internshipId':record_id,
                    'fileIds':[file['fileId']],'expectedVersion':0}))
                expected.append((result['id'],file['fileId']))
        with recorded_sql() as statements:
            rows=data(teacher.get(STAFF+'/material-requirements/'+req['id']+'/students',params={'state':'PENDING_REVIEW'}))
        assert rows['total']==5
        assert [(row['submission']['id'],row['submission']['files'][0]['fileId']) for row in rows['items']]==expected
        file_reads=[sql for sql in statements if 'FROM T_INTERNSHIP_MATERIAL_SUBMISSION_FILE' in sql.upper()]
        assert len(file_reads)==1,'Load only the current page file metadata in one query, not one query per student'
        summary=data(teacher.get(STAFF+'/material-requirements/'+req['id']+'/coverage'))
        assert summary['requiredStudents']==6 and summary['pendingReviewStudents']==5 and summary['missingStudents']==1


def test_unsubmitted_draft_is_in_missing_list_and_coverage(flow):
    with login(flow) as school,login(flow,'INTERN_MENTOR') as teacher:
        req=requirement(flow,school)
        with get_sessionmaker()() as db:
            db.add(InternshipMaterialSubmission(tenant_id=int(flow['tenantId']),requirement_id=int(req['id']),
                internship_id=int(flow['recordId']),student_id=int(flow['studentId']),batch_id=int(flow['batchId']),status='DRAFT'))
            db.commit()
        queue=STAFF+'/material-requirements/'+req['id']
        summary=data(teacher.get(queue+'/coverage'))
        missing=data(teacher.get(queue+'/students',params={'state':'MISSING'}))
        assert summary['missingStudents']==1 and missing['total']==1
        assert missing['items'][0]['submission']['status']=='DRAFT'
        assert data(teacher.get(queue+'/students',params={'state':'PENDING_REVIEW'}))['items']==[]


@pytest.mark.parametrize('invalid',[None,True,'1','invalid-version'])
def test_material_review_requires_an_actual_current_integer_version(flow,invalid):
    with login(flow) as school,login(flow,'STUDENT') as student,login(flow,'INTERN_MENTOR') as teacher:
        req=requirement(flow,school)
        file=upload(student,biz='INTERNSHIP_CUSTOM_MATERIAL')
        submitted=data(submit(flow,student,req,file))
        body={'action':'APPROVE','comment':'合成版本校验'}
        if invalid is not None:
            body['expectedVersion']=invalid
        response=teacher.post(STAFF+'/material-submissions/'+submitted['id']+'/review',json=body)
        assert response.status_code==409
        current=next(row for row in data(student.get(MOBILE,params=context(flow))) if row['id']==req['id'])['submission']
        assert current['status']=='SUBMITTED' and current['version']==submitted['version']
