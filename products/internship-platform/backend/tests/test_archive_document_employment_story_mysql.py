"""Ended synthetic placement prerequisites; target documents/employment/archive use normal commands."""
from datetime import datetime,date
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
import json,zipfile
import pytest
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import (Tenant,User,StudentProfile,StudentContact,College,Major,SchoolClass,EmpCompany,
    InternshipRecord,InternshipBatch,InternshipProcessReport,InternshipReportVersion,InternshipReportReview,
    InternshipPayrollStatement,InternshipPayrollVersion,InternshipRotation,InternshipRotationProject)
from app.core.field_crypto import encrypt_sensitive
from test_evaluation_score_story_mysql import seed_score_story,login,enterprise_login,complete_evaluations,result,context
from test_internship_employment_mysql import fields,decide

ROOT='/api/v1/internship'
MOBILE='/api/v1/mobile/internship/employment'
TEACHER='/api/v1/teacher-mobile/internship/employment'


@pytest.mark.parametrize('stamp,expected',[('2026-10-18T23:52:50','2026-10-19 07:52'),('2026-10-18T23:52:50Z','2026-10-19 07:52'),('2026-10-19T07:52:50+08:00','2026-10-19 07:52'),(None,'')])
def test_formal_pdf_school_time_keeps_utc_source_unchanged(monkeypatch,stamp,expected):
    from zoneinfo import ZoneInfo
    from app.modules.internship.services import internship_formal_document_service as service
    monkeypatch.setattr(service,'tenant_tz',lambda:ZoneInfo('Asia/Shanghai'))
    facts={'publishedAt':stamp};assert service._school_time(facts['publishedAt'])==expected;assert facts['publishedAt']==stamp


@pytest.mark.parametrize('end_day',[18,19,20])
def test_certificate_uses_school_calendar_date_at_utc_boundary(monkeypatch,end_day):
    from app.modules.internship.services import internship_formal_document_service as service
    from app.modules.internship.services import internship_student_age
    from app.core.exceptions import AppException
    class Clock(datetime):
        @classmethod
        def utcnow(cls):return cls(2026,10,18,23,50)
    monkeypatch.setattr(service,'datetime',Clock)
    monkeypatch.setattr(internship_student_age,'policy_today',lambda:date(2026,10,19))
    monkeypatch.setattr(service,'_attendance_facts',lambda *args:{'attendanceDays':1})
    record=SimpleNamespace(status='ASSESSING',enterprise_name='虚构企业',position_name='虚构新岗',intern_start_date=datetime(2026,10,18),intern_end_date=datetime(2026,10,end_day))
    if end_day<=19:
        assert service._certificate_fact(None,record)['attendanceDays']==1
    else:
        with pytest.raises(AppException,match='实习尚未结束'):service._certificate_fact(None,record)
    assert record.intern_end_date==datetime(2026,10,end_day)

