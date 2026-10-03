"""Real account/API/file tests; each test gets an isolated synthetic school."""
import io
from datetime import datetime
from uuid import uuid4
import pytest
from PIL import Image
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipRecord, InternshipBatch, StudentProfile, StudentAccountLink, User, UserRole, Role
from app.models.file import FileObject, FileBinding
from test_yiyang_plan_export_options_mysql import seed_workspace, login, PASSWORD

PORTAL = '/api/v1/portal/internship'
STAFF = '/api/v1/internship'

def seed_flow():
    data = seed_workspace(2)
    with get_sessionmaker()() as db:
        record = db.scalar(select(InternshipRecord).where(InternshipRecord.batch_id == int(data['batches'][0]['id'])))
        student = db.get(StudentProfile, record.student_id)
        record.status = 'ONBOARD'
        record.eligibility_status = 'QUALIFIED'
        record.intern_start_date = datetime(2026, 9, 1)
        record.intern_end_date = datetime(2026, 12, 30)
        record.enterprise_name, record.position_name = '合成测试企业', '实习岗位'
        batch = db.get(InternshipBatch, record.batch_id)
        batch.end_date = datetime(2026, 12, 30)
        db.add(StudentAccountLink(tenant_id=int(data['tenantId']),student_id=student.id,
            user_id=data['users']['STUDENT'],link_status='ACTIVE',source='IDENTITY_IMPORT',
            bound_student_no=student.student_no,bound_login_name='student'))
        db.commit()
        data['recordId'], data['studentId'] = str(record.id), str(student.id)
        data['batchId'] = str(batch.id)
    return data

@pytest.fixture
def flow():
    import os
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('requires explicit isolated MySQL opt-in')
    return seed_flow()

def png_bytes():
    output = io.BytesIO()
    Image.new('RGB',(160,100),(235,242,250)).save(output,format='PNG')
    return output.getvalue()

def upload(client, data=None, name='policy.png', mime='image/png', biz='INTERNSHIP_INSURANCE_POLICY'):
    response=client.post('/api/v1/files',params={'bizType':biz},files={'file':(name,data or png_bytes(),mime)})
    assert response.status_code==200 and response.json()['code']==0,response.text
    result=response.json()['data']
    assert result['readyForBusiness'] is True
    assert 'fileKey' not in result and 'storagePath' not in result
    return result

def context(flow):
    return {'batchId':flow['batchId'],'internshipId':flow['recordId']}

def insurance_body(flow,file_id,version=0):
    return {**context(flow),'policyNo':'POL-'+uuid4().hex[:12],'insurerName':'测试保险公司',
            'coverageType':'实习责任保险','effectiveDate':'2026-09-01','expiryDate':'2026-12-31',
            'fileId':file_id,'expectedVersion':version}

def test_student_file_upload_is_private_real_bytes_and_not_claimed_business(flow):
    with login(flow,'STUDENT') as client:
        meta=upload(client)
        result=client.get('/api/v1/files/download/'+meta['fileId'])
        assert result.status_code==200 and result.content==png_bytes()
    with get_sessionmaker()() as db:
        row=db.get(FileObject,int(meta['fileId']))
        assert row.biz_type=='TEMP_PRIVATE' and row.biz_id is None
        assert row.upload_source=='USER' and row.owner_user_id==flow['users']['STUDENT']
        assert row.visibility=='PRIVATE'

def test_insurance_submission_rejection_resubmission_and_approval(flow):
    with login(flow,'STUDENT') as student, login(flow) as school:
        first=upload(student)
        response=student.post(PORTAL+'/insurance',json=insurance_body(flow,first['fileId']))
        assert response.status_code==200 and response.json()['code']==0,response.text
        policy=response.json()['data']
        rejected=school.post(f"{STAFF}/insurances/{policy['id']}/verify",json={
            'action':'REJECT','comment':'请补充清晰的保险凭证','expectedVersion':policy['version']})
        assert rejected.json()['code']==0,rejected.text
        read=student.get(PORTAL+'/insurance',params=context(flow)).json()['data']
        assert read['status']=='REJECTED'
        second=upload(student,name='policy-corrected.png')
        response=student.post(PORTAL+'/insurance',json=insurance_body(flow,second['fileId'],read['version']))
        assert response.json()['code']==0,response.text
        latest=response.json()['data']
        approved=school.post(f"{STAFF}/insurances/{policy['id']}/verify",json={
            'action':'APPROVE','comment':'保险凭证核验通过','expectedVersion':latest['version']})
        assert approved.json()['code']==0,approved.text
        assert student.get(PORTAL+'/insurance',params=context(flow)).json()['data']['status']=='VERIFIED'


