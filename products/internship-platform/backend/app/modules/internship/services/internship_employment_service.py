"""Minimal local employment declarations behind EmploymentGateway; no full employment imports."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.field_crypto import decrypt_field, encrypt_field
from app.core.permissions import enforce_permission, has_permission
from app.models import (College, EmpCompany, Major, SchoolClass, StudentAccountLink, StudentContact,
                        StudentProfile, UnifiedMessage, InternshipRecord, InternshipAuditTrail,
                        InternshipEmploymentRegistration as Registration,
                        InternshipEmploymentSubmission as Submission, InternshipEmploymentReview as Review)
from app.modules.internship.services.internship_scope import assert_internship_record_scope, apply_internship_record_scope, lock_internship_record
from app.modules.internship.services.internship_student_context_guard import require_explicit_context, require_expected_version
from app.modules.internship.services import internship_todo_helper as todo, internship_audit_service as audit
from app.services import file_access_service as files, file_business_binding_service as bindings
from app.services.db_service import _as_id, _iso, _tid, session

FIELD_LABELS = {
    'studentName': '姓名', 'studentNo': '学号', 'collegeName': '院系', 'majorName': '专业',
    'grade': '年级', 'className': '班级', 'enrollmentYear': '入校年份', 'studentPhone': '学生手机',
    'employmentType': '就业类型', 'companyName': '单位名称', 'creditCode': '统一社会信用代码',
    'companyAddress': '企业所在地址', 'companyScale': '企业规模', 'companyPhone': '企业电话',
    'companyEmail': '企业邮箱', 'hrContact': '企业人事联系人', 'companyNature': '企业性质',
    'industry': '所属行业', 'jobCategory': '岗位类别', 'positionName': '岗位名称',
    'majorMatch': '专业是否对口', 'salary': '月薪（元）', 'agreementNo': '协议书编号',
}
IDENTITY_FIELDS = {'studentName','studentNo','collegeName','majorName','grade','className'}
STATUS_LABELS = {'SUBMITTED':'待教师审核','RETURNED':'已退回补正','APPROVED':'已核验'}
MODE_LABELS = {'EMPLOYMENT':'就业上报','INTERNSHIP_TRANSFER':'实习转就业'}
TODO_TYPE = 'INTERN_EMPLOYMENT_REPORT'
BIZ_TYPE = 'INTERNSHIP_EMPLOYMENT'

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None,microsecond=0)

def _uid(user):
    raw = str((user or {}).get('userId') or '').removeprefix('db-')
    if not raw.isascii() or not raw.isdigit() or not 0 < int(raw) < 2**63:
        raise no_permission('当前账号无有效用户身份')
    return int(raw)

def _text(value, label, maximum, required=False):
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise AppException('VALIDATION_ERROR', label+'格式不正确')
    value = value.strip()
    if required and not value:
        raise AppException('VALIDATION_ERROR', '请填写'+label)
    if len(value) > maximum:
        raise AppException('VALIDATION_ERROR', f'{label}最多{maximum}字')
    return value

def _org(db, model, row_id):
    row = db.get(model, row_id) if row_id else None
    return row if row and row.tenant_id == _tid() and not row.is_deleted else None

def _identity(db, student):
    school_class = _org(db, SchoolClass, student.class_id)
    major = _org(db, Major, student.major_id or (school_class.major_id if school_class else None))
    college = _org(db, College, student.college_id or (major.college_id if major else None))
    phone = db.scalar(select(StudentContact).where(StudentContact.tenant_id == _tid(),
        StudentContact.student_id == student.id, StudentContact.contact_type == 'PHONE',
        StudentContact.is_deleted.is_(False)).order_by(StudentContact.is_primary.desc(), StudentContact.id.desc()))
    return {'studentName':student.real_name, 'studentNo':student.student_no,
            'collegeName':college.college_name if college else '', 'majorName':major.major_name if major else '',
            'className':school_class.class_name if school_class else '',
            'grade':student.grade or (school_class.grade if school_class else '') or '',
            'enrollmentYear':str(student.enroll_date.year) if student.enroll_date else '',
            'studentPhone':decrypt_field(phone.contact_value_encrypted) if phone else ''}

def _company(db, record):
    row = _org(db, EmpCompany, record.enterprise_id)
    if row and row.status == 'ACTIVE' and not row.blacklist:
        return row
    return None

def _prefill(db, record, student):
    identity = _identity(db, student)
    company = _company(db, record)
    transfer = {'companyName':company.name, 'creditCode':company.credit_code or '',
        'companyAddress':company.address or '', 'companyScale':company.scale or '',
        'companyPhone':decrypt_field(company.contact_phone_encrypted) or '',
        'hrContact':company.contact_person or '', 'companyNature':company.nature or '',
        'industry':company.industry or '', 'positionName':record.position_name or ''} if company else None
    return {'identity':identity, 'transfer':transfer, 'canTransfer':bool(company),
        'transferHint':'' if company else '当前实习尚无有效的正式企业关联，可先普通就业上报，或请学校核实企业安置。',
        'fieldLabels':FIELD_LABELS, 'identityEditable':{'studentPhone':True, 'enrollmentYear':not bool(student.enroll_date)}}

def _declaration(db, record, student, payload, mode):
    raw = payload.get('fields')
    if not isinstance(raw, dict) or set(raw) - set(FIELD_LABELS):
        raise AppException('VALIDATION_ERROR','登记信息包含未支持内容，请刷新登记页')
    authoritative = _identity(db, student)
    missing = [FIELD_LABELS[key] for key in FIELD_LABELS if key in IDENTITY_FIELDS and not authoritative[key]]
    if missing:
        raise AppException('DATA_CONFLICT','学校档案缺少'+ '、'.join(missing)+'，请联系学校补齐后登记')
    for key in IDENTITY_FIELDS:
        if key in raw and str(raw[key] or '').strip() != str(authoritative[key] or ''):
            raise no_permission('学校身份和组织信息不能由就业登记修改')
    values = dict(authoritative)
    sources = {key:'SCHOOL_PROFILE' for key in authoritative}
    phone = _text(raw.get('studentPhone',values['studentPhone']), '学生手机', 30, True)
    if not re.fullmatch(r'\+?[0-9 ()-]{6,30}',phone):
        raise AppException('VALIDATION_ERROR','学生手机格式不正确')
    year = _text(raw.get('enrollmentYear',values['enrollmentYear']), '入校年份', 4, True)
    if not year.isascii() or not year.isdigit() or not 1900 <= int(year) <= _now().year:
        raise AppException('VALIDATION_ERROR','请填写四位的真实入校年份')
    if student.enroll_date and year != authoritative['enrollmentYear']:
        raise no_permission('学校已有入校年份不能由就业登记修改')
    sources['studentPhone'] = 'SCHOOL_CONTACT' if phone == authoritative['studentPhone'] else 'STUDENT_DECLARED'
    sources['enrollmentYear'] = 'SCHOOL_PROFILE' if student.enroll_date else 'STUDENT_DECLARED'
    values.update(studentPhone=phone,enrollmentYear=year)
    lengths = {'employmentType':50,'companyName':200,'creditCode':18,'companyAddress':300,'companyScale':50,
        'companyPhone':50,'companyEmail':200,'hrContact':100,'companyNature':50,'industry':100,
        'jobCategory':100,'positionName':100,'agreementNo':100}
    for key, maximum in lengths.items():
        values[key] = _text(raw.get(key),FIELD_LABELS[key],maximum,True)
        sources[key] = 'STUDENT_DECLARED'
    values['creditCode'] = values['creditCode'].upper()
    if not re.fullmatch(r'[0-9A-HJ-NPQRTUWXY]{18}',values['creditCode']):
        raise AppException('VALIDATION_ERROR','统一社会信用代码应为18位合法大写字符')
    if not re.fullmatch(r'\+?[0-9 ()-]{6,50}',values['companyPhone']):
        raise AppException('VALIDATION_ERROR','企业电话格式不正确')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',values['companyEmail']):
        raise AppException('VALIDATION_ERROR','企业邮箱格式不正确')
    if type(raw.get('majorMatch')) is not bool:
        raise AppException('VALIDATION_ERROR','请选择专业是否对口')
    values['majorMatch'] = raw['majorMatch']
    try:
        amount = Decimal(str(raw.get('salary')))
    except (InvalidOperation,ValueError):
        raise AppException('VALIDATION_ERROR','月薪必须是合法金额') from None
    if not amount.is_finite() or amount < 0 or amount > Decimal('999999999.99') or amount != amount.quantize(Decimal('.01')):
        raise AppException('VALIDATION_ERROR','月薪应为非负金额，最多保留两位小数')
    values['salary'] = str(amount.quantize(Decimal('.01')))
    sources.update(majorMatch='STUDENT_DECLARED',salary='STUDENT_DECLARED')
    source_company_id = None
    if mode == 'INTERNSHIP_TRANSFER':
        company = _company(db, record)
        if not company:
            raise AppException('DATA_CONFLICT','当前实习缺少有效的正式企业关联，无法实习转就业')
        if values['companyName'] != company.name or values['creditCode'] != str(company.credit_code or '').upper():
            raise AppException('DATA_CONFLICT','实习转就业的单位必须与当前正式实习企业一致，请刷新后重试')
        source_company_id = company.id
        sources.update(companyName='CURRENT_INTERNSHIP_COMPANY',creditCode='CURRENT_INTERNSHIP_COMPANY')
    return {'fields':values,'sources':sources}, source_company_id

def _head(db, record_id, lock=False):
    query = select(Registration).where(Registration.tenant_id == _tid(), Registration.internship_id == record_id,
        Registration.is_deleted.is_(False))
    return db.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)

def _view(db, head, history=True, masked=False, loaded=None):
    if not head:
        return None
    if loaded is not None:
        submissions, reviews = loaded
    else:
        query = select(Submission).where(Submission.tenant_id == _tid(), Submission.registration_id == head.id)
        review_query = select(Review).where(Review.tenant_id == _tid(), Review.registration_id == head.id)
        if not history:
            query = query.where(Submission.id == head.current_submission_id)
            review_query = review_query.where(Review.submission_id == head.current_submission_id)
        submissions = db.scalars(query.order_by(Submission.revision_no.desc())).all()
        reviews = db.scalars(review_query).all()
    review_map = {row.submission_id:row for row in reviews}
    versions = []
    for row in submissions:
        if not history and row.id != head.current_submission_id:
            continue
        content = json.loads(decrypt_field(row.details_encrypted,allow_legacy_plaintext=False))
        if masked:
            content['fields'] = {key:('已隐藏，请说明核验用途后查看' if key in SENSITIVE_FIELDS and value else value)
                for key,value in content['fields'].items()}
        review = review_map.get(row.id)
        versions.append({'id':str(row.id),'revisionNo':row.revision_no,'registrationMode':row.registration_mode,
            'modeLabel':MODE_LABELS.get(row.registration_mode,'就业登记'),'fields':content['fields'],'sources':content['sources'],
            'sourceCompanyId':str(row.source_company_id or ''),'attachments':row.attachments_json,
            'submittedAt':_iso(row.submitted_at),'correctionReason':decrypt_field(row.correction_reason_encrypted,allow_legacy_plaintext=False) or '',
            'review':{'action':review.action,'actionLabel':'核验通过' if review.action == 'APPROVE' else '退回补正',
                'comment':decrypt_field(review.comment_encrypted,allow_legacy_plaintext=False) or '',
                'reviewerName':review.reviewer_name,'reviewedAt':_iso(review.reviewed_at)} if review else None})
    return {'id':str(head.id),'internshipId':str(head.internship_id),'studentId':str(head.student_id),
        'batchId':str(head.batch_id),'status':head.status,'statusLabel':STATUS_LABELS.get(head.status,'待核实'),
        'version':head.version,'revisionCount':head.revision_count,'fieldLabels':FIELD_LABELS,'sensitiveVisible':not masked,
        'current':next((x for x in versions if x['id'] == str(head.current_submission_id)),None),
        'history':versions if history else []}

RESULT_ACTION = 'student.internship.employment-registration'

def _notification_conditions(head, user):
    return [UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
        UnifiedMessage.receiver_user_id == _uid(user), UnifiedMessage.receiver_type == 'STUDENT',
        UnifiedMessage.receiver_context_key == 'GLOBAL', UnifiedMessage.source_module == 'internship',
        UnifiedMessage.source_biz_id == head.id, UnifiedMessage.action_key == RESULT_ACTION,
        UnifiedMessage.delivery_status == 'DELIVERED', UnifiedMessage.withdrawn_at.is_(None),
        or_(UnifiedMessage.expire_at.is_(None), UnifiedMessage.expire_at > _now())]

def _notification_view(row):
    return {'id':str(row.id), 'title':row.title, 'content':row.content or '',
        'status':row.status, 'statusLabel':'已读' if row.status == 'READ' else '未读',
        'createdAt':_iso(row.created_at), 'readAt':_iso(row.read_at) if row.read_at else None}

def _notifications(db, head, user, page):
    if not head:
        return {'items':[], 'total':0, 'unread':0, 'page':1, 'pageSize':20, 'hasMore':False}
    conditions = _notification_conditions(head,user)
    total = int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(*conditions)) or 0)
    unread = int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(*conditions,UnifiedMessage.status == 'UNREAD')) or 0)
    rows = db.scalars(select(UnifiedMessage).where(*conditions).order_by(UnifiedMessage.created_at.desc(),UnifiedMessage.id.desc())
        .offset((page-1)*20).limit(20)).all()
    return {'items':[_notification_view(row) for row in rows], 'total':total, 'unread':unread,
        'page':page, 'pageSize':20, 'hasMore':page*20 < total}

def get_my(user, *, batch_id, internship_id, notification_page=1):
    if not isinstance(notification_page,int) or isinstance(notification_page,bool) or notification_page < 1:
        raise AppException('VALIDATION_ERROR','通知页码无效')
    with session() as db:
        record, student, _ = require_explicit_context(db,user,{'batchId':batch_id,'internshipId':internship_id},for_write=False)
        head = _head(db,record.id)
        return {'batchId':str(record.batch_id),'internshipId':str(record.id),'prefill':_prefill(db,record,student),
                'registration':_view(db,head),'resultNotifications':_notifications(db,head,user,notification_page)}

def read_my_notification(user, message_id, *, batch_id, internship_id):
    with session() as db:
        record, _, _ = require_explicit_context(db,user,{'batchId':batch_id,'internshipId':internship_id},for_write=False)
        head = _head(db,record.id)
        if not head:
            raise not_found('就业结果通知不存在')
        row = db.scalar(select(UnifiedMessage).where(*_notification_conditions(head,user),UnifiedMessage.id == _as_id(message_id))
            .with_for_update().execution_options(populate_existing=True))
        if not row:
            raise not_found('就业结果通知不存在')
        if row.status != 'READ':
            row.status = 'READ'; row.read_at = _now(); row.version = int(row.version or 0)+1
            db.commit()
        return _notification_view(row)

def submit_my(user, payload):
    if set(payload) - {'batchId','internshipId','expectedVersion','registrationMode','fields','attachmentFileIds','correctionReason'}:
        raise AppException('VALIDATION_ERROR','登记请求包含未支持内容，请刷新后重试')
    mode = str(payload.get('registrationMode') or '')
    if mode not in MODE_LABELS:
        raise AppException('VALIDATION_ERROR','请选择就业上报或实习转就业')
    with session() as db:
        record, student, _ = require_explicit_context(db,user,payload,for_write=True)
        record = lock_internship_record(db,record.id)
        head = _head(db,record.id,lock=True)
        require_expected_version(payload.get('expectedVersion'),head.version if head else 0,entity_name='就业登记')
        if head and head.status == 'SUBMITTED':
            raise AppException('DATA_CONFLICT','已有待审核登记，请等待指导教师处理')
        assignee = todo.resolve_advisor_assignee_id(db,record)
        if not assignee:
            raise AppException('DATA_CONFLICT','学校尚未分配有效指导教师，无法投递就业审核')
        content, company_id = _declaration(db,record,student,payload,mode)
        reason = _text(payload.get('correctionReason'),'更正说明',500)
        if head and len(reason) < 5:
            raise AppException('VALIDATION_ERROR','补正或更正登记需填写不少于5字的说明')
        raw_files = payload.get('attachmentFileIds') or []
        if not isinstance(raw_files,list) or len(raw_files) > 9 or len(set(map(str,raw_files))) != len(raw_files):
            raise AppException('VALIDATION_ERROR','登记照片最多9张，不能重复')
        attachments = []
        for raw in raw_files:
            file_obj = files.require_file_access(str(raw),user=user,action='bind')
            if not str(file_obj.mime_type or '').lower().startswith('image/'):
                raise AppException('VALIDATION_ERROR','就业佐证仅支持照片')
            attachments.append({'fileId':str(file_obj.id),'fileName':file_obj.file_name or '就业佐证',
                'mimeType':file_obj.mime_type,'sha256':file_obj.sha256,'sizeBytes':file_obj.size_bytes})
        before = head.status if head else None
        if not head:
            head = Registration(tenant_id=_tid(),internship_id=record.id,student_id=student.id,batch_id=record.batch_id)
            db.add(head); db.flush()
        revision = int(head.revision_count or 0)+1
        snapshot = Submission(tenant_id=_tid(),registration_id=head.id,revision_no=revision,
            registration_mode=mode,source_company_id=company_id,
            details_encrypted=encrypt_field(json.dumps(content,ensure_ascii=False)),attachments_json=attachments,
            correction_reason_encrypted=encrypt_field(reason),submitted_at=_now(),submitted_by=_uid(user))
        db.add(snapshot); db.flush()
        for photo in attachments:
            bindings.bind_file_to_business(db,file_id=photo['fileId'],biz_type=BIZ_TYPE,biz_id=head.id,
                actor=user,subject_type='STUDENT',subject_id=student.id,module_code='INTERNSHIP',
                student_id=student.id,batch_id=str(record.batch_id),college_id=student.college_id,class_id=student.class_id,
                scope={'internshipId':str(record.id),'studentId':str(student.id),'batchId':str(record.batch_id)})
        head.current_submission_id = snapshot.id
        head.revision_count = revision
        head.status = 'SUBMITTED'
        head.version = int(head.version or 0)+1
        todo.todo_upsert(db,biz_type=BIZ_TYPE,biz_id=head.id,todo_type=TODO_TYPE,assignee_id=assignee,
            student_id=student.id,title=f'就业上报待审：{student.real_name}')
        audit.add_audit(db,target_type='EMPLOYMENT_REGISTRATION',target_id=head.id,
            action='EMPLOYMENT_SUBMIT' if revision == 1 else 'EMPLOYMENT_RESUBMIT',user=user,
            batch_id=record.batch_id,internship_id=record.id,before_status=before,after_status=head.status,
            expected_version=payload.get('expectedVersion'),new_version=head.version,
            file_ids=[x['fileId'] for x in attachments],detail={'submissionId':str(snapshot.id),'revisionNo':revision,
                'registrationMode':mode,'sourceCompanyId':str(company_id or '')})
        db.commit()
        return _view(db,head)

def list_for_teacher(user, *, batch_id, status='ALL',page=1,page_size=20,internship_id=None):
    enforce_permission(user,'internship.employment.view')
    if status not in {'ALL',*STATUS_LABELS}:
        raise AppException('VALIDATION_ERROR','就业登记筛选状态不正确')
    with session() as db:
        scoped = apply_internship_record_scope(select(InternshipRecord.id).where(InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == _as_id(batch_id),InternshipRecord.is_deleted.is_(False)),user)
        query = select(Registration).where(Registration.tenant_id == _tid(),Registration.batch_id == _as_id(batch_id),
            Registration.is_deleted.is_(False),Registration.internship_id.in_(scoped))
        if internship_id is not None:
            query = query.where(Registration.internship_id == _as_id(internship_id))
        if status != 'ALL':
            query = query.where(Registration.status == status)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(query.order_by(Registration.updated_at.desc(),Registration.id.desc())
            .offset((page-1)*page_size).limit(page_size)).all()
        current_ids = [row.current_submission_id for row in rows]
        snapshots = db.scalars(select(Submission).where(Submission.tenant_id == _tid(),Submission.id.in_(current_ids))).all() if rows else []
        reviews = db.scalars(select(Review).where(Review.tenant_id == _tid(),Review.submission_id.in_(current_ids))).all() if rows else []
        by_head = {row.id:([s for s in snapshots if s.registration_id == row.id],[r for r in reviews if r.registration_id == row.id]) for row in rows}
        return {'items':[_view(db,row,history=False,masked=True,loaded=by_head[row.id]) for row in rows],'total':total,
            'page':page,'pageSize':page_size,'hasMore':page*page_size < total}

def get_for_teacher(user, registration_id):
    enforce_permission(user,'internship.employment.view')
    with session() as db:
        head = db.scalar(select(Registration).where(Registration.tenant_id == _tid(),Registration.id == _as_id(registration_id),Registration.is_deleted.is_(False)))
        if not head:
            raise not_found('就业登记不存在')
        assert_internship_record_scope(db,head.internship_id,user,'查看就业登记')
        return _view(db,head,masked=True)

SENSITIVE_FIELDS = {'studentPhone','companyPhone','companyEmail','companyAddress','hrContact','salary','agreementNo'}

def disclose_for_teacher(user, registration_id, payload):
    enforce_permission(user,'internship.employment.sensitive.view')
    if set(payload) != {'purpose'}:
        raise AppException('VALIDATION_ERROR','请说明本次查看完整就业登记的用途')
    purpose = _text(payload.get('purpose'),'核验用途',200,True)
    if len(purpose) < 5:
        raise AppException('VALIDATION_ERROR','核验用途不少于5字')
    with session() as db:
        head = db.scalar(select(Registration).where(Registration.tenant_id == _tid(),Registration.id == _as_id(registration_id),Registration.is_deleted.is_(False)))
        if not head:
            raise not_found('就业登记不存在')
        assert_internship_record_scope(db,head.internship_id,user,'查看完整就业登记')
        audit.add_audit(db,target_type='EMPLOYMENT_REGISTRATION',target_id=head.id,action='EMPLOYMENT_SENSITIVE_VIEW',user=user,
            batch_id=head.batch_id,internship_id=head.internship_id,
            detail={'purposeEncrypted':encrypt_field(purpose),'submissionId':str(head.current_submission_id),
                'registrationVersion':head.version,'fields':sorted(SENSITIVE_FIELDS)})
        result = _view(db,head)
        db.commit()
        return result

def review(user, registration_id, payload):
    enforce_permission(user,'internship.employment.review')
    if set(payload) - {'action','comment','expectedVersion','submissionId'}:
        raise AppException('VALIDATION_ERROR','审核请求包含未支持内容，请刷新后重试')
    action = str(payload.get('action') or '')
    if action not in {'APPROVE','RETURN'}:
        raise AppException('VALIDATION_ERROR','请选择核验通过或退回补正')
    comment = _text(payload.get('comment'),'审核意见',1000,action == 'RETURN')
    if action == 'RETURN' and len(comment) < 5:
        raise AppException('VALIDATION_ERROR','退回原因不少于5字')
    with session() as db:
        initial = db.scalar(select(Registration).where(Registration.tenant_id == _tid(),Registration.id == _as_id(registration_id),Registration.is_deleted.is_(False)))
        if not initial:
            raise not_found('就业登记不存在')
        record = assert_internship_record_scope(db,initial.internship_id,user,'审核就业登记',lock=True)
        head = _head(db,record.id,lock=True)
        require_expected_version(payload.get('expectedVersion'),head.version,entity_name='就业登记')
        if str(payload.get('submissionId') or '') != str(head.current_submission_id) or head.status != 'SUBMITTED':
            raise AppException('DATA_CONFLICT','当前提交版本或状态已变化，请刷新后重试')
        snapshot = db.scalar(select(Submission).where(Submission.id == head.current_submission_id,
            Submission.tenant_id == _tid(),Submission.registration_id == head.id).with_for_update())
        if not snapshot:
            raise AppException('DATA_CONFLICT','登记当前版本缺失，禁止办理')
        decision = Review(tenant_id=_tid(),registration_id=head.id,submission_id=snapshot.id,action=action,
            comment_encrypted=encrypt_field(comment),reviewed_by=_uid(user),reviewer_name=str(user.get('realName') or '指导教师'),reviewed_at=_now())
        db.add(decision)
        head.status = 'APPROVED' if action == 'APPROVE' else 'RETURNED'
        head.version += 1
        todo.todo_done(db,biz_id=head.id,todo_type=TODO_TYPE)
        recipients = db.scalars(select(StudentAccountLink.user_id).where(StudentAccountLink.tenant_id == _tid(),
            StudentAccountLink.student_id == head.student_id,StudentAccountLink.is_deleted.is_(False),StudentAccountLink.link_status == 'ACTIVE')).all()
        for uid in set(recipients):
            db.add(UnifiedMessage(tenant_id=_tid(),receiver_id=uid,receiver_user_id=uid,receiver_type='STUDENT',
                receiver_context_key='GLOBAL',source_module='internship',source_biz_id=head.id,
                message_type='BUSINESS',category='BUSINESS',priority='NORMAL',status='UNREAD',
                title='就业登记核验结果',content='就业登记'+STATUS_LABELS[head.status]+'，请打开就业登记查看意见和本次提交版本。',
                action_key=RESULT_ACTION,action_params_json={'registrationId':str(head.id),
                    'batchId':str(record.batch_id),'internshipId':str(record.id),'submissionId':str(snapshot.id),'revisionNo':snapshot.revision_no},
                delivery_status='DELIVERED',delivered_at=_now()))
        audit.add_audit(db,target_type='EMPLOYMENT_REGISTRATION',target_id=head.id,action='EMPLOYMENT_'+action,
            user=user,batch_id=record.batch_id,internship_id=record.id,before_status='SUBMITTED',after_status=head.status,
            expected_version=payload.get('expectedVersion'),new_version=head.version,
            detail={'submissionId':str(snapshot.id),'revisionNo':snapshot.revision_no})
        db.commit()
        return _view(db,head,masked=True)

def authorize_employment_file(db, file_obj, file_bindings, user, action):
    if db is None or file_obj.biz_type != BIZ_TYPE or not str(file_obj.biz_id or '').isdigit():
        return False
    head = db.scalar(select(Registration).where(Registration.id == int(file_obj.biz_id),Registration.tenant_id == _tid(),Registration.is_deleted.is_(False)))
    if not head:
        return False
    if not any(not b.is_deleted and b.status == 'ACTIVE' and b.biz_type == BIZ_TYPE and str(b.biz_id) == str(head.id)
        and str(b.file_id) == str(file_obj.id) and b.tenant_id == _tid() for b in file_bindings):
        return False
    snapshots = db.scalars(select(Submission).where(Submission.tenant_id == _tid(),Submission.registration_id == head.id)).all()
    if not any(str(photo.get('fileId')) == str(file_obj.id) and photo.get('sha256') == file_obj.sha256
        for snapshot in snapshots for photo in snapshot.attachments_json or []):
        return False
    if str(user.get('userType') or '').upper() == 'STUDENT':
        record, student, _ = require_explicit_context(db,user,{'batchId':str(head.batch_id),'internshipId':str(head.internship_id)},for_write=False)
        return student.id == head.student_id and record.id == head.internship_id
    if not has_permission(user,'internship.employment.view') or not has_permission(user,'internship.employment.sensitive.view'):
        return False
    assert_internship_record_scope(db,head.internship_id,user,'访问就业佐证照片')
    # Bound photos may include contacts and agreement details. An old disclosure
    # cannot authorize a newly submitted or reviewed registration version.
    disclosed = db.scalar(select(InternshipAuditTrail.id).where(
        InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == 'EMPLOYMENT_REGISTRATION',
        InternshipAuditTrail.target_id == head.id, InternshipAuditTrail.action == 'EMPLOYMENT_SENSITIVE_VIEW',
        InternshipAuditTrail.detail_json['actorUserId'].as_string() == str(user.get('userId') or ''),
        InternshipAuditTrail.detail_json['detailJson']['submissionId'].as_string() == str(head.current_submission_id),
        InternshipAuditTrail.detail_json['detailJson']['registrationVersion'].as_integer() == head.version).limit(1))
    return disclosed is not None

def destination(student_id, *, internship_id=None):
    """Gateway projection: current school-verified declarations only; no external certification."""
    with session() as db:
        query = select(Registration).where(Registration.tenant_id == _tid(),Registration.student_id == _as_id(student_id),
            Registration.is_deleted.is_(False),Registration.status == 'APPROVED')
        if internship_id is not None:
            query = query.where(Registration.internship_id == _as_id(internship_id))
        head = db.scalar(query.order_by(Registration.updated_at.desc(),Registration.id.desc()).limit(1))
        if not head:
            return None
        view = _view(db,head,history=False)
        current = view['current']
        if not current or not current['review'] or current['review']['action'] != 'APPROVE':
            return None
        return {'recordId':view['id'],'exists':True,'status':'SCHOOL_VERIFIED','revisionNo':current['revisionNo'],
                'internshipId':view['internshipId'],'enterpriseName':current['fields']['companyName'],
                'positionName':current['fields']['positionName'],'externalVerified':False}