def seed_archive_story():
    story=seed_score_story();tid=int(story['tenantId'])
    with get_sessionmaker()() as db:
        db.get(Tenant,tid).school_name='文书归档就业合成学校'
        batch=db.get(InternshipBatch,int(story['batchId']));batch.batch_name='2026文书归档就业验收批次';batch.end_date=datetime(2026,10,13)
        record=db.get(InternshipRecord,int(story['recordId']));record.intern_end_date=datetime(2026,10,13)
        student=db.get(StudentProfile,int(story['studentId']));student.real_name='文档归档验收学生';student.gender='FEMALE'
        college=College(tenant_id=tid,college_name='合成信息工程学院');db.add(college);db.flush()
        major=Major(tenant_id=tid,college_id=college.id,major_name='合成软件技术');db.add(major);db.flush()
        group=SchoolClass(tenant_id=tid,major_id=major.id,class_name='合成软件一班',grade='2024');db.add(group);db.flush()
        student.class_id=group.id;student.grade='2024';student.enroll_date=datetime(2024,9,1)
        db.add(StudentContact(tenant_id=tid,student_id=student.id,contact_type='PHONE',contact_value_encrypted=encrypt_sensitive('13900000001','phone'),is_primary=True))
        db.get(User,story['users']['INTERN_MENTOR']).phone_encrypted=encrypt_sensitive('13900000002','phone')
        db.get(EmpCompany,int(story['companyId'])).credit_code='91430100MA4L0ABC1D'
        summary=db.scalar(select(InternshipProcessReport).where(InternshipProcessReport.internship_id==record.id,InternshipProcessReport.report_type=='SUMMARY'))
        for revision,action,content in [(1,'RETURN','历史总结原文，待补充具体成果。'),(2,'APPROVE','完成软件测试与问题复盘，形成测试记录并改进协作方法。')]:
            snap=InternshipReportVersion(tenant_id=tid,report_kind='PROCESS',report_id=summary.id,version_no=revision,
                internship_id=record.id,student_id=student.id,report_type='SUMMARY',period_key=summary.period_key,
                word_count=len(content),content_json={'content':content},attachment_file_ids_json=[],submitted_at=datetime(2026,10,12,revision))
            db.add(snap);db.flush()
            db.add(InternshipReportReview(tenant_id=tid,report_kind='PROCESS',report_id=summary.id,report_version_id=snap.id,
                action=action,rating_level=4,summary_score=90 if action=='APPROVE' else None,comment='历史合成批阅事实',
                reviewer_user_id=str(story['users']['INTERN_MENTOR']),reviewer_name='合成指导教师',reviewed_at=datetime(2026,10,12,revision+1)))
        summary.content=content;summary.word_count=len(content);summary.version=2
        payroll=InternshipPayrollStatement(tenant_id=tid,internship_id=record.id,student_id=student.id,batch_id=batch.id,pay_month='2026-09',revision_count=2)
        db.add(payroll);db.flush()
        for revision,amount,state in [(1,'1200.00','SUPERSEDED'),(2,'1234.56','APPROVED')]:
            pay=InternshipPayrollVersion(tenant_id=tid,statement_id=payroll.id,revision_no=revision,actual_amount=amount,
                status=state,is_current=revision==2,review_comment='历史合成工资核验')
            db.add(pay);db.flush()
        payroll.current_version_id=pay.id
        rotation=InternshipRotation(tenant_id=tid,internship_id=record.id,student_id=student.id,batch_id=batch.id,
            rotation_seq=1,department_name='合成质量部',mentor_name='合成指导教师',start_date=date(2026,9,1),end_date=date(2026,10,13),status='COMPLETED')
        db.add(rotation);db.flush()
        db.add(InternshipRotationProject(tenant_id=tid,rotation_id=rotation.id,project_seq=1,project_name='软件测试实训',status='COMPLETED'))
        db.commit()
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student,enterprise_login(story) as enterprise:
        complete_evaluations(story,school,teacher,student,enterprise)
        score=result(teacher.post(ROOT+'/scores/compute',json={'internshipId':story['recordId']}))
        review=result(school.post(ROOT+'/scores/'+score['id']+'/review',json={'expectedVersion':score['version']}))
        result(school.post(ROOT+'/scores/'+score['id']+'/publish',json={'expectedVersion':review['version']}))
        story['scoreId']=score['id']
    return story

@pytest.fixture
def story(record_property):
    value=seed_archive_story();record_property('tenantId',value['tenantId']);return value

def documents(school,story):
    return [result(school.post(ROOT+'/formal-documents/generate',json={'internshipId':story['recordId'],'documentType':kind}))
        for kind in ['ENTERPRISE_EVALUATION','INTERNSHIP_CERTIFICATE','FINAL_ASSESSMENT','SUMMARY_REPORT']]

def archive(school,story):
    check=result(school.post(ROOT+'/archive/'+story['recordId']+'/preflight'));assert check['canArchive'],check
    return result(school.post(ROOT+'/archive/'+story['recordId']+'/archive',json={
        'expectedVersion':check['version'] if check['version'] is not None else check['recordVersion'],
        'recordExpectedVersion':check['recordVersion']}))