def test_first_insurance_file_is_bound_and_school_can_read_only_after_submission(flow):
    with login(flow,'STUDENT') as student, login(flow) as school:
        meta=upload(student)
        assert school.get('/api/v1/files/download/'+meta['fileId']).status_code==404
        response=student.post(PORTAL+'/insurance',json=insurance_body(flow,meta['fileId']))
        assert response.json()['code']==0,response.text
        policy=response.json()['data']
        with get_sessionmaker()() as db:
            bindings=db.scalars(select(FileBinding).where(FileBinding.file_id==int(meta['fileId']))).all()
            assert len(bindings)==1
            assert bindings[0].biz_type=='INTERNSHIP_INSURANCE' and bindings[0].biz_id==policy['id']
            assert bindings[0].student_id==int(flow['studentId'])
        response=school.get('/api/v1/files/download/'+meta['fileId'])
        assert response.status_code==200 and response.content==png_bytes()

@pytest.mark.parametrize('kind',['WEEKLY','DAILY','MONTHLY','SUMMARY'])
def test_report_attachment_return_resubmit_and_review_remain_version_bound(flow,kind):
    from app.models import InternshipReportVersion, InternshipReportReview
    route='/context/weekly-reports' if kind=='WEEKLY' else '/context/reports'
    with login(flow,'STUDENT') as student, login(flow,'INTERN_MENTOR') as teacher:
        attachment=upload(student,biz='INTERNSHIP_REPORT')
        base={**context(flow),'expectedVersion':0,'attachments':[attachment['fileId']]}
        if kind=='WEEKLY':
            base.update(weekNo=1,workContent='完成真实岗位实习任务与安全要求。'*5,harvestContent='学习工作流程并记录成果。'*4,planContent='继续巩固岗位能力。')
        else:
            base.update(reportType=kind,periodKey='2026-09-30' if kind=='DAILY' else '2026-09',content='真实岗位实习工作内容与成果记录。'*30)
        response=student.post(PORTAL+route,json=base)
        assert response.status_code==200 and response.json()['code']==0,response.text
        report=response.json()['data']
        endpoint=STAFF+('/reports/' if kind=='WEEKLY' else '/process-reports/')+report['id']+'/review'
        read=teacher.get('/api/v1/files/download/'+attachment['fileId'])
        assert read.status_code==200 and read.content==png_bytes(),read.text
        returned=teacher.post(endpoint,json={'action':'RETURN','comment':'请补充真实岗位成果与图片说明','expectedVersion':report['version'],'batchId':flow['batchId']})
        assert returned.json()['code']==0,returned.text
        listed=student.get(PORTAL+route,params=context(flow)).json()['data']['items']
        row=next(x for x in listed if x['id']==report['id'])
        assert row['status']=='RETURNED'
        base['expectedVersion']=row['version']
        if kind=='WEEKLY': base['workContent']+='已根据指导意见完善工作成果。'
        else: base['content']+='已根据指导意见完善工作成果。'
        updated=student.post(PORTAL+route,json=base)
        assert updated.json()['code']==0,updated.text
        current=updated.json()['data']
        approved=teacher.post(endpoint,json={'action':'APPROVE','comment':'修改后符合要求','expectedVersion':current['version'],
            'batchId':flow['batchId'],'ratingLevel':4,**({'summaryScore':88} if kind=='SUMMARY' else {})})
        assert approved.json()['code']==0,approved.text
        with get_sessionmaker()() as db:
            versions=db.scalars(select(InternshipReportVersion).where(InternshipReportVersion.tenant_id==int(flow['tenantId']),
                InternshipReportVersion.report_id==int(report['id']),InternshipReportVersion.report_kind=='WEEKLY' if kind=='WEEKLY' else InternshipReportVersion.report_kind=='PROCESS').order_by(InternshipReportVersion.version_no)).all()
            assert [x.version_no for x in versions]==[1,2]
            reviews=db.scalars(select(InternshipReportReview).where(InternshipReportReview.report_version_id.in_([x.id for x in versions]))).all()
            assert {x.action for x in reviews}=={'RETURN','APPROVE'}
        final=student.get(PORTAL+route,params=context(flow)).json()['data']['items']
        assert next(x for x in final if x['id']==report['id'])['status']=='APPROVED'


