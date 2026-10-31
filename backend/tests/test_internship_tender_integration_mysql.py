"""招标能力回接：用隔离 MySQL 验证预审交接、责任顺序和敏感字段存储。"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException

TID = 1000000000000000001


def _activate(user):
    set_tenant({'tenantId': str(TID)})
    set_current_user(user)


@pytest.fixture
def tender_rows(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (College, InternshipBatch, InternshipRecord, Major, Permission,
                            Role, RolePermission, SchoolClass, StudentProfile, Tenant, User, UserRole)
    from app.services.student_account_link_service import bind_in_session
    _activate(None)
    with get_sessionmaker()() as db:
        if not db.get(Tenant, TID):
            db.add(Tenant(id=TID, tenant_code=f'tender-test-{TID}', school_name='虚构招标接入测试学校'))
        college = College(tenant_id=TID, college_name='虚构实习测试学院', status='ACTIVE')
        db.add(college); db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name='虚构实习测试专业', status='ACTIVE')
        db.add(major); db.flush()
        school_class = SchoolClass(tenant_id=TID, major_id=major.id, class_name='虚构实习测试班', status='ACTIVE')
        db.add(school_class); db.flush()
        student = StudentProfile(tenant_id=TID, student_no='TENDER-INTEGRATION-001', real_name='虚构实习学生',
            college_id=college.id, major_id=major.id, class_id=school_class.id, grade='2025',
            current_stage='INTERN', student_status='NORMAL', status='ACTIVE', enroll_date=datetime(2025,9,1))
        db.add(student)
        accounts = {}
        for key, role_code, user_type, permissions in (
            ('student','STUDENT','STUDENT',()),
            ('mentor','INTERN_MENTOR','TEACHER',('internship.employment.view','internship.employment.review','internship.leave.review',
                'internship.payroll.view','internship.payroll.review','internship.student.material.view','internship.material.review',
                'internship.attendance.view','internship.guidance.view','internship.archive.view')),
            ('employer','EMPLOYMENT_TEACHER','TEACHER',('employment.view','systemAdmin.approval.view','systemAdmin.approval.manage')),
            ('school','SCHOOL_ADMIN','SCHOOL_ADMIN',('internship.leave.policy.view','internship.leave.policy.manage','internship.leave.review','internship.reporting.view','internship.archive.view')),
        ):
            account=User(tenant_id=TID,login_name='tender-'+key,real_name='虚构'+key,
                password_hash='unusable-test-only',user_type=user_type,status='ACTIVE')
            role=Role(tenant_id=TID,role_code=role_code,role_name='测试'+key,role_type='CUSTOM',status='ACTIVE')
            db.add_all([account,role]); db.flush()
            membership=UserRole(tenant_id=TID,user_id=account.id,role_id=role.id,status='ACTIVE')
            db.add(membership); db.flush()
            for code in permissions:
                permission=db.scalar(select(Permission).where(Permission.permission_code==code))
                if not permission:
                    permission=Permission(permission_code=code,permission_name='测试权限',module_code='INTERNSHIP')
                    db.add(permission);db.flush()
                db.add(RolePermission(tenant_id=TID,role_id=role.id,permission_id=permission.id,status='ACTIVE'))
            accounts[key]={'userId':'db-'+str(account.id),'tenantId':str(TID),'loginName':account.login_name,
                'realName':account.real_name,'userType':user_type,'currentRoleCode':role_code,'activeContextId':'role:'+str(role.id),
                'membershipId':membership.id}
        db.flush()
        bind_in_session(db,tenant_id=TID,student_id=student.id,
            user_id=int(accounts['student']['userId'].removeprefix('db-')),student_no=student.student_no)
        accounts['student'].update(studentId=str(student.id),studentNo=student.student_no)
        batch=InternshipBatch(tenant_id=TID,batch_no='TENDER-INTEGRATION',batch_name='虚构招标接入批次',
            status='RUNNING',planned_count=1,start_date=datetime(2026,1,1),end_date=datetime(2027,12,31),rules_config={})
        db.add(batch);db.flush()
        record=InternshipRecord(tenant_id=TID,student_id=student.id,batch_id=batch.id,status='ONBOARD',
            advisor_user_id=int(accounts['mentor']['userId'].removeprefix('db-')),advisor_name=accounts['mentor']['realName'],
            eligibility_status='QUALIFIED',destination_type='SELF_ARRANGED',enterprise_name='虚构测试企业',
            intern_start_date=batch.start_date,intern_end_date=batch.end_date)
        db.add(record);db.commit()
        result={'studentId':student.id,'recordId':record.id,'batchId':batch.id,'batchVersion':batch.version,**accounts}
    try:
        yield result
    finally:
        set_current_user(None)
        set_tenant(None)


def _employment_payload(rows, expected=0):
    return {'batchId':str(rows['batchId']),'internshipId':str(rows['recordId']),
        'expectedVersion':expected,'registrationMode':'EMPLOYMENT','attachmentFileIds':[],
        'fields':{'studentName':'虚构实习学生','studentNo':'TENDER-INTEGRATION-001',
            'collegeName':'虚构实习测试学院','majorName':'虚构实习测试专业','className':'虚构实习测试班','grade':'2025',
            'enrollmentYear':'2025','studentPhone':'13800000001','employmentType':'签约就业',
            'companyName':'虚构测试企业有限公司','creditCode':'91310110MA1G123456','companyAddress':'虚构地区测试地址',
            'companyScale':'小型','companyPhone':'021-12345678','companyEmail':'test@example.invalid',
            'hrContact':'虚构联系人','companyNature':'民营','industry':'制造业','jobCategory':'技术',
            'positionName':'虚构技术岗位','majorMatch':True,'salary':'3500.00','agreementNo':'TEST-AGREEMENT'}}


def test_employment_pre_review_opens_formal_task_and_does_not_write_ledger(tender_rows):
    from app.db.session import get_sessionmaker
    from app.models import EmpDestinationSubmission, EmpStudent, InternshipEmploymentReview, WorkflowTask
    from app.modules.internship.services import internship_employment_service as service
    from app.services import db_service
    rows=tender_rows
    _activate(rows['student'])
    submitted=service.submit_my(rows['student'],_employment_payload(rows))
    payload={'action':'APPROVE','comment':'已核对原始登记资料','expectedVersion':submitted['version'],
        'submissionId':submitted['current']['id']}
    _activate(rows['mentor'])
    reviewed=service.review(rows['mentor'],submitted['id'],payload)
    assert reviewed['statusLabel']=='预审已通过'
    assert reviewed['formalSubmission']['status']=='SUBMITTED'
    assert reviewed['summaryStatusLabel']=='待就业老师审批'
    with get_sessionmaker()() as db:
        formal=db.get(EmpDestinationSubmission,int(reviewed['formalSubmission']['submissionId']))
        task=db.get(WorkflowTask,formal.current_task_id)
        assert task.assignee_id==int(rows['employer']['userId'].removeprefix('db-'))
        assert db.scalar(select(func.count()).select_from(EmpStudent).where(EmpStudent.student_id==rows['studentId']))==0
        assert db.scalar(select(func.count()).select_from(InternshipEmploymentReview))==1
        task_id,task_version=task.id,task.version
    with pytest.raises(AppException):
        service.review(rows['mentor'],submitted['id'],payload)
    _activate(rows['student'])
    with pytest.raises(AppException,match='就业老师审批'):
        service.submit_my(rows['student'],{**_employment_payload(rows,reviewed['version']),'correctionReason':'测试重复修改正在审批的数据'})
    _activate(rows['employer'])
    db_service.act_task(task_id,'APPROVED',user=rows['employer'],version=task_version)
    _activate(rows['student'])
    result=service.get_my(rows['student'],batch_id=rows['batchId'],internship_id=rows['recordId'])['registration']
    assert result['formalSubmission']['status']=='APPROVED'
    with get_sessionmaker()() as db:
        ledger=db.scalar(select(EmpStudent).where(EmpStudent.student_id==rows['studentId']))
        assert ledger.company_name=='虚构测试企业有限公司'
        assert ledger.verify_status=='PENDING_VERIFY'


def test_formal_handoff_failure_rolls_back_pre_review_and_keeps_current_version(tender_rows,monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import InternshipEmploymentRegistration, InternshipEmploymentReview, EmpDestinationSubmission
    from app.modules.internship.services import internship_employment_service as service
    from app.modules.employment.services import employment_destination_submission_service as formal
    rows=tender_rows
    _activate(rows['student'])
    submitted=service.submit_my(rows['student'],_employment_payload(rows))
    def unavailable(*args,**kwargs):
        raise AppException('DATA_CONFLICT','正式就业流程暂不可用')
    monkeypatch.setattr(formal,'submit_in_session',unavailable)
    _activate(rows['mentor'])
    with pytest.raises(AppException,match='暂不可用'):
        service.review(rows['mentor'],submitted['id'],{'action':'APPROVE','comment':'核对完成',
            'expectedVersion':submitted['version'],'submissionId':submitted['current']['id']})
    with get_sessionmaker()() as db:
        head=db.get(InternshipEmploymentRegistration,int(submitted['id']))
        assert head.status=='SUBMITTED' and head.version==submitted['version']
        assert db.scalar(select(func.count()).select_from(InternshipEmploymentReview))==0
        assert db.scalar(select(func.count()).select_from(EmpDestinationSubmission))==0


def test_leave_policy_keeps_default_and_requires_sequential_active_assignees(tender_rows):
    from app.db.session import get_sessionmaker
    from app.models import InternshipLeave, InternshipRecord, WorkflowInstance, WorkflowTask, UserRole
    from app.modules.internship.services import internship_leave_policy_service as policy
    rows=tender_rows
    _activate(rows['student'])
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,rows['recordId'])
        leave=InternshipLeave(tenant_id=TID,internship_id=record.id,student_id=record.student_id,
            leave_type='PERSONAL',start_date='2026-11-01',end_date='2026-11-01',days=1,reason='虚构请假验证',status='PENDING')
        db.add(leave);db.flush()
        policy.start(db,leave,record)
        assert policy.latest_instance(db,TID,leave.id) is None
        db.rollback()
    _activate(rows['school'])
    nodes=[{'type':'GUIDE','roleCode':'INTERN_MENTOR','userId':''},
        {'type':'SCHOOL','roleCode':'SCHOOL_ADMIN','userId':rows['school']['userId'].removeprefix('db-')}]
    published=policy.publish(rows['school'],rows['batchId'],{'nodes':nodes,'expectedVersion':rows['batchVersion'],'reason':'测试学校明确确认两级审批'})
    assert published['checkedStudents']==1
    _activate(rows['student'])
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,rows['recordId'])
        leave=InternshipLeave(tenant_id=TID,internship_id=record.id,student_id=record.student_id,
            leave_type='PERSONAL',start_date='2026-11-01',end_date='2026-11-01',days=1,reason='虚构多级请假验证',status='PENDING')
        db.add(leave);db.flush();policy.start(db,leave,record);db.commit();leave_id=leave.id
    _activate(rows['school'])
    with get_sessionmaker()() as db:
        with pytest.raises(AppException):
            policy.advance(db,rows['school'],db.get(InternshipLeave,leave_id),'APPROVE','不能越级')
        db.rollback()
    _activate(rows['mentor'])
    with get_sessionmaker()() as db:
        assert policy.advance(db,rows['mentor'],db.get(InternshipLeave,leave_id),'APPROVE','指导教师通过') is False
        db.commit()
    with get_sessionmaker()() as db:
        membership=db.get(UserRole,rows['school']['membershipId']);membership.status='DISABLED';db.commit()
    _activate(rows['school'])
    with get_sessionmaker()() as db:
        with pytest.raises(AppException,match='停用|范围'):
            policy.advance(db,rows['school'],db.get(InternshipLeave,leave_id),'APPROVE','停用身份不得审批')
        db.rollback()
        instance=policy.latest_instance(db,TID,leave_id)
        assert instance.status=='RUNNING'
        assert [r.status for r in db.scalars(select(WorkflowTask).where(WorkflowTask.instance_id==instance.id).order_by(WorkflowTask.sequence_no))]==['APPROVED','PENDING']


def test_new_application_contacts_are_encrypted_at_rest(tender_rows):
    from app.db.session import get_sessionmaker
    from app.models import InternshipApplication
    from app.core.field_crypto import looks_like_fernet
    rows=tender_rows
    _activate(rows['student'])
    with get_sessionmaker()() as db:
        record=InternshipApplication(tenant_id=TID,record_id=rows['recordId'],student_id=rows['studentId'],
            batch_id=rows['batchId'],application_type='SELF_ARRANGED',company_phone='13800000011',
            company_email='fictional@example.invalid',enterprise_mentor_phone='13800000012')
        db.add(record);db.commit();db.refresh(record)
        assert looks_like_fernet(record.company_phone_encrypted)
        assert looks_like_fernet(record.company_email_encrypted)
        assert looks_like_fernet(record.enterprise_mentor_phone_encrypted)
        assert record.company_phone=='13800000011'
        assert record.enterprise_mentor_phone=='13800000012'
        assert 'company_phone' not in record.__table__.c
        assert 'enterprise_mentor_phone' not in record.__table__.c


def test_regulatory_reporting_permission_does_not_expand_college_scope(tender_rows):
    from app.db.session import get_sessionmaker
    from app.models import Permission, Role, RolePermission, UserRole
    from app.modules.internship.services import internship_regulatory_reporting_service as service
    rows=tender_rows
    with get_sessionmaker()() as db:
        role=Role(tenant_id=TID,role_code='COLLEGE_ADMIN',role_name='虚构学院报送角色',role_type='CUSTOM',status='ACTIVE')
        db.add(role);db.flush()
        permission=db.scalar(select(Permission).where(Permission.permission_code=='internship.reporting.view'))
        db.add(RolePermission(tenant_id=TID,role_id=role.id,permission_id=permission.id,status='ACTIVE'))
        db.add(UserRole(tenant_id=TID,user_id=int(rows['employer']['userId'].removeprefix('db-')),role_id=role.id,status='ACTIVE'))
        db.commit()
        college={**rows['employer'],'currentRoleCode':'COLLEGE_ADMIN','activeContextId':'role:'+str(role.id)}
    _activate(college)
    with pytest.raises(AppException,match='仅校级'):
        service.list_tasks(user=college)
    _activate(rows['school'])
    assert service.list_tasks(user=rows['school'])==[]


@pytest.fixture
def local_evidence(tender_rows, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services import storage
    from app.services.storage import config
    monkeypatch.setattr(settings,'UPLOAD_DIR',str(tmp_path/'uploads'))
    monkeypatch.setattr(config,'effective_config',lambda: {'backend':'local'})
    storage.reset_backend()
    yield
    storage.reset_backend()


def _image_file(actor, filename, color):
    from io import BytesIO
    from PIL import Image
    from app.services import file_service
    _activate(actor)
    output=BytesIO()
    Image.new('RGB',(360,260),color=color).save(output,format='PNG')
    return file_service.store_bytes(output.getvalue(),filename,'TEMP_PRIVATE','image/png',user=actor,visibility='PRIVATE')


def test_rotation_keeps_separate_rounds_and_frozen_weighted_result(tender_rows):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch
    from app.modules.internship.services import internship_rotation_service as service
    rows=tender_rows
    _activate(rows['mentor'])
    with get_sessionmaker()() as db:
        batch=db.get(InternshipBatch,rows['batchId'])
        batch.rules_config={'rotationScoreWeights':{'theory':20,'skill':50,'mentor':30}}
        db.commit()
    payload={'batchId':str(rows['batchId']),'departmentName':'虚构技术部门','mentorName':'虚构带教教师',
        'startDate':'2026-09-01','endDate':'2026-09-30','projects':[{'projectName':'虚构技能训练'}]}
    first=service.create_rotation(rows['recordId'],payload,rows['mentor'])
    second=service.create_rotation(rows['recordId'],{**payload,'departmentName':'虚构生产部门',
        'startDate':'2026-10-01','endDate':'2026-10-31'},rows['mentor'])
    assert first['id']!=second['id'] and second['rotationSeq']==2
    with pytest.raises(AppException,match='重叠'):
        service.create_rotation(rows['recordId'],payload,rows['mentor'])
    _activate(rows['student'])
    self_review=service.submit_self_evaluation(first['id'],{
        'batchId':str(rows['batchId']),'internshipId':str(rows['recordId']),'expectedVersion':first['version'],
        'selfRating':4,'selfEvaluation':'这是一段虚构的轮岗自评，用于验证原单版本和最终评分规则。'},rows['student'])
    _activate(rows['mentor'])
    graded=service.evaluate_rotation(first['id'],{'batchId':str(rows['batchId']),
        'expectedVersion':self_review['version'],'theoryScore':80,'skillScore':90,'mentorScore':100},rows['mentor'])
    assert graded['scores']['total']==91
    assert graded['scores']['rule']['source']=='BATCH_RULES'
    _activate(rows['student'])
    with pytest.raises(AppException,match='已完成'):
        service.submit_self_evaluation(first['id'],{'batchId':str(rows['batchId']),
            'internshipId':str(rows['recordId']),'expectedVersion':graded['version'],'selfRating':5,
            'selfEvaluation':'试图覆盖已经完成轮岗的自评，系统必须保留原来的正式记录。'},rows['student'])


def test_payroll_return_creates_new_version_and_preserves_evidence(tender_rows,local_evidence):
    from app.modules.internship.services import internship_payroll_service as service
    rows=tender_rows
    file1=_image_file(rows['student'],'工资凭证第一版.png','blue')
    payload={'batchId':str(rows['batchId']),'internshipId':str(rows['recordId']),
        'payMonth':'2026-09','actualAmount':'2400.00','currency':'CNY','paidOn':'2026-10-01',
        'evidenceFileId':file1['fileId']}
    submitted=service.submit_my(rows['student'],payload)
    with pytest.raises(AppException,match='待审核'):
        service.submit_my(rows['student'],{**payload,'expectedVersion':submitted['version']})
    _activate(rows['mentor'])
    returned=service.review(submitted['current']['id'],{'action':'RETURN','comment':'请补充完整工资到账证明',
        'expectedVersion':submitted['current']['version']},rows['mentor'])
    file2=_image_file(rows['student'],'工资凭证第二版.png','green')
    corrected=service.submit_my(rows['student'],{**payload,'evidenceFileId':file2['fileId'],
        'actualAmount':'2600.00','expectedVersion':returned['version'],'correctionReason':'已补齐凭证并更正实发金额'})
    assert corrected['id']==submitted['id'] and corrected['revisionCount']==2
    assert corrected['current']['actualAmount']==2600
    assert corrected['history'][1]['evidenceFileId']==file1['fileId']
    assert corrected['history'][1]['status']=='SUPERSEDED'
    _activate(rows['mentor'])
    final=service.review(corrected['current']['id'],{'action':'APPROVE','expectedVersion':corrected['current']['version']},rows['mentor'])
    assert final['current']['status']=='APPROVED'


def test_custom_material_return_keeps_asset_history_and_template_bytes(tender_rows,local_evidence):
    from app.db.session import get_sessionmaker
    from app.models.file import FileVersion
    from app.modules.internship.services import internship_material_requirement_service as service
    rows=tender_rows
    _activate(rows['school'])
    requirement=service.create_requirement({'batchId':str(rows['batchId']),'materialCode':'TENDER_PROOF',
        'materialName':'虚构实习佐证','minFiles':1,'maxFiles':2,'allowedExtensions':['png'],'audienceType':'ALL'},rows['school'])
    template=_image_file(rows['school'],'材料模板.png','white')
    service.attach_template(requirement['id'],template['fileId'],rows['school'])
    service.publish_requirement(requirement['id'],rows['school'])
    _activate(rows['student'])
    downloaded=service.template_download(requirement['id'],rows['student'],batch_id=rows['batchId'],internship_id=rows['recordId'])
    assert downloaded[0].read_bytes().startswith(b'\x89PNG')
    file1=_image_file(rows['student'],'材料第一版.png','yellow')
    payload={'batchId':str(rows['batchId']),'internshipId':str(rows['recordId']),
        'fileIds':[file1['fileId']],'expectedVersion':0}
    submitted=service.submit_material(rows['student'],requirement['id'],payload)
    _activate(rows['mentor'])
    returned=service.review_submission(submitted['id'],{'action':'RETURN','comment':'请补充清晰的佐证照片',
        'expectedVersion':submitted['version']},rows['mentor'])
    file2=_image_file(rows['student'],'材料第二版.png','orange')
    corrected=service.submit_material(rows['student'],requirement['id'],{**payload,'fileIds':[file2['fileId']],
        'expectedVersion':returned['version']})
    assert corrected['id']==submitted['id']
    assert corrected['files'][0]['versionNo']==2
    with get_sessionmaker()() as db:
        versions=list(db.scalars(select(FileVersion).where(FileVersion.asset_id==int(corrected['files'][0]['assetId'])).order_by(FileVersion.version_no)))
        assert [str(row.file_object_id) for row in versions]==[file1['fileId'],file2['fileId']]
        assert versions[0].is_current is False and versions[1].is_current is True


def test_watermark_keeps_original_bytes_and_formal_documents_refuse_missing_facts(tender_rows,local_evidence):
    from hashlib import sha256
    from app.db.session import get_sessionmaker
    from app.models import FileObject, InternshipCheckin, InternshipFormalDocument
    from app.services import file_service
    from app.modules.internship.services import internship_checkin_evidence_service as evidence
    from app.modules.internship.services import internship_formal_document_service as documents
    rows=tender_rows
    original=_image_file(rows['student'],'合成现场原图.png','purple')
    original_path,_=file_service.resolve_download(original['fileId'],user=rows['student'])
    original_bytes=original_path.read_bytes()
    with get_sessionmaker()() as db:
        checkin=InternshipCheckin(tenant_id=TID,internship_id=rows['recordId'],checkin_date='2026-10-01',
            checkin_at=datetime(2026,10,1,1,0),result='NORMAL',evidence_file_id=original['fileId'])
        db.add(checkin);db.flush()
        result=evidence.watermark_photo(original_file_id=original['fileId'],checkin_id=checkin.id,
            watermark_text='2026-10-01 09:00 虚构测试地点',actor=rows['student'],student_id=rows['studentId'],
            batch_id=str(rows['batchId']),db=db)
        checkin.watermarked_file_id=result['watermarkedFileId']
        checkin.evidence_sha256=result['originalSha256'];checkin.watermarked_sha256=result['watermarkedSha256']
        db.commit()
    assert original_path.read_bytes()==original_bytes
    assert result['originalSha256']==sha256(original_bytes).hexdigest()
    assert result['watermarkedSha256']!=result['originalSha256']
    transformed,_=file_service.resolve_download(result['watermarkedFileId'],user=rows['student'])
    assert sha256(transformed.read_bytes()).hexdigest()==result['watermarkedSha256']
    _activate(rows['mentor'])
    readiness=documents.document_readiness(rows['mentor'],rows['recordId'])
    certificate=next(item for item in readiness['items'] if item['documentType']=='INTERNSHIP_CERTIFICATE')
    assert not certificate['ready'] and certificate['reason']
    with pytest.raises(AppException):
        documents.generate(rows['mentor'],{'internshipId':rows['recordId'],'documentType':'INTERNSHIP_CERTIFICATE'})
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipFormalDocument))==0