def test_frozen_archive_rejects_rotation_score_rewrite_and_preserves_version(story):
    with get_sessionmaker()() as db:
        row=db.scalar(select(InternshipRotation).where(InternshipRotation.tenant_id==int(story['tenantId']),InternshipRotation.internship_id==int(story['recordId'])))
        row.student_self_evaluation='纯虚构历史轮岗自评';row.student_self_rating=4;db.commit();rotation_id=str(row.id);version=row.version
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher:
        archive(school,story)
        response=teacher.post('/api/v1/mobile/teacher/internship/context/rotations/'+rotation_id+'/evaluate',json={
            'batchId':story['batchId'],'expectedVersion':version,'theoryScore':80,'skillScore':81,'mentorScore':82,'comment':'纯虚构归档冻结反向核对'})
        assert response.status_code in (400,409) and '已归档' in response.json()['message']
    with get_sessionmaker()() as db:assert db.get(InternshipRotation,int(rotation_id)).version==version

def test_complete_frozen_package_has_documents_history_payroll_rotation_and_employment(story):
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student:
        from test_yiyang_write_flows_mysql import upload,png_bytes
        photo=upload(school,biz='INTERNSHIP_REPORT')
        with get_sessionmaker()() as db:
            report=db.scalar(select(InternshipReportVersion).where(InternshipReportVersion.internship_id==int(story['recordId'])).order_by(InternshipReportVersion.id))
            report.attachment_file_ids_json=[photo['fileId']]
            statement=db.scalar(select(InternshipPayrollStatement).where(InternshipPayrollStatement.internship_id==int(story['recordId'])))
            db.get(InternshipPayrollVersion,statement.current_version_id).evidence_file_id=int(photo['fileId'])
            db.commit()
        docs=documents(school,story)
        employment=result(student.post(MOBILE,json={**context(story),'registrationMode':'EMPLOYMENT','expectedVersion':0,'fields':fields()}))
        result(decide(teacher,employment,'APPROVE'))
        archived=archive(school,story)
        package=result(school.post(ROOT+'/archive/'+story['recordId']+'/package'))
        raw=school.get(ROOT+'/archive-packages/'+package['packageId']+'/download');assert raw.status_code==200
        assert sha256(raw.content).hexdigest()==package['sha256']
        with zipfile.ZipFile(BytesIO(raw.content)) as z:
            manifest=json.loads(z.read('manifest.json'))
            assert manifest['internshipId']==story['recordId']
            for item in manifest['items']:
                assert sha256(z.read(item['archivePath'])).hexdigest()==item['sha256']
            frozen=next(json.loads(z.read(x['archivePath'])) for x in manifest['items'] if x['materialCode'].startswith('ARCHIVE_STATE_SNAPSHOT:'))
            data=frozen['businessEvidence']['datasets']
            assert [x['version_no'] for x in data['report-versions']]==[1,2]
            assert [x['action'] for x in data['report-reviews']]==['RETURN','APPROVE']
            assert [x['actual_amount'] for x in data['payroll-versions']]==[1200,1234.56]
            assert data['rotations'][0]['department_name']=='合成质量部' and len(data['rotation-projects'])==1
            assert data['employment'][0]['status']=='APPROVED' and len(data['employment-submissions'])==1
            declaration=frozen['businessEvidence']['employmentRegistration']
            assert declaration['id']==employment['id'] and len(declaration['current']['fields'])==23
            assert declaration['current']['fields']['companyName']=='合成就业测试企业'
            assert declaration['current']['fields']['studentPhone']=='已隐藏，请说明核验用途后查看'
            assert declaration['sensitiveVisible'] is False
            assert len(data['formal-documents'])==4
            assert frozen['finalScoreFreezeHash']==archived['finalScoreFreezeHash']
            assert '13900000001' not in json.dumps(frozen,ensure_ascii=False)
            assert not any('encrypted' in x for x in data['employment-submissions'][0])
            pdfs=[z.read(x['archivePath']) for x in manifest['items'] if x['materialCode'].startswith('FORMAL_DOCUMENT:')]
            assert len(pdfs)==4 and all(x.startswith(b'%PDF') for x in pdfs)
            retained=[x for x in manifest['items'] if x['fileObjectId']==photo['fileId']]
            assert len(retained)==2 and all(z.read(x['archivePath'])==png_bytes() for x in retained)
        assert result(school.post(ROOT+'/archive-packages/'+package['packageId']+'/restore-check'))['restoreReady']
        transition=result(school.get(ROOT+'/archive/'+story['recordId']+'/employment-transition'))
        assert transition['employmentRecordId']==employment['id'] and transition['employmentGatewayStatus']=='SCHOOL_VERIFIED'