def test_private_file_cannot_be_stolen_by_same_school_account_or_foreign_school(flow):
    from app.models import InternshipInsurance
    foreign=seed_flow()
    with login(flow,'STUDENT') as student, login(flow) as school, login(foreign,'STUDENT') as outsider:
        school_file=upload(school)
        for client in (student,outsider):
            assert client.get('/api/v1/files/'+school_file['fileId']).status_code==404
            assert client.get('/api/v1/files/download/'+school_file['fileId']).status_code==404
        denied=student.post(PORTAL+'/insurance',json=insurance_body(flow,school_file['fileId']))
        assert denied.json()['code']!=0
        with get_sessionmaker()() as db:
            assert db.scalar(select(InternshipInsurance).where(InternshipInsurance.internship_id==int(flow['recordId']))) is None
            assert db.get(FileObject,int(school_file['fileId'])).biz_type=='TEMP_PRIVATE'

@pytest.mark.parametrize('name,data,mime',[('bad.png',b'not an image','image/png'),('script.html',b'<script>bad</script>','text/html'),('bad.doc',b'fake document','application/msword'),('bad.mp4',b'fake video','video/mp4')])
def test_invalid_file_content_never_creates_available_evidence(flow,name,data,mime):
    with login(flow,'STUDENT') as student:
        response=student.post('/api/v1/files',files={'file':(name,data,mime)})
        assert response.status_code==400,response.text
    with get_sessionmaker()() as db:
        assert not db.scalars(select(FileObject).where(FileObject.tenant_id==int(flow['tenantId']))).all()


def test_required_scan_is_quarantined_and_not_usable_or_downloadable(flow,monkeypatch):
    monkeypatch.setenv('FILE_SCAN_REQUIRED','true')
    with login(flow,'STUDENT') as student:
        response=student.post('/api/v1/files',files={'file':('report.txt',b'Real synthetic training notes','text/plain')})
        assert response.json()['code']==0,response.text
        meta=response.json()['data']
        assert meta['status']=='QUARANTINED' and meta['scanStatus']=='PENDING' and not meta['readyForBusiness']
        assert student.get('/api/v1/files/download/'+meta['fileId']).status_code==404
        assert student.post(PORTAL+'/insurance',json=insurance_body(flow,meta['fileId'])).json()['code']!=0


def test_unbound_old_student_session_cannot_read_own_uploaded_file(flow):
    with login(flow,'STUDENT') as student:
        meta=upload(student)
        with get_sessionmaker()() as db:
            link=db.scalar(select(StudentAccountLink).where(StudentAccountLink.tenant_id==int(flow['tenantId']),StudentAccountLink.user_id==flow['users']['STUDENT']))
            link.link_status='REVOKED'; db.commit()
        assert student.get('/api/v1/files/'+meta['fileId']).status_code==403

@pytest.mark.parametrize('kind',['WEEKLY','MONTHLY'])
def test_concurrent_review_yields_one_receipt_without_500(flow,kind):
    from concurrent.futures import ThreadPoolExecutor
    route='/context/weekly-reports' if kind=='WEEKLY' else '/context/reports'
    with login(flow,'STUDENT') as student, login(flow,'INTERN_MENTOR') as teacher1, login(flow,'INTERN_MENTOR') as teacher2:
        body={**context(flow),'expectedVersion':0}
        if kind=='WEEKLY': body.update(weekNo=1,workContent='岗位工作总结与成果。'*8,harvestContent='学习收获。'*8)
        else: body.update(reportType='MONTHLY',periodKey='2026-10',content='岗位工作总结与成果。'*20)
        created=student.post(PORTAL+route,json=body); assert created.json()['code']==0,created.text
        row=created.json()['data']; endpoint=STAFF+('/reports/' if kind=='WEEKLY' else '/process-reports/')+row['id']+'/review'
        payload={'action':'APPROVE','comment':'审核符合岗位要求','ratingLevel':4,'expectedVersion':row['version'],'batchId':flow['batchId']}
        with ThreadPoolExecutor(max_workers=2) as pool:
            calls=[pool.submit(c.post,endpoint,json=payload) for c in (teacher1,teacher2)]
            results=[x.result(timeout=20) for x in calls]
        assert sorted(x.json()['code']==0 for x in results)==[False,True]
        assert all(x.status_code<500 for x in results)


