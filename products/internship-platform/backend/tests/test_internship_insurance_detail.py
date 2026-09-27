"""Insurance deep links: real MySQL tenant/batch/teacher row isolation."""
import uuid
import pytest

TID = 1000000000000000001


def context(tenant=TID, role='SCHOOL_ADMIN', uid='1'):
    from app.core.context import set_tenant, set_current_user
    user = {'tenantId': str(tenant), 'userId': uid, 'realName': '保险核验测试',
            'userType': 'ADMIN' if role == 'SCHOOL_ADMIN' else 'TEACHER', 'currentRoleCode': role}
    set_tenant({'tenantId': str(tenant)})
    set_current_user(user)
    return user


@pytest.fixture
def policy(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, InternshipInsurance, StudentProfile
    context()
    with get_sessionmaker()() as db:
        batches = [InternshipBatch(tenant_id=TID, batch_no=uuid.uuid4().hex,
                   batch_name='保险核验测试批次', status='RUNNING') for _ in range(2)]
        student = StudentProfile(tenant_id=TID, student_no=uuid.uuid4().hex[:20], real_name='虚构核验学生', status='ACTIVE')
        db.add_all([*batches, student]); db.flush()
        record = InternshipRecord(tenant_id=TID, student_id=student.id, batch_id=batches[0].id,
                                  advisor_user_id=987654321, status='PREPARING')
        db.add(record); db.flush()
        insurance = InternshipInsurance(tenant_id=TID, internship_id=record.id, student_id=student.id,
                    policy_no='TEST-POLICY', insurer_name='虚构保险公司', status='PENDING_VERIFY')
        db.add(insurance); db.commit()
        return {'id': str(insurance.id), 'batch': str(batches[0].id), 'other_batch': str(batches[1].id), 'student': student.id}


def test_detail_and_queue_read_same_record(policy):
    from app.modules.internship.services import internship_insurance_service as svc
    user = context()
    detail = svc.get_insurance(policy['id'], batch_id=policy['batch'], user=user)
    rows, total = svc.list_insurances(1, 20, batch_id=policy['batch'], user=user)
    assert total == 1 and rows[0] == detail
    assert detail['id'] == policy['id'] and isinstance(detail['version'], int)


def test_deep_link_rejects_other_batch_and_tenant(policy):
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_insurance_service as svc
    with pytest.raises(AppException) as wrong_batch:
        svc.get_insurance(policy['id'], batch_id=policy['other_batch'], user=context())
    assert wrong_batch.value.http_status == 404
    with pytest.raises(AppException) as foreign:
        svc.get_insurance(policy['id'], batch_id=policy['batch'], user=context(TID + 1))
    assert foreign.value.http_status == 404


def test_unassigned_mentor_cannot_read_deep_link(policy):
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_insurance_service as svc
    with pytest.raises(AppException):
        svc.get_insurance(policy['id'], batch_id=policy['batch'], user=context(role='INTERN_MENTOR', uid='987654322'))


def test_deleted_student_is_not_exposed(policy):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_insurance_service as svc
    with get_sessionmaker()() as db:
        db.get(StudentProfile, policy['student']).is_deleted = True; db.commit()
    with pytest.raises(AppException):
        svc.get_insurance(policy['id'], batch_id=policy['batch'], user=context())


def test_compliance_rechecks_approved_insurance_period_in_mysql(policy):
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, InternshipInsurance
    from app.modules.internship.services.internship_compliance_service import evaluate_internship_compliance

    today = datetime.utcnow().date()
    with get_sessionmaker()() as db:
        ins = db.get(InternshipInsurance, int(policy['id']))
        rec = db.get(InternshipRecord, ins.internship_id)
        batch = db.get(InternshipBatch, rec.batch_id)
        batch.start_date = datetime.combine(today - timedelta(days=3), datetime.min.time())
        batch.end_date = datetime.combine(today + timedelta(days=30), datetime.min.time())
        batch.rules_config = {"compliance": {"insurance": {"required": True, "severity": "BLOCK"}}}
        ins.status = "VERIFIED"
        ins.effective_date = (today - timedelta(days=3)).isoformat()
        record_id = rec.id
        for expiry, expected in [(today - timedelta(days=1), "MISSING"), (today + timedelta(days=29), "MISSING"), (today + timedelta(days=30), "VALID")]:
            ins.expiry_date = expiry.isoformat()
            db.commit()
            result = evaluate_internship_compliance(str(record_id), user=context(), db=db)
            item = next(item for item in result['items'] if item['code'] == 'insurance')
            assert item['status'] == expected
            assert item['evidenceId'] == policy['id']
            assert ('insurance' in {item['code'] for item in result['blockers']}) == (expected != 'VALID')

def test_resubmitted_file_binds_atomically_and_old_version_cannot_replace_it(policy):
    from app.core.context import set_current_user
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, InternshipInsurance, InternshipAuditTrail
    from app.models.file import FileObject, FileBinding
    from app.services.file_access_service import require_file_access
    from app.modules.internship.services import internship_insurance_service as svc
    from sqlalchemy import select
    with get_sessionmaker()() as db:
        student = db.get(StudentProfile, policy['student'])
        sno = student.student_no
        db.get(InternshipInsurance, int(policy['id'])).status = 'REJECTED'
        files = [FileObject(tenant_id=TID, file_key=f'test-insurance/{uuid.uuid4().hex}.txt',
                 file_name='fictional-policy.txt', ext='txt', mime_type='text/plain', size_bytes=8,
                 sha256=uuid.uuid4().hex * 2, biz_type='TEMP_PRIVATE', owner_user_id=99001,
                 visibility='PRIVATE', status='AVAILABLE', storage_backend='local', storage_zone='ACTIVE',
                 upload_source='USER', scan_required=False, scan_status='NOT_REQUIRED') for _ in range(2)]
        db.add_all(files); db.commit(); file_ids=[str(f.id) for f in files]
    actor={'tenantId':str(TID),'userId':'99001','userType':'STUDENT','currentRoleCode':'STUDENT',
           'studentNo':sno,'studentId':str(policy['student']),'realName':'虚构核验学生'}
    context();set_current_user(actor)
    body={'policyNo':'INS-TEST-REPLACEMENT','insurerName':'虚构保险机构','effectiveDate':'2026-09-01',
          'expiryDate':'2027-02-28','fileId':file_ids[0],'expectedVersion':0}
    updated=svc.student_submit(actor,body)
    assert updated['status']=='PENDING_VERIFY' and updated['version']==1
    with pytest.raises(AppException):
        svc.student_submit(actor,{**body,'fileId':file_ids[1]})
    with get_sessionmaker()() as db:
        saved=db.get(InternshipInsurance,int(policy['id']))
        assert saved.file_id==file_ids[0] and saved.version==1
        binding=db.scalar(select(FileBinding).where(FileBinding.file_id==int(file_ids[0]),FileBinding.is_deleted.is_(False)))
        assert binding.biz_type=='INTERNSHIP_INSURANCE' and binding.biz_id==policy['id']
        assert binding.scope_json['studentId']==str(policy['student'])
        assert db.get(FileObject,int(file_ids[1])).biz_type=='TEMP_PRIVATE'
        trail=db.scalar(select(InternshipAuditTrail).where(InternshipAuditTrail.target_id==int(policy['id']),InternshipAuditTrail.target_type=='INSURANCE'))
        assert trail.action=='RESUBMIT'
    admin=context()
    assert str(require_file_access(file_ids[0],user=admin,action='meta').id)==file_ids[0]


def test_insurance_renewal_returns_to_teacher_review_and_preserves_old_evidence(policy):
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from app.core.context import set_current_user
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipInsurance, InternshipAuditTrail, StudentProfile
    from app.models.file import FileObject, FileBinding
    from app.modules.internship.services import internship_insurance_service as svc

    today = datetime.utcnow().date()
    start, end = (today - timedelta(days=30)).isoformat(), (today + timedelta(days=60)).isoformat()
    with get_sessionmaker()() as db:
        # Start without an insurance row so the production ORM creation hook
        # and the explicit replacement path are both exercised by this story.
        db.delete(db.get(InternshipInsurance, int(policy['id'])))
        batch = db.get(InternshipBatch, int(policy['batch']))
        batch.start_date = datetime.fromisoformat(start); batch.end_date = datetime.fromisoformat(end)
        student = db.get(StudentProfile, policy['student']); sno = student.student_no
        files = [FileObject(tenant_id=TID, file_key=f'test-renewal/{uuid.uuid4().hex}.txt',
                 file_name='fictional-renewal.txt', ext='txt', mime_type='text/plain', size_bytes=8,
                 sha256=uuid.uuid4().hex * 2, biz_type='TEMP_PRIVATE', owner_user_id=99001,
                 visibility='PRIVATE', status='AVAILABLE', storage_backend='local', storage_zone='ACTIVE',
                 upload_source='USER', scan_required=False, scan_status='NOT_REQUIRED') for _ in range(2)]
        db.add_all(files); db.commit(); file_ids = [str(f.id) for f in files]
    actor = {'tenantId':str(TID),'userId':'99001','userType':'STUDENT','currentRoleCode':'STUDENT',
             'studentNo':sno,'studentId':str(policy['student']),'realName':'虚构续保学生'}
    body = {'policyNo':'RENEW-FIXTURE','insurerName':'虚构保险机构','effectiveDate':start,
            'expiryDate':(today - timedelta(days=1)).isoformat(),'fileId':file_ids[0],
            'expectedVersion':0,'batchId':policy['batch']}
    context(); set_current_user(actor)
    initial = svc.student_submit(actor, body)
    policy['id'] = initial['id']
    with get_sessionmaker()() as db:
        bindings = db.scalars(select(FileBinding).where(FileBinding.file_id == int(file_ids[0]), FileBinding.is_deleted.is_(False))).all()
        assert len(bindings) == 1 and bindings[0].biz_id == initial['id']
    approved = svc.verify_insurance(initial['id'], 'APPROVE', expected_version=initial['version'], user=context())
    assert approved['canRenew'] is True
    context(); set_current_user(actor)
    assert svc.student_my_insurance(actor)['canRenew'] is True
    with pytest.raises(AppException):
        svc.student_submit(actor, {**body, 'expectedVersion':approved['version']})
    update = {**body, 'fileId':file_ids[1], 'expiryDate':end, 'expectedVersion':approved['version']}
    renewed = svc.student_submit(actor, update)
    assert renewed['id'] == approved['id'] and renewed['status'] == 'PENDING_VERIFY'
    assert renewed['verifiedAt'] == '' and renewed['canRenew'] is False
    with pytest.raises(AppException):
        svc.student_submit(actor, update)
    with get_sessionmaker()() as db:
        saved = db.get(InternshipInsurance, int(policy['id']))
        trail = db.scalar(select(InternshipAuditTrail).where(InternshipAuditTrail.target_id == saved.id, InternshipAuditTrail.action == 'RENEW'))
        assert trail.detail_json['previousPolicy']['fileId'] == file_ids[0]
        assert trail.detail_json['previousPolicy']['version'] == approved['version']
        assert trail.detail_json['previousPolicy']['verifiedAt']
        binding = db.scalar(select(FileBinding).where(FileBinding.file_id == int(file_ids[1]), FileBinding.is_deleted.is_(False)))
        assert binding.biz_id == policy['id'] and saved.file_id == file_ids[1]
    final = svc.verify_insurance(renewed['id'], 'APPROVE', expected_version=renewed['version'], user=context())
    assert final['status'] == 'VERIFIED' and final['coverageStatus'] == 'VALID'
    context(); set_current_user(actor)
    reread = svc.student_my_insurance(actor)
    assert reread['canRenew'] is False and reread['version'] == final['version']
    with pytest.raises(AppException):
        svc.student_submit(actor, {**update, 'expectedVersion':final['version']})