def test_documents_owner_access_and_archive_permission_remain_separate(story):
    other=seed_score_story()
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student,login(other) as foreign:
        doc=documents(school,story)[0]
        assert teacher.get(ROOT+'/formal-documents/'+doc['id']+'/download').status_code==200
        assert foreign.get(ROOT+'/formal-documents/'+doc['id']+'/download').status_code in (403,404)
        owned=student.get('/api/v1/portal/internship/context/formal-documents/'+doc['id']+'/pdf',params=context(story))
        assert owned.status_code==200 and owned.json()['code']==0
        archive(school,story)
        for actor,path,body in [(school,ROOT+'/formal-documents/generate',{'internshipId':story['recordId'],'documentType':'ENTERPRISE_EVALUATION'}),
            (student,'/api/v1/portal/internship/context/formal-documents/generate',{**context(story),'documentType':'ENTERPRISE_EVALUATION'})]:
            denied=actor.post(path,json=body)
            assert denied.status_code==409 and '已冻结' in denied.json()['message']
        assert teacher.get(ROOT+'/formal-documents/'+doc['id']+'/download').status_code==200
        package=result(school.post(ROOT+'/archive/'+story['recordId']+'/package'))
        for actor in [teacher,student,foreign]:
            assert actor.get(ROOT+'/archive-packages/'+package['packageId']+'/download').status_code in (403,404)
            assert actor.get('/api/v1/files/download/'+package['fileId']).status_code==404

def test_child_queries_and_current_materials_exclude_another_placement_for_same_student(story):
    from app.core.context import set_tenant
    from app.models.file import FileAsset,FileVersion,FileBinding
    from app.modules.internship.services import internship_evidence_package_service as evidence,internship_material_center_service as core
    from app.models import InternshipArchive,InternshipVisit
    assert 'material_snapshot' not in evidence._safe_row(InternshipArchive(material_snapshot={'oldSnapshot':{'nested':'derived'}}))
    location=evidence._safe_row(InternshipVisit(location_encrypted='synthetic-encrypted-location'))
    assert location['has_location'] is True and 'location_encrypted' not in location
    with get_sessionmaker()() as db:
        tid=int(story['tenantId']);original=db.get(InternshipRecord,int(story['recordId']))
        batch=InternshipBatch(tenant_id=tid,batch_no='OTHER-'+story['recordId'],batch_name='另一实习批次',status='RUNNING')
        db.add(batch);db.flush()
        sibling=InternshipRecord(tenant_id=tid,student_id=original.student_id,batch_id=batch.id,status='ONBOARD')
        db.add(sibling);db.flush()
        unrelated=InternshipPayrollStatement(tenant_id=tid,internship_id=sibling.id,student_id=sibling.student_id,batch_id=sibling.batch_id,pay_month='2026-08')
        db.add(unrelated);db.flush()
        pay=InternshipPayrollVersion(tenant_id=tid,statement_id=unrelated.id,revision_no=1,actual_amount='9999.99',status='APPROVED')
        db.add(pay);db.commit()
        set_tenant({'tenantId':str(tid)})
        rows=evidence._query_evidence(db,'InternshipPayrollVersion',original.id)
        assert pay.id not in [x.id for x in rows] and len(rows)==2
    with login(story) as school:
        documents(school,story)
        result(school.post(ROOT+'/material-center/'+story['recordId']+'/sync'))
    with get_sessionmaker()() as db:
        set_tenant({'tenantId':str(tid)})
        original=db.get(InternshipRecord,int(story['recordId']))
        rows=core._current_rows(db,original);assert rows
        for _,asset,_,_ in rows:
            asset.owner_id=str(sibling.id)
        db.flush()
        assert core._current_rows(db,original)==[]