def test_invalid_batch_review_cannot_change_report(flow):
    with login(flow,'STUDENT') as student, login(flow,'INTERN_MENTOR') as teacher:
        response=student.post(PORTAL+'/context/reports',json={**context(flow),'expectedVersion':0,'reportType':'MONTHLY',
            'periodKey':'2026-10','content':'真实岗位实习记录。'*30})
        row=response.json()['data']
        bad=teacher.post(STAFF+'/process-reports/'+row['id']+'/review',json={'action':'RETURN','comment':'需要完善过程记录',
            'expectedVersion':row['version'],'batchId':flow['batches'][1]['id']})
        assert bad.json()['code']!=0
        read=student.get(PORTAL+'/context/reports',params=context(flow)).json()['data']['items'][0]
        assert read['status']=='PENDING_REVIEW' and read['version']==row['version']


def test_simultaneous_insurance_submission_never_leaves_duplicates_or_500(flow):
    from concurrent.futures import ThreadPoolExecutor
    from app.models import InternshipInsurance
    with login(flow,'STUDENT') as one, login(flow,'STUDENT') as two:
        file=upload(one); body=insurance_body(flow,file['fileId'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=[future.result(timeout=20) for future in [pool.submit(c.post,PORTAL+'/insurance',json=body) for c in (one,two)]]
        assert all(r.status_code<500 for r in responses)
        assert any(r.json()['code']==0 for r in responses)
    with get_sessionmaker()() as db:
        assert len(db.scalars(select(InternshipInsurance).where(InternshipInsurance.internship_id==int(flow['recordId']))).all())==1
        assert len(db.scalars(select(FileBinding).where(FileBinding.file_id==int(file['fileId']))).all())==1


def test_tampered_storage_bytes_are_not_delivered(flow):
    from app.services.storage import get_backend
    with login(flow,'STUDENT') as student:
        file=upload(student)
        with get_sessionmaker()() as db:
            row=db.get(FileObject,int(file['fileId'])); path=get_backend().fetch_local(row.file_key)
        original=path.read_bytes()
        try:
            path.write_bytes(b'corrupted')
            denied=student.get('/api/v1/files/download/'+file['fileId'])
            assert denied.status_code==409 and denied.json()['bizCode']=='FILE_INTEGRITY_ERROR'
        finally: path.write_bytes(original)


def test_oversized_upload_never_persists_file(flow):
    with login(flow,'STUDENT') as student:
        result=student.post('/api/v1/files',files={'file':('large.png',b'x'*(20*1024*1024+1),'image/png')})
        assert result.status_code==413
    with get_sessionmaker()() as db:
        assert not db.scalars(select(FileObject).where(FileObject.tenant_id==int(flow['tenantId']))).all()


def test_audit_failure_rolls_back_upload_without_stray_bytes(flow,monkeypatch):
    from app.modules.internship.services import internship_audit_service
    from app.core.exceptions import AppException
    from app.services.storage import get_backend
    root=get_backend().root
    before={p for p in root.rglob('*') if p.is_file()}
    def failure(*args,**kwargs): raise AppException('AUDIT_UNAVAILABLE','审计服务不可用',http_status=503)
    monkeypatch.setattr(internship_audit_service,'add_audit',failure)
    with login(flow,'STUDENT') as student:
        result=student.post('/api/v1/files',files={'file':('receipt.png',png_bytes(),'image/png')})
        assert result.status_code==503
        assert not result.json().get('data')
    assert {p for p in root.rglob('*') if p.is_file()}==before
    with get_sessionmaker()() as db:
        assert not db.scalars(select(FileObject).where(FileObject.tenant_id==int(flow['tenantId']))).all()


def test_lost_commit_acknowledgement_does_not_delete_committed_upload(flow,monkeypatch):
    from sqlalchemy.orm import Session
    from app.core.exceptions import AppException
    original=Session.commit
    def lost_ack(db):
        original(db)
        raise AppException('COMMIT_ACK_UNCERTAIN','提交回执中断，请刷新核实',http_status=503)
    with login(flow,'STUDENT') as student:
        with monkeypatch.context() as patch:
            patch.setattr(Session,'commit',lost_ack)
            response=student.post('/api/v1/files',files={'file':('receipt.png',png_bytes(),'image/png')})
            assert response.status_code==503
        with get_sessionmaker()() as db:
            row=db.scalar(select(FileObject).where(FileObject.tenant_id==int(flow['tenantId'])))
            assert row is not None
            file_id=str(row.id)
        result=student.get('/api/v1/files/download/'+file_id)
        assert result.status_code==200 and result.content==png_bytes()