def test_invalidated_historical_attachment_cannot_be_rebound_as_new_archive_material(story):
    from test_yiyang_write_flows_mysql import upload
    from app.models.file import FileVersion
    with login(story) as school:
        photo=upload(school,biz='INTERNSHIP_REPORT')
        with get_sessionmaker()() as db:
            report=db.scalar(select(InternshipReportVersion).where(InternshipReportVersion.internship_id==int(story['recordId'])).order_by(InternshipReportVersion.id))
            report.attachment_file_ids_json=[photo['fileId']];db.commit()
        result(school.post(ROOT+'/material-center/'+story['recordId']+'/sync'))
        with get_sessionmaker()() as db:
            version=db.scalar(select(FileVersion).where(FileVersion.file_object_id==int(photo['fileId'])))
            version.status='INVALIDATED';db.commit()
        blocked=school.post(ROOT+'/material-center/'+story['recordId']+'/sync')
        assert blocked.json()['bizCode']=='DATA_CONFLICT' and '历史附件' in blocked.json()['message']

def test_employment_after_archive_is_independent_and_requires_open_batch_and_valid_frozen_score(story):
    from app.models import InternshipArchive,InternshipFinalScore
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student:
        documents(school,story);archive(school,story)
        package=result(school.post(ROOT+'/archive/'+story['recordId']+'/package'))
        before=school.get(ROOT+'/archive-packages/'+package['packageId']+'/download').content
        assert result(student.get(MOBILE,params=context(story)))['canSubmit'] is True
        payload={**context(story),'registrationMode':'EMPLOYMENT','expectedVersion':0,'fields':fields()}
        submitted=result(student.post(MOBILE,json=payload));verified=result(decide(teacher,submitted,'APPROVE'))
        assert result(school.get(ROOT+'/archive/'+story['recordId']+'/employment-transition'))['employmentRecordId']==submitted['id']
        old=result(student.get(MOBILE,params=context(story)))['registration']['current']
        correction=result(student.post(MOBILE,json={**payload,'expectedVersion':verified['version'],
            'fields':fields(positionName='归档后更正岗位',salary='4200'),'correctionReason':'合成核验后更正岗位与薪酬'}))
        assert correction['history'][1]==old and correction['current']['review'] is None
        assert result(school.post(TEACHER+'/export',params={**context(story),'status':'APPROVED'}))['rowCount']==0
        returned=result(decide(teacher,correction,'RETURN','请补齐本次更正说明'))
        resubmitted=result(student.post(MOBILE,json={**payload,'expectedVersion':returned['version'],
            'fields':fields(positionName='归档后更正岗位',salary='4200'),'correctionReason':'已补充核对本次岗位薪酬更正'}))
        result(decide(teacher,resubmitted,'APPROVE'))
        assert result(school.post(TEACHER+'/export',params={**context(story),'status':'APPROVED'}))['rowCount']==1
        assert school.get(ROOT+'/archive-packages/'+package['packageId']+'/download').content==before
        with get_sessionmaker()() as db:
            batch=db.get(InternshipBatch,int(story['batchId']));batch.status='ENDED';db.commit()
        assert result(student.get(MOBILE,params=context(story)))['canSubmit'] is False
        assert student.post(MOBILE,json={**payload,'expectedVersion':6,'correctionReason':'合成关闭批次不能更正'}).status_code==409
        with get_sessionmaker()() as db:
            db.get(InternshipBatch,int(story['batchId'])).status='RUNNING'
            score=db.get(InternshipFinalScore,int(story['scoreId']));score.version+=1;db.commit()
        assert result(student.get(MOBILE,params=context(story)))['canSubmit'] is False
        assert student.post(MOBILE,json={**payload,'expectedVersion':6,'correctionReason':'合成冻结成绩漂移不能提交'}).status_code==409
