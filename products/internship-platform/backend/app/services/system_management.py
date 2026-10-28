"""学校组织、人员、身份和任职。所有管理写入在本校锁和必需审计事务内完成。"""
from contextlib import contextmanager
from datetime import datetime, timedelta
import secrets
from sqlalchemy import select, update, func, or_, and_, false, literal, union_all
from app.core.exceptions import AppException, no_permission, not_found, check_version
from app.core.field_crypto import encrypt_field, mask_phone_encrypted
from app.core.permissions import enforce_permission, has_permission, _matches
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import (Tenant, User, Role, UserRole, RolePermission, Permission, College, Major, SchoolClass,
    StudentProfile, StudentContact, StudentAccountLink, TeacherStudentScope, StaffProfile, SchoolDepartment, SchoolSetting,
    SchoolDeliveryRecord, SecurityAuditLog, ExcelImportJob, UnifiedTodo, InternshipRecord)
from app.services.system_authorization import audit, active_roles, role_permissions, permission_name, preset_role_patterns, ROLE_NAMES, SYSTEM_PERMISSIONS
from app.services.mobile_teacher_service import _ADVISOR_ROLES

STATUS_LABELS = {'ACTIVE': '正常', 'DISABLED': '停用', 'LOCKED': '锁定', 'PENDING': '待处理',
                 'IMPORTED': '已完成', 'VALIDATED': '预检通过', 'FAILED': '失败', 'SUCCESS': '成功',
                 'DONE': '已完成', 'CANCELLED': '已取消', 'VERIFIED': '已核验', 'REVIEW': '待核对',
                 'UPLOADED':'已上传','VALIDATING':'正在预检','CONFIRMING':'正在确认'}
STATUS_LABELS['QUEUED']='已排队或正在整批处理'
ORG = {'colleges': (College, 'college_name', 'code', None),
       'majors': (Major, 'major_name', 'code', 'college_id'),
       'classes': (SchoolClass, 'class_name', 'class_code', 'major_id'),
       'departments': (SchoolDepartment, 'name', 'code', None)}
DIRECTORY_LABELS={'student':'学生','staff':'教职工','colleges':'院系','majors':'专业','classes':'班级','departments':'校内部门'}


def ids(user):
    raw = str(user.get('userId') or '').removeprefix('db-')
    if not raw.isdigit() or not str(user.get('tenantId') or '').isdigit():
        raise no_permission('系统管理仅支持已登录的真实学校账号')
    return int(user['tenantId']), int(raw)


def base_role(user):
    return str(user.get('currentRoleBaseCode') or user.get('currentRoleCode') or '')


def school_wide(user):
    return base_role(user) in {'SYSTEM_ADMIN', 'SCHOOL_ADMIN'}


@contextmanager
def transaction(user, permission):
    enforce_permission(user, permission)
    tenant_id, _ = ids(user)
    with get_sessionmaker()() as db:
        # ponytail: serialize school administration; split locks by object if measured contention requires it.
        school = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == 'ACTIVE',
                                                Tenant.is_deleted.is_(False)).with_for_update())
        if not school:
            raise no_permission('学校不存在或已停用')
        try:
            # Recheck after the lock: a concurrent revoke must not leave a waiting command authorized.
            from app.services.system_authorization import authorize_subject
            account = db.get(User, ids(user)[1])
            if not account or account.is_deleted or account.status != 'ACTIVE':
                raise no_permission('当前账号已停用')
            fresh = authorize_subject(db, account, dict(user))
            enforce_permission(fresh, permission)
            user.update(fresh)
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def tenant_query(model, user):
    return select(model).where(model.tenant_id == ids(user)[0], model.is_deleted.is_(False))


def unique_organization_codes(db, user, codes):
    matches = dict.fromkeys(codes, 0)
    if not matches: return set()
    for model, _, code_column, _ in ORG.values():
        for code in db.scalars(tenant_query(model,user).where(model.status=='ACTIVE',
                getattr(model,code_column).in_(matches)).with_only_columns(getattr(model,code_column))):
            matches[code] += 1
    return {code for code,count in matches.items() if count==1}


def row(db, model, identifier, user, lock=False):
    if not str(identifier).isdigit():
        raise not_found()
    query = tenant_query(model, user).where(model.id == int(identifier))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    result = db.scalar(query)
    if not result:
        raise not_found()
    return result


def scope_ids(db, user):
    tenant_id, user_id = ids(user)
    result = {key: set() for key in ('COLLEGE', 'MAJOR', 'CLASS', 'STUDENT')}
    grants = db.scalars(tenant_query(TeacherStudentScope, user).where(
        TeacherStudentScope.user_id == user_id, TeacherStudentScope.role_code == user['currentRoleCode'],
        TeacherStudentScope.status == 'ACTIVE', TeacherStudentScope.ref_id.is_not(None)))
    for grant in grants:
        if grant.scope_type in result:
            result[grant.scope_type].add(grant.ref_id)
    return result


def scoped_students(db, user):
    query = tenant_query(StudentProfile, user)
    if school_wide(user):
        return query
    if base_role(user) in _ADVISOR_ROLES:
        assigned=tenant_query(InternshipRecord,user).where(InternshipRecord.advisor_user_id==ids(user)[1])
        return query.where(StudentProfile.id.in_(assigned.with_only_columns(InternshipRecord.student_id)))
    scopes = scope_ids(db, user)
    major_ids = select(Major.id).where(Major.tenant_id == ids(user)[0], Major.is_deleted.is_(False),
        or_(Major.college_id.in_(scopes['COLLEGE']), Major.id.in_(scopes['MAJOR'])))
    class_ids = select(SchoolClass.id).where(SchoolClass.tenant_id == ids(user)[0], SchoolClass.is_deleted.is_(False),
        or_(SchoolClass.major_id.in_(major_ids), SchoolClass.id.in_(scopes['CLASS'])))
    return query.where(or_(StudentProfile.college_id.in_(scopes['COLLEGE']),
        StudentProfile.major_id.in_(major_ids), StudentProfile.class_id.in_(class_ids),
        StudentProfile.id.in_(scopes['STUDENT'])))


def scoped_staff(db, user):
    query = tenant_query(StaffProfile, user)
    if base_role(user) in _ADVISOR_ROLES: return query.where(StaffProfile.user_id==ids(user)[1])
    return query if school_wide(user) else query.where(StaffProfile.college_id.in_(scope_ids(db, user)['COLLEGE']))


def scoped_accounts(db, user):
    query = tenant_query(User, user)
    if school_wide(user):
        return query
    student_ids = scoped_students(db, user).with_only_columns(StudentProfile.id)
    linked = select(StudentAccountLink.user_id).where(StudentAccountLink.tenant_id == ids(user)[0],
        StudentAccountLink.student_id.in_(student_ids), StudentAccountLink.is_deleted.is_(False),
        StudentAccountLink.link_status == 'ACTIVE')
    if base_role(user) in _ADVISOR_ROLES: return query.where(User.user_type=='STUDENT',User.id.in_(linked))
    return query.where(or_(User.id.in_(linked), User.id.in_(scoped_staff(db, user).with_only_columns(StaffProfile.user_id))))


def org_query(db, user, kind, include_parents=False):
    model = ORG[kind][0]
    query = tenant_query(model, user)
    if school_wide(user):
        return query
    if base_role(user) in _ADVISOR_ROLES:
        if kind=='departments':
            return query.where(SchoolDepartment.id.in_(scoped_staff(db,user).with_only_columns(StaffProfile.department_id)))
        field={'colleges':StudentProfile.college_id,'majors':StudentProfile.major_id,'classes':StudentProfile.class_id}[kind]
        return query.where(model.id.in_(scoped_students(db,user).with_only_columns(field)))
    scope = scope_ids(db, user)
    if kind == 'colleges':
        parents=org_query(db,user,'majors',include_parents=True).with_only_columns(Major.college_id) if include_parents else None
        return query.where(or_(College.id.in_(scope['COLLEGE']),College.id.in_(parents) if include_parents else false()))
    if kind == 'majors':
        parents=tenant_query(SchoolClass,user).where(SchoolClass.id.in_(scope['CLASS'])).with_only_columns(SchoolClass.major_id)
        return query.where(or_(Major.college_id.in_(scope['COLLEGE']), Major.id.in_(scope['MAJOR']),
            Major.id.in_(parents) if include_parents else false()))
    if kind == 'classes':
        majors = org_query(db, user, 'majors').with_only_columns(Major.id)
        return query.where(or_(SchoolClass.major_id.in_(majors), SchoolClass.id.in_(scope['CLASS'])))
    return query.where(false())


def paginated(db, query, page, size, serializer):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = db.scalars(query.limit(size).offset((page - 1) * size)).all()
    return {'items': [serializer(item) for item in items], 'total': total, 'page': page, 'pageSize': size}


def common(item):
    return {'id': str(item.id), 'version': item.version, 'status': item.status,
            'statusLabel': STATUS_LABELS.get(item.status, '待核对')}


def edit_version(version, expected, current):
    """Only caller-provided public fields may enter a conflict response; never model dumps."""
    try:
        check_version(version, expected)
    except AppException as exc:
        exc.details = {'version': version or 0, 'current': current}
        raise


def organization(item, kind):
    _, name, code, parent = ORG[kind]
    return {**common(item), 'kind': kind, 'name': getattr(item, name), 'code': getattr(item, code),
            'parentId': str(getattr(item, parent) or '') if parent else '',
            'grade': getattr(item, 'grade', ''), 'educationYears': getattr(item, 'education_years', None),
            'trainingLevel': getattr(item, 'training_level', ''), 'nationalCode': getattr(item,'national_code','') or ''}


def list_organizations(user, kind, page=1, size=30, keyword='', object_ids=None):
    enforce_permission(user, 'system.org.view')
    with get_sessionmaker()() as db:
        query = org_query(db, user, kind)
        model, name, code, _ = ORG[kind]
        if object_ids is not None: query=query.where(model.id.in_(object_ids))
        if keyword:
            query = query.where(or_(getattr(model, name).contains(keyword, autoescape=True),
                                    getattr(model, code).contains(keyword, autoescape=True)))
        return paginated(db, query.order_by(model.id), page, size, lambda r: organization(r, kind))


def selected_object(user,kind,identifier):
    permission='org' if kind in ORG else 'account' if kind=='accounts' else kind
    enforce_permission(user,f'system.{permission}.view')
    with get_sessionmaker()() as db:
        if kind in ORG: model,name,code,_=ORG[kind];query=org_query(db,user,kind,include_parents=True)
        elif kind=='accounts': model,name,code=User,'real_name','login_name';query=scoped_accounts(db,user)
        elif kind=='student': model,name,code=StudentProfile,'real_name','student_no';query=scoped_students(db,user)
        else: model,name,code=StaffProfile,'real_name','staff_no';query=scoped_staff(db,user)
        item=db.scalar(query.where(model.id==int(identifier)))
        if not item: raise not_found('该对象不存在或已不在可见范围内')
        return {'id':str(item.id),'name':getattr(item,name),'code':getattr(item,code)}


def organization_impact_in_session(db,user,kind,item):
    import hashlib,json
    major_ids=tenant_query(Major,user).where(Major.college_id==item.id if kind=='colleges' else Major.id==item.id if kind=='majors' else false()).with_only_columns(Major.id)
    class_ids=tenant_query(SchoolClass,user).where(SchoolClass.id==item.id if kind=='classes' else SchoolClass.major_id.in_(major_ids)).with_only_columns(SchoolClass.id)
    students=scoped_students(db,user).where(or_(StudentProfile.class_id.in_(class_ids),StudentProfile.major_id.in_(major_ids),
        StudentProfile.college_id==item.id if kind=='colleges' else false())).with_only_columns(StudentProfile.id)
    staff=scoped_staff(db,user).where(StaffProfile.college_id==item.id if kind=='colleges' else StaffProfile.department_id==item.id if kind=='departments' else false())
    records=tenant_query(InternshipRecord,user).where(or_(InternshipRecord.student_id.in_(students),InternshipRecord.advisor_user_id.in_(staff.with_only_columns(StaffProfile.user_id))))
    todos=tenant_query(UnifiedTodo,user).where(UnifiedTodo.status=='PENDING',or_(UnifiedTodo.student_id.in_(students),UnifiedTodo.assignee_id.in_(staff.with_only_columns(StaffProfile.user_id))))
    if not school_wide(user):
        visible=scoped_students(db,user).with_only_columns(StudentProfile.id)
        records=records.where(InternshipRecord.student_id.in_(visible));todos=todos.where(UnifiedTodo.student_id.in_(visible))
    scopes=tenant_query(TeacherStudentScope,user).where(or_(
        and_(TeacherStudentScope.scope_type=='COLLEGE',TeacherStudentScope.ref_id==item.id) if kind=='colleges' else false(),
        and_(TeacherStudentScope.scope_type=='MAJOR',TeacherStudentScope.ref_id.in_(major_ids)),
        and_(TeacherStudentScope.scope_type=='CLASS',TeacherStudentScope.ref_id.in_(class_ids))))
    def count(query):return db.scalar(select(func.count()).select_from(query.subquery()))
    counts={'下级组织':(count(major_ids) if kind=='colleges' else 0)+(count(class_ids) if kind in {'colleges','majors'} else 0),
        '学生主档':count(students),'教职工资料':count(staff),'责任关系（含历史）':count(scopes),
        '关联实习记录':count(records),'未完成待办':count(todos)}
    fingerprint=hashlib.sha256(json.dumps([ids(user)[0],kind,item.id,item.version,counts],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'items':[{'name':name,'count':value} for name,value in counts.items()], 'hasReferences':any(counts.values()),'fingerprint':fingerprint,
        'parentId':str(getattr(item,ORG[kind][3]) or '') if ORG[kind][3] else '',
        'note':'停用仅停止该组织用于新建资料，不删除下级组织、师生、实习或历史责任；现有账号和待办不会自动停用或交接。'}


def organization_impact(user,kind,identifier):
    enforce_permission(user,'system.org.view')
    with get_sessionmaker()() as db:
        model=ORG[kind][0]
        item=db.scalar(org_query(db,user,kind).where(model.id==int(identifier)))
        if not item:raise not_found()
        return organization_impact_in_session(db,user,kind,item)


def save_organization(user, kind, data, identifier=None):
    with transaction(user, 'system.org.manage') as db:
        model, name, code, parent = ORG[kind]
        if identifier:
            item = db.scalar(org_query(db, user, kind).where(model.id == int(identifier)).with_for_update())
            if not item:
                raise not_found()
            edit_version(item.version, data['expectedVersion'], organization(item, kind))
            if data['status']=='DISABLED' and item.status!='DISABLED':
                impact=organization_impact_in_session(db,user,kind,item)
                if impact['hasReferences'] and (not data.get('confirmImpact') or data.get('impactFingerprint')!=impact['fingerprint']):
                    raise AppException('IMPACT_REVIEW_REQUIRED','组织仍有引用，或引用数量已变化，请重新核对后明确确认停用',http_status=409)
        else:
            if kind in {'colleges', 'departments'} and not school_wide(user):
                raise no_permission('只有校级负责人员可新增院系或校内部门')
            item = model(tenant_id=ids(user)[0]); db.add(item)
        before = organization(item, kind) if identifier else None
        moved_students = 0
        duplicate = db.scalar(tenant_query(model, user).where(getattr(model, code) == data['code'],
                                                             model.id != (item.id or 0)))
        if duplicate:
            raise AppException('DATA_CONFLICT', '组织代码已存在，请打开原组织维护', http_status=409)
        if parent:
            parent_kind = 'colleges' if kind == 'majors' else 'majors'
            parent_model = ORG[parent_kind][0]
            parent_row = db.scalar(org_query(db, user, parent_kind,include_parents=bool(identifier and str(getattr(item,parent))==data['parentId'])).where(
                parent_model.id == int(data['parentId'] or 0)))
            if not parent_row:
                raise no_permission('上级组织不存在、已停用或超出负责范围')
            moving = bool(identifier and getattr(item, parent) != parent_row.id)
            if parent_row.status!='ACTIVE' and (not identifier or moving or (data['status']=='ACTIVE' and item.status!='ACTIVE')):
                raise no_permission('上级组织已停用，不能新增或启用下级组织')
            if moving:
                impact=organization_impact_in_session(db,user,kind,item)
                if not data.get('confirmImpact') or data.get('impactFingerprint')!=impact['fingerprint']:
                    raise AppException('IMPACT_REVIEW_REQUIRED','请重新核对组织归属调整影响并明确确认；当前学生归属将同步，历史实习和原待办责任保留',http_status=409)
                college=parent_row if kind=='majors' else row(db,College,parent_row.college_id,user)
                if college.status!='ACTIVE': raise no_permission('目标院系已停用，不能调整组织归属')
                if kind=='majors':
                    children=tenant_query(SchoolClass,user).where(SchoolClass.major_id==item.id).with_only_columns(SchoolClass.id)
                    affected=or_(StudentProfile.major_id==item.id,StudentProfile.class_id.in_(children))
                else:
                    affected=StudentProfile.class_id==item.id
                moved_students=db.execute(update(StudentProfile).where(StudentProfile.tenant_id==ids(user)[0],
                    StudentProfile.is_deleted.is_(False),affected).values(college_id=college.id,
                    major_id=item.id if kind=='majors' else parent_row.id,version=StudentProfile.version+1)).rowcount
            setattr(item, parent, parent_row.id)
        setattr(item, name, data['name']); setattr(item, code, data['code'])
        item.status = data['status']
        if kind == 'majors':
            item.education_years, item.training_level = data['educationYears'], data['trainingLevel']
            item.national_code = data.get('nationalCode') or None
        if kind == 'classes':
            item.grade = data['grade']
        item.version = (item.version or 0) + 1
        db.flush()
        result = organization(item, kind)
        audit(db, user, 'ORG_SAVE', kind, item.id, {'before': before, 'after': result, 'reason': data['reason'], 'updatedStudentCount':moved_students})
        if parent and moving: result['message']=f'组织归属已调整，已同步{moved_students}名学生当前归属；历史实习和待办责任保留，请到责任交接核对在办事项'
        return result


def people_query(db, user, kind, keyword='', account_status=''):
    model = StudentProfile if kind == 'student' else StaffProfile
    query = scoped_students(db, user) if kind == 'student' else scoped_staff(db, user)
    number = model.student_no if kind == 'student' else model.staff_no
    if keyword:
        query = query.where(or_(model.real_name.contains(keyword, autoescape=True), number.contains(keyword, autoescape=True)))
    if account_status:
        linked = select(StudentAccountLink.id).where(StudentAccountLink.tenant_id==ids(user)[0],
            StudentAccountLink.student_id==StudentProfile.id,StudentAccountLink.link_status=='ACTIVE',
            StudentAccountLink.is_deleted.is_(False)).exists() if kind=='student' else StaffProfile.user_id.is_not(None)
        query = query.where(linked if account_status=='BOUND' else ~linked)
    return query


def list_people(user, kind, page=1, size=30, keyword='', account_status='', object_ids=None):
    enforce_permission(user, f'system.{kind}.view')
    with get_sessionmaker()() as db:
        model = StudentProfile if kind == 'student' else StaffProfile
        query = people_query(db, user, kind, keyword, account_status)
        if object_ids is not None: query=query.where(model.id.in_(object_ids))
        page_ids=query.with_only_columns(model.id).order_by(model.id).limit(size).offset((page-1)*size).subquery()
        bindings=dict(db.execute(select(StudentAccountLink.student_id,StudentAccountLink.user_id).where(
            StudentAccountLink.tenant_id==ids(user)[0],StudentAccountLink.student_id.in_(select(page_ids.c.id)),
            StudentAccountLink.link_status=='ACTIVE',StudentAccountLink.is_deleted.is_(False))).all()) if kind=='student' else {}
        people=db.scalars(query.order_by(model.id).limit(size).offset((page-1)*size)).all()
        names={};codes={}
        for field,org_model,label in [('college_id',College,'college_name'),('major_id',Major,'major_name'),
                                     ('class_id',SchoolClass,'class_name'),('department_id',SchoolDepartment,'name')]:
            refs={getattr(p,field,None) for p in people}-{None}
            code=SchoolClass.class_code if org_model is SchoolClass else org_model.code
            rows=db.execute(select(org_model.id,getattr(org_model,label),code).where(
                org_model.tenant_id==ids(user)[0],org_model.id.in_(refs))).all() if refs else []
            names[field]={r[0]:r[1] for r in rows};codes[field]={r[0]:r[2] for r in rows}
        contacts={}
        if kind=='student':
            for contact in db.scalars(tenant_query(StudentContact,user).where(StudentContact.student_id.in_([p.id for p in people]),
                    StudentContact.contact_type=='PHONE').order_by(StudentContact.is_primary.desc(),StudentContact.id.desc())):
                contacts.setdefault(contact.student_id,contact.contact_value_encrypted)
        def serialize(item):
            user_id = item.user_id if kind == 'staff' else bindings.get(item.id)
            return {**common(item), 'number': getattr(item, 'student_no' if kind == 'student' else 'staff_no'),
                'name': item.real_name, 'collegeId': str(item.college_id or ''),
                'majorId': str(getattr(item, 'major_id', '') or ''), 'classId': str(getattr(item, 'class_id', '') or ''),
                'departmentId': str(getattr(item, 'department_id', '') or ''), 'grade': getattr(item, 'grade', '') or '',
                **{key:codes[field].get(getattr(item,field,None),'') or '' for key,field in (
                    ('collegeCode','college_id'),('majorCode','major_id'),('classCode','class_id'),('departmentCode','department_id'))},
                'userId': str(user_id or ''), 'accountLabel': '已绑定' if user_id else '尚未开通',
                'organizationLabel': ' / '.join(names[field].get(getattr(item,field,None),'') for field in names if names[field].get(getattr(item,field,None))),
                'phone': mask_phone_encrypted(contacts.get(item.id) if kind=='student' else item.phone_encrypted)}
        return paginated(db, query.order_by(model.id), page, size, serialize)


def person_state(item):
    return {'name':item.real_name,'status':item.status,
        **{key:str(getattr(item,field,None) or '') for key,field in (
            ('collegeId','college_id'),('majorId','major_id'),('classId','class_id'),('departmentId','department_id'))},
        'grade':getattr(item,'grade','') or ''}


def save_person(user, kind, identifier, data):
    with transaction(user, f'system.{kind}.manage') as db:
        model = StudentProfile if kind == 'student' else StaffProfile
        query = scoped_students(db, user) if kind == 'student' else scoped_staff(db, user)
        item = db.scalar(query.where(model.id == int(identifier)).with_for_update())
        if not item:
            raise not_found()
        edit_version(item.version, data['expectedVersion'], person_state(item))
        changed_org = str(item.college_id or '') != data['collegeId'] or (kind == 'student' and str(item.class_id or '') != data['classId']) or (kind=='staff' and str(item.department_id or '')!=data['departmentId'])
        if changed_org and not data['confirmImpact']:
            raise AppException('IMPACT_REVIEW_REQUIRED', '请先核对组织调整对管理范围和在办实习的影响', http_status=409)
        college = db.scalar(org_query(db, user, 'colleges',include_parents=kind=='student').where(College.id == int(data['collegeId'] or 0)))
        if not college and (kind=='student' or data['collegeId'] or not data.get('departmentId')):
            raise no_permission('院系不存在或超出负责范围')
        if changed_org and college and college.status != 'ACTIVE':
            raise no_permission('院系已停用，不能将人员调入该组织')
        before = person_state(item)
        if kind == 'student':
            class_row = db.scalar(org_query(db,user,'classes').where(SchoolClass.id==int(data['classId'] or 0)))
            if not class_row: raise no_permission('班级不存在或超出负责范围')
            major = row(db, Major, class_row.major_id, user)
            if major.college_id != college.id:
                raise AppException('VALIDATION_ERROR', '班级、专业和院系归属不一致')
            if changed_org and (class_row.status != 'ACTIVE' or major.status != 'ACTIVE'):
                raise AppException('VALIDATION_ERROR', '班级或专业已停用，不能将学生调入该组织')
            item.class_id, item.major_id, item.grade = class_row.id, major.id, data['grade']
        else:
            if data.get('phone'):
                item.phone_encrypted = encrypt_field(data['phone'])
            if data.get('departmentId'):
                department = row(db, SchoolDepartment, data['departmentId'], user)
                if changed_org and department.status != 'ACTIVE':
                    raise AppException('VALIDATION_ERROR', '部门已停用，不能将人员调入该组织')
                item.department_id = department.id
            else:
                item.department_id = None
        if item.real_name != data['name']:
            account_id = item.user_id if kind == 'staff' else db.scalar(tenant_query(StudentAccountLink,user).where(
                StudentAccountLink.student_id==item.id,StudentAccountLink.link_status=='ACTIVE').with_only_columns(StudentAccountLink.user_id))
            if account_id:
                account = row(db,User,account_id,user,lock=True)
                if account.user_type != ('STUDENT' if kind=='student' else 'TEACHER'):
                    raise AppException('DATA_CONFLICT','人员绑定的账号身份不一致，请先核对绑定后再更正姓名',http_status=409)
                account.real_name=data['name'];account.version=(account.version or 0)+1
        item.real_name, item.college_id, item.status = data['name'], college.id if college else None, data['status']
        item.version += 1
        audit(db, user, 'PERSON_SAVE', kind, item.id, {'before': before, 'after':person_state(item), 'reason': data['reason']})
        return {'id': str(item.id), 'version': item.version, 'message': '资料已更新，历史实习记录和职责保持原记录'}


def impact(user, kind, identifier):
    from app.models import InternshipBatch
    enforce_permission(user, f'system.{kind}.view')
    with get_sessionmaker()() as db:
        if kind == 'student':
            person = db.scalar(scoped_students(db, user).where(StudentProfile.id == int(identifier)))
            if not person: raise not_found()
            records = tenant_query(InternshipRecord, user).where(InternshipRecord.student_id == person.id)
            todos = tenant_query(UnifiedTodo, user).where(UnifiedTodo.student_id == person.id, UnifiedTodo.status == 'PENDING')
            scope_filter=or_(*[and_(TeacherStudentScope.scope_type==key,TeacherStudentScope.ref_id==value)
                for key,value in [('COLLEGE',person.college_id),('MAJOR',person.major_id),('CLASS',person.class_id),('STUDENT',person.id)] if value])
        else:
            person = db.scalar(scoped_staff(db, user).where(StaffProfile.id == int(identifier)))
            if not person: raise not_found()
            records = tenant_query(InternshipRecord, user).where(InternshipRecord.advisor_user_id == person.user_id if person.user_id else false())
            todos = tenant_query(UnifiedTodo, user).where(UnifiedTodo.assignee_id == person.user_id if person.user_id else false(), UnifiedTodo.status == 'PENDING')
            scope_filter=TeacherStudentScope.user_id==person.user_id if person.user_id else false()
        scopes=tenant_query(TeacherStudentScope,user).where(scope_filter,TeacherStudentScope.status=='ACTIVE')
        if not school_wide(user):
            visible_students=scoped_students(db,user).with_only_columns(StudentProfile.id)
            records=records.where(InternshipRecord.student_id.in_(visible_students))
            todos=todos.where(UnifiedTodo.student_id.in_(visible_students))
            scopes=scopes.where(or_(*[and_(TeacherStudentScope.scope_type==key,TeacherStudentScope.ref_id.in_(
                org_query(db,user,org_kind).with_only_columns(ORG[org_kind][0].id)))
                for key,org_kind in [('COLLEGE','colleges'),('MAJOR','majors'),('CLASS','classes')]],
                and_(TeacherStudentScope.scope_type=='STUDENT',TeacherStudentScope.ref_id.in_(scoped_students(db,user).with_only_columns(StudentProfile.id)))))
        batches=tenant_query(InternshipBatch,user).where(InternshipBatch.id.in_(records.with_only_columns(InternshipRecord.batch_id)))
        return {'internshipCount': db.scalar(select(func.count()).select_from(records.subquery())),
                'pendingCount': db.scalar(select(func.count()).select_from(todos.subquery())),
                'batchCount':db.scalar(select(func.count()).select_from(batches.subquery())),
                'batches':[{'id':str(r.id),'name':r.batch_name} for r in db.scalars(batches.order_by(InternshipBatch.id).limit(30))],
                'scopeCount':db.scalar(select(func.count()).select_from(scopes.subquery())),
                'serviceResponsibilityCount':db.scalar(select(func.count()).select_from(SchoolSetting).where(
                    SchoolSetting.tenant_id==ids(user)[0],SchoolSetting.is_deleted.is_(False),SchoolSetting.setting_key=='notification',
                    SchoolSetting.value_json['responsibleUserId'].as_string()==str(person.user_id))) if kind=='staff' and person.user_id else 0,
                'responsibilities':scope_rows(db,user,db.scalars(scopes.order_by(TeacherStudentScope.id).limit(30)).all()),
                'note': '组织调整会改变后续数据可见范围；实习导师和在办承办人必须分别办理交接。批次和责任关系各展示前30项。'}


def list_accounts(user, page=1, size=30, keyword=''):
    enforce_permission(user, 'system.account.view')
    with get_sessionmaker()() as db:
        query = scoped_accounts(db, user)
        if keyword:
            query = query.where(or_(User.login_name.contains(keyword, autoescape=True), User.real_name.contains(keyword, autoescape=True)))
        page_ids=query.with_only_columns(User.id).order_by(User.id).limit(size).offset((page-1)*size).subquery()
        roles={}
        for uid,role in db.execute(select(UserRole.user_id,Role).join(Role,Role.id==UserRole.role_id).where(
            UserRole.tenant_id==ids(user)[0],UserRole.user_id.in_(select(page_ids.c.id)),UserRole.status=='ACTIVE',
            UserRole.is_deleted.is_(False),Role.tenant_id==ids(user)[0],Role.status=='ACTIVE',Role.is_deleted.is_(False))):
            roles.setdefault(uid,[]).append({'id':str(role.id),'name':role.role_name})
        return paginated(db, query.order_by(User.id), page, size, lambda r: {**common(r),
            'statusLabel':'有效期已结束' if r.status=='ACTIVE' and r.expires_at and r.expires_at<=datetime.utcnow() else STATUS_LABELS.get(r.status,'待核对'),
            'loginName': r.login_name, 'name': r.real_name, 'userType': r.user_type,
            'typeLabel': {'STUDENT': '学生', 'TEACHER': '教职工', 'SCHOOL_ADMIN': '学校管理人员',
                          'ENTERPRISE_MENTOR': '企业导师'}.get(r.user_type, '校内人员'),
            'roles': roles.get(r.id,[]),
            'mustChangePassword': r.must_change_password, 'expiresAt': r.expires_at.isoformat()+'Z' if r.expires_at else None,
            'phone': mask_phone_encrypted(r.phone_encrypted), 'lastLoginAt': r.last_login_at})


def protect_last_admin(db, user):
    db.flush()
    candidates = db.scalars(tenant_query(User, user).join(UserRole, and_(UserRole.user_id == User.id,
        UserRole.tenant_id == User.tenant_id)).join(Role, and_(Role.id == UserRole.role_id, Role.tenant_id == User.tenant_id))
        .where(User.status == 'ACTIVE', or_(User.expires_at.is_(None), User.expires_at > datetime.utcnow()),
        UserRole.status == 'ACTIVE', UserRole.is_deleted.is_(False), Role.status == 'ACTIVE',
        Role.is_deleted.is_(False), Role.base_role_code == 'SYSTEM_ADMIN')).unique().all()
    for candidate in candidates:
        for role in active_roles(db, ids(user)[0], candidate.id):
            grants = role_permissions(db, role)
            if role.base_role_code == 'SYSTEM_ADMIN' and all(any(_matches(p, needed) for p in grants)
                for needed in ('system.account.manage', 'system.role.manage')):
                return
    raise AppException('LAST_ADMIN_REQUIRED', '必须保留至少一位有效且具备账号与角色维护权的学校系统管理员', http_status=409)


def account_action(user, identifier, data):
    permission = 'system.account.reset' if data['action'] == 'RESET' else 'system.account.manage'
    with transaction(user, permission) as db:
        account = db.scalar(scoped_accounts(db, user).where(User.id == int(identifier)).with_for_update())
        if not account: raise not_found()
        edit_version(account.version, data['expectedVersion'], {'name':account.real_name,'status':account.status,
            'expiresAt':account.expires_at.isoformat()+'Z' if account.expires_at else None})
        if account.user_type.startswith('ENTERPRISE'):
            raise no_permission('企业账号的启停与重置请通过企业成员授权入口办理')
        before={'status':account.status,'expiresAt':account.expires_at.isoformat()+'Z' if account.expires_at else None}
        result = {'id': str(account.id)}
        if data['action'] == 'RESET':
            password = 'Aa9!' + secrets.token_urlsafe(15)
            account.password_hash, account.must_change_password = hash_password(password), True
            result['temporaryPassword'] = password
        elif data['action'] in {'ENABLE', 'UNLOCK', 'DISABLE'}:
            allowed_states = {'ENABLE': {'DISABLED'}, 'UNLOCK': {'LOCKED'}, 'DISABLE': {'ACTIVE', 'LOCKED'}}
            if account.status not in allowed_states[data['action']]:
                raise AppException('ACCOUNT_STATUS_CONFLICT', {
                    'ENABLE': '只有已停用账号可启用；锁定账号请办理解锁',
                    'UNLOCK': '只有已锁定账号可解锁；停用账号请明确办理启用',
                    'DISABLE': '只有正常或锁定账号可停用',
                }[data['action']], http_status=409)
            account.status = 'DISABLED' if data['action'] == 'DISABLE' else 'ACTIVE'
        elif data['action'] == 'EXPIRY':
            account.expires_at = data['expiresAt']
        account.version += 1; account.credential_version += 1
        protect_last_admin(db, user)
        pending = db.scalar(select(func.count()).select_from(tenant_query(UnifiedTodo, user).where(
            UnifiedTodo.assignee_id == account.id, UnifiedTodo.status == 'PENDING').subquery()))
        audit(db, user, 'ACCOUNT_' + data['action'], 'account', account.id, {'reason': data['reason'],
            'before':before,'after':{'status':account.status,'expiresAt':account.expires_at.isoformat()+'Z' if account.expires_at else None},
            'status': account.status, 'pendingCount': pending})
        return {**result, 'version': account.version, 'pendingCount': pending,
                'message': '账号已更新；原登录会话失效，未交接事项仍保留在原办理记录中'}


def list_roles(user):
    enforce_permission(user, 'system.role.view')
    with get_sessionmaker()() as db:
        catalog = [{'code': p.permission_code, 'name': permission_name(p.permission_code,p.permission_name)} for p in db.scalars(
            select(Permission).where(~Permission.permission_code.contains('*'),
                ~Permission.permission_code.endswith('.')).order_by(Permission.permission_code))]
        presets = preset_role_patterns()
        roles = db.scalars(tenant_query(Role, user).order_by(Role.id)).all()
        grants={};members={}
        for rid,code in db.execute(select(RolePermission.role_id,Permission.permission_code).join(Permission,
            Permission.id==RolePermission.permission_id).where(RolePermission.tenant_id==ids(user)[0],
            RolePermission.status=='ACTIVE',RolePermission.is_deleted.is_(False))): grants.setdefault(rid,[]).append(code)
        members=dict(db.execute(select(UserRole.role_id,func.count()).where(UserRole.tenant_id==ids(user)[0],
            UserRole.status=='ACTIVE',UserRole.is_deleted.is_(False)).group_by(UserRole.role_id)).all())
        return {'items': [{**common(r), 'code': r.role_code, 'name': r.role_name,
            'baseRole': r.base_role_code or r.role_code, 'baseLabel': ROLE_NAMES.get(r.base_role_code or r.role_code, '历史身份'),
            'permissions': grants.get(r.id,[]), 'memberCount': members.get(r.id,0)} for r in roles],
            'catalog': catalog,
            'templates': [{'code': k, 'name': v, 'permissions': [p['code'] for p in catalog
                if any(_matches(pattern,p['code']) for pattern in presets.get(k,set()))]}
                for k, v in ROLE_NAMES.items() if k != 'STUDENT']}


def role_change_impact(db,user,role_code,role_id=None,user_id=None):
    from app.models.approval import WorkflowTask, WorkflowInstance
    from app.services.system_leave_policy import available_task_ids
    members=tenant_query(User,user).join(UserRole,and_(UserRole.user_id==User.id,UserRole.tenant_id==User.tenant_id)).where(
        UserRole.role_id==role_id,UserRole.status=='ACTIVE',UserRole.is_deleted.is_(False))
    tasks=tenant_query(WorkflowTask,user).join(WorkflowInstance,WorkflowInstance.id==WorkflowTask.instance_id).where(
        WorkflowTask.assignee_role_code==role_code,WorkflowTask.status.in_(['PENDING','WAITING']),
        WorkflowInstance.tenant_id==ids(user)[0],WorkflowInstance.is_deleted.is_(False),WorkflowInstance.status=='RUNNING',
        WorkflowInstance.source_module=='internship',WorkflowInstance.source_biz_type=='LEAVE')
    scopes=tenant_query(TeacherStudentScope,user).where(TeacherStudentScope.role_code==role_code,TeacherStudentScope.status=='ACTIVE')
    if user_id:
        row(db,User,user_id,user)
        members=members.where(User.id==int(user_id));tasks=tasks.where(WorkflowTask.assignee_id==int(user_id));scopes=scopes.where(TeacherStudentScope.user_id==int(user_id))
    todos=tenant_query(UnifiedTodo,user).where(UnifiedTodo.assignee_id.in_(members.with_only_columns(User.id)),
        UnifiedTodo.source_module=='internship',UnifiedTodo.status=='PENDING')
    def count(query):return db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.execute(tasks.add_columns(WorkflowInstance.source_biz_id).order_by(WorkflowTask.id).limit(30)).all()
    available=set(db.scalars(available_task_ids(ids(user)[0]).where(WorkflowTask.id.in_([r.id for r,_ in rows]))))
    names={r.id:r.real_name for r in db.scalars(tenant_query(User,user).where(User.id.in_({r.assignee_id for r,_ in rows})))}
    return {'roleId':str(role_id or ''),'userId':str(user_id or ''),'memberCount':count(members),'scopeCount':count(scopes),
        'pendingApprovalCount':count(tasks.where(WorkflowTask.status=='PENDING')),'waitingApprovalCount':count(tasks.where(WorkflowTask.status=='WAITING')),
        'blockedApprovalCount':count(tasks.where(WorkflowTask.id.not_in(available_task_ids(ids(user)[0])))),
        'memberTodoCount':count(todos),'items':[{'id':str(r.id),'objectId':str(biz_id),'assigneeName':names.get(r.assignee_id,'原人员已不可用'),
            'stage':f'第{r.sequence_no}级','statusLabel':'待重新指定责任人' if r.id not in available else '待审批' if r.status=='PENDING' else '等待前级'} for r,biz_id in rows],
        'note':'请假节点按本角色统计，最多展示前30项；成员待办可能还涉及其他身份。停用或撤权不会自动转派，失去办理资格的节点须交接。'}


def role_detail(user,identifier,section,page=1,user_id=None):
    enforce_permission(user,'system.role.view')
    with get_sessionmaker()() as db:
        role=row(db,Role,identifier,user)
        if section=='impact':return role_change_impact(db,user,role.role_code,role.id,user_id)
        if section=='members':
            query=tenant_query(User,user).join(UserRole,and_(UserRole.user_id==User.id,UserRole.tenant_id==User.tenant_id)).where(
                UserRole.role_id==role.id,UserRole.status=='ACTIVE',UserRole.is_deleted.is_(False))
            return paginated(db,query.order_by(User.id),page,30,lambda r:{'id':str(r.id),'name':r.real_name,
                'loginName':r.login_name,'statusLabel':STATUS_LABELS.get(r.status,'待核对')})
        if section=='history':
            query=select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==ids(user)[0],
                SecurityAuditLog.resource=='role',SecurityAuditLog.resource_id==str(role.id))
            return paginated(db,query.order_by(SecurityAuditLog.id.desc()),page,30,lambda r:{'id':str(r.id),
                'name':r.operator_name,'reason':(r.detail_json or {}).get('reason',''),
                'statusLabel':'权限调整' if r.action=='ROLE_SAVE' else '成员调整','createdAt':r.created_at})
        query=tenant_query(TeacherStudentScope,user).where(TeacherStudentScope.role_code==role.role_code)
        items=db.scalars(query.order_by(TeacherStudentScope.id).limit(30).offset((page-1)*30)).all()
        return {'items':scope_rows(db,user,items),'total':db.scalar(select(func.count()).select_from(query.subquery()))}


def save_role(user, data, identifier=None):
    with transaction(user, 'system.role.manage') as db:
        if base_role(user) != 'SYSTEM_ADMIN':
            raise no_permission('只有学校系统管理身份可维护角色授权')
        if data['baseRole'] not in ROLE_NAMES or data['baseRole'] == 'STUDENT':
            raise no_permission('学生和企业身份不可复制成学校管理角色')
        requested = set(data['permissions'])
        catalog = {p.permission_code: p for p in db.scalars(select(Permission))}
        if requested - catalog.keys() or any('*' in p or p.endswith('.') for p in requested):
            raise no_permission('请选择逐项业务权限，不能创建通配授权')
        grantable = {code for code in catalog if has_permission(user, code)}
        if has_permission(user, 'system.role.grant-business'):
            grantable.update(code for code in catalog if code.startswith('internship.'))
        if has_permission(user, 'system.role.grant-admin'):
            grantable.update(code for code in catalog if code.startswith('system.'))
        if requested - grantable:
            raise no_permission('所选权限超出当前身份的授权能力')
        if data['baseRole'] != 'SYSTEM_ADMIN' and any(p.startswith('system.role.') or p == 'system.account.manage' for p in requested):
            raise no_permission('账号与角色授权能力只能授予学校系统管理身份')
        if not data['sensitiveConfirmed'] and any('sensitive' in p or p.endswith('.reset') for p in requested):
            raise AppException('VALIDATION_ERROR', '请逐项确认敏感查看与密码重置权限')
        if identifier:
            target = row(db, Role, identifier, user, True)
            edit_version(target.version, data['expectedVersion'], {'name':target.role_name,'status':target.status,
                'permissions':list(role_permissions(db,target))})
            if target.base_role_code != data['baseRole']:
                raise no_permission('已有角色不能改变身份类型，请另建角色')
        else:
            target = Role(tenant_id=ids(user)[0], role_code='CUSTOM_' + secrets.token_hex(8).upper(),
                          role_name=data['name'], role_type='CUSTOM', base_role_code=data['baseRole']); db.add(target); db.flush()
        before = set(role_permissions(db, target))
        before_fields={'name':target.role_name,'status':target.status} if identifier else {}
        target.role_name, target.status = data['name'], data['status']; target.version = (target.version or 0) + 1
        links = {r.permission_id: r for r in db.scalars(tenant_query(RolePermission, user).where(RolePermission.role_id == target.id))}
        for code, permission in catalog.items():
            if permission.id in links:
                links[permission.id].status = 'ACTIVE' if code in requested else 'DISABLED'
            elif code in requested:
                db.add(RolePermission(tenant_id=ids(user)[0], role_id=target.id, permission_id=permission.id, status='ACTIVE'))
        protect_last_admin(db, user)
        audit(db, user, 'ROLE_SAVE', 'role', target.id, {'added': sorted(requested-before),
            'removed': sorted(before-requested), 'reason': data['reason'], 'status': target.status,
            'before':before_fields,'after':{'name':target.role_name,'status':target.status}})
        return {'id': str(target.id), 'version': target.version}


def role_member(user, identifier, data):
    with transaction(user, 'system.role.manage') as db:
        if base_role(user) != 'SYSTEM_ADMIN': raise no_permission('仅学校系统管理员可分配管理身份')
        target = row(db, Role, identifier, user, True)
        edit_version(target.version, data['expectedVersion'], {'name':target.role_name,'status':target.status,
            'permissions':list(role_permissions(db,target))})
        account = row(db, User, data['userId'], user)
        if data['enabled']:
            for code in role_permissions(db,target):
                business=code.startswith('internship.') and has_permission(user,'system.role.grant-business')
                admin=code.startswith('system.') and has_permission(user,'system.role.grant-admin')
                if not (business or admin or has_permission(user,code)):
                    raise no_permission('该角色包含超出本人授权能力的权限，不能分配其成员')
        if target.base_role_code == 'STUDENT' or (data['enabled'] and account.user_type not in {'SCHOOL_ADMIN','TEACHER'}):
            raise no_permission('校内管理身份只能分配给学校管理人员或教师')
        link = db.scalar(select(UserRole).where(UserRole.tenant_id == ids(user)[0], UserRole.role_id == target.id,
                                              UserRole.user_id == account.id).with_for_update())
        was_enabled=bool(link and link.status=='ACTIVE' and not link.is_deleted)
        if not link:
            link = UserRole(tenant_id=ids(user)[0], role_id=target.id, user_id=account.id); db.add(link)
        link.status, link.is_deleted = ('ACTIVE' if data['enabled'] else 'DISABLED'), False
        target.version += 1; account.version += 1
        protect_last_admin(db, user)
        audit(db, user, 'ROLE_MEMBER', 'role', target.id, {'userId': str(account.id),
            'enabled': data['enabled'], 'reason': data['reason'],
            'before':{'enabled':was_enabled},'after':{'enabled':data['enabled'],'userId':str(account.id),'memberName':account.real_name,'roleName':target.role_name}})
        return {'id': str(target.id), 'version': target.version}


def scope_rows(db,user,items):
    accounts={r.id:r.real_name for r in db.scalars(tenant_query(User,user).where(User.id.in_({r.user_id for r in items})))}
    refs={}
    for kind,model,name in [('COLLEGE',College,'college_name'),('MAJOR',Major,'major_name'),('CLASS',SchoolClass,'class_name'),('STUDENT',StudentProfile,'real_name')]:
        refs[kind]={r.id:getattr(r,name) for r in db.scalars(tenant_query(model,user).where(model.id.in_({r.ref_id for r in items if r.scope_type==kind})))}
    def serialize(r):
        label=refs.get(r.scope_type,{}).get(r.ref_id)
        return {**common(r), 'userId': str(r.user_id or ''), 'name': accounts.get(r.user_id,r.teacher_name), 'roleCode': r.role_code,
                'scopeType': r.scope_type, 'refId': str(r.ref_id or ''), 'refName': label or r.ref_value, 'object': label or r.ref_value,
                'kind': {'COLLEGE':'院系','MAJOR':'专业','CLASS':'班级','STUDENT':'学生'}.get(r.scope_type,'待核对'),
                'needsReview': r.status=='REVIEW' or not (r.user_id and r.ref_id)}
    return [serialize(r) for r in items]


def scope_review_condition():
    return and_(TeacherStudentScope.status!='DISABLED',or_(TeacherStudentScope.status=='REVIEW',
        TeacherStudentScope.user_id.is_(None),TeacherStudentScope.ref_id.is_(None)))


def list_scopes(user, page=1, size=30, issue_page=1, issue_type='', scope_type='', ref_id='', review_only=False, blocked_page=1):
    enforce_permission(user, 'system.scope.view')
    if not school_wide(user): raise no_permission('责任配置查询限校级授权人员')
    with get_sessionmaker()() as db:
        query=tenant_query(TeacherStudentScope,user).order_by(TeacherStudentScope.id)
        if review_only: query=query.where(scope_review_condition())
        selected=None
        if scope_type and ref_id:
            model,label,_,_=ORG[{'COLLEGE':'colleges','MAJOR':'majors','CLASS':'classes'}[scope_type]]
            target=row(db,model,ref_id,user)
            selected={'scopeType':scope_type,'refId':str(target.id),'name':getattr(target,label)}
            query=query.where(TeacherStudentScope.scope_type==scope_type,TeacherStudentScope.ref_id==target.id)
        items=db.scalars(query.limit(size).offset((page-1)*size)).all()
        return {'items':scope_rows(db,user,items),'total':db.scalar(select(func.count()).select_from(query.subquery())),
            'selectedObject':selected,'responsibilityCheck':responsibility_gaps(db,user,issue_page,30,issue_type),'blockedTasks':blocked_tasks(db,user,blocked_page)}


def blocked_tasks(db,user,page=1,size=30):
    from app.models.approval import WorkflowInstance, WorkflowTask
    from app.services.system_leave_policy import available_task_ids
    from app.modules.internship.services.internship_todo_helper import ADVISOR_TODO_PERMISSIONS
    revoked_advisor=[]
    for permission,types in ADVISOR_TODO_PERMISSIONS.items():
        parts=permission.split('.')
        patterns=['*',permission,*['.'.join(parts[:n])+'.*' for n in range(1,len(parts))]]
        permitted=select(UserRole.id).join(Role,Role.id==UserRole.role_id).join(
            RolePermission,RolePermission.role_id==Role.id).join(Permission,Permission.id==RolePermission.permission_id).where(
            UserRole.tenant_id==ids(user)[0],UserRole.user_id==UnifiedTodo.assignee_id,
            UserRole.status=='ACTIVE',UserRole.is_deleted.is_(False),Role.tenant_id==ids(user)[0],
            Role.status=='ACTIVE',Role.is_deleted.is_(False),RolePermission.tenant_id==ids(user)[0],
            RolePermission.status=='ACTIVE',RolePermission.is_deleted.is_(False),Permission.permission_code.in_(patterns)
        ).correlate(UnifiedTodo).exists()
        revoked_advisor.append(and_(UnifiedTodo.todo_type.in_(types),~permitted))
    revoked=select(WorkflowTask.id).join(WorkflowInstance,WorkflowInstance.id==WorkflowTask.instance_id).where(
        WorkflowTask.tenant_id==ids(user)[0],WorkflowTask.is_deleted.is_(False),WorkflowTask.status=='PENDING',
        WorkflowTask.assignee_id==UnifiedTodo.assignee_id,WorkflowInstance.tenant_id==ids(user)[0],
        WorkflowInstance.is_deleted.is_(False),WorkflowInstance.status=='RUNNING',WorkflowInstance.source_module=='internship',
        WorkflowInstance.source_biz_type=='LEAVE',WorkflowInstance.source_biz_id==UnifiedTodo.source_biz_id,
        WorkflowTask.id.not_in(available_task_ids(ids(user)[0]))).correlate(UnifiedTodo).exists()
    query=tenant_query(UnifiedTodo,user).outerjoin(User,and_(User.id==UnifiedTodo.assignee_id,User.tenant_id==UnifiedTodo.tenant_id)).where(
        UnifiedTodo.source_module=='internship',UnifiedTodo.status=='PENDING',or_(User.id.is_(None),User.is_deleted.is_(True),
        User.status!='ACTIVE',User.expires_at<=datetime.utcnow(),and_(UnifiedTodo.source_biz_type=='INTERN_LEAVE',revoked),*revoked_advisor))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(UnifiedTodo.id).offset((page-1)*size).limit(size)).all()
    paths={}
    from app.models import InternshipLeave
    from app.modules.internship.services.internship_todo_helper import advisor_todo_sources,TODO_LEAVE
    leaves=[r for r in rows if r.todo_type==TODO_LEAVE and r.source_biz_type=='INTERN_LEAVE']
    if leaves:
        targets=select(WorkflowTask.id,WorkflowTask.assignee_id,InternshipLeave.id,InternshipRecord.batch_id).join(
            WorkflowInstance,WorkflowInstance.id==WorkflowTask.instance_id).join(InternshipLeave,InternshipLeave.id==WorkflowInstance.source_biz_id).join(
            InternshipRecord,InternshipRecord.id==InternshipLeave.internship_id).where(
            WorkflowTask.tenant_id==ids(user)[0],WorkflowTask.is_deleted.is_(False),WorkflowTask.status=='PENDING',
            WorkflowTask.assignee_id.in_({r.assignee_id for r in leaves}),WorkflowInstance.tenant_id==ids(user)[0],
            WorkflowInstance.is_deleted.is_(False),WorkflowInstance.status=='RUNNING',WorkflowInstance.source_module=='internship',
            WorkflowInstance.source_biz_type=='LEAVE',InternshipLeave.tenant_id==ids(user)[0],InternshipLeave.is_deleted.is_(False),
            InternshipLeave.id.in_({r.source_biz_id for r in leaves}),InternshipRecord.tenant_id==ids(user)[0],InternshipRecord.is_deleted.is_(False))
        for task_id,actor,leave_id,batch_id in db.execute(targets):
            for item in leaves:
                if (item.source_biz_id,item.assignee_id)==(leave_id,actor):
                    paths[item.id]=(f'/admin/system/scopes?blocked=1&blockedPage={page}&handoffBatchId={batch_id}&handoffSourceId={actor}&handoffTaskId={task_id}','核对并交接此请假节点')
    for types,source_query in advisor_todo_sources(ids(user)[0]):
        candidates=[r for r in rows if r.todo_type in types]
        if not candidates: continue
        source=source_query.subquery()
        targets=select(source.c.biz_id,InternshipRecord.id,InternshipRecord.batch_id,InternshipRecord.advisor_user_id).join(
            InternshipRecord,InternshipRecord.id==source.c.record_id).where(source.c.biz_id.in_({r.source_biz_id for r in candidates}),
            InternshipRecord.tenant_id==ids(user)[0],InternshipRecord.is_deleted.is_(False),InternshipRecord.status!='ARCHIVED')
        for biz_id,record_id,batch_id,actor in db.execute(targets):
            for item in candidates:
                if (item.source_biz_id,item.assignee_id)==(biz_id,actor):
                    paths[item.id]=(f'/admin/internship/students?batchId={batch_id}&advisorId={record_id}','核对原实习记录并交接导师')
    return {'total':total,'items':[{'id':str(r.id),'title':r.title,'objectId':str(r.source_biz_id),
        'assigneeId':str(r.assignee_id),'statusLabel':'原承办账号不可用，或审批身份、权限、负责关系已失效',
        'path':paths.get(r.id,('',''))[0],'actionLabel':paths.get(r.id,('',''))[1],
        'actionNote':'' if r.id in paths else '尚未定位可交接的原节点或现任导师关系，请核对原单与历史记录，不能直接重派。'} for r in rows],
        'note':'保留原待办与历史；请假沿冻结节点交接，导师事项沿原实习学生名单分配命令接续办理。'}


def responsibility_gaps(db,user,page=1,size=30,issue_type=''):
    """Check effective memberships and stable object references, including disabled/expired staff."""
    queries=[];missing=duplicates=0
    for kind,model,label,bases in [('COLLEGE',College,'college_name',['COLLEGE_ADMIN']),
        ('MAJOR',Major,'major_name',['PROFESSIONAL_LEADER','MAJOR_LEADER']),('CLASS',SchoolClass,'class_name',['COUNSELOR'])]:
        counts=select(TeacherStudentScope.ref_id.label('ref'),func.count(func.distinct(User.id)).label('count')).select_from(TeacherStudentScope).join(
            User,User.id==TeacherStudentScope.user_id).join(UserRole,UserRole.user_id==User.id).join(Role,Role.id==UserRole.role_id).where(
            TeacherStudentScope.tenant_id==ids(user)[0],TeacherStudentScope.scope_type==kind,TeacherStudentScope.status=='ACTIVE',TeacherStudentScope.is_deleted.is_(False),
            Role.role_code==TeacherStudentScope.role_code,func.coalesce(Role.base_role_code,Role.role_code).in_(bases),
            Role.tenant_id==ids(user)[0],Role.status=='ACTIVE',Role.is_deleted.is_(False),UserRole.tenant_id==ids(user)[0],
            UserRole.status=='ACTIVE',UserRole.is_deleted.is_(False),User.tenant_id==ids(user)[0],User.status=='ACTIVE',User.is_deleted.is_(False),
            or_(User.expires_at.is_(None),User.expires_at>datetime.utcnow())).group_by(TeacherStudentScope.ref_id).subquery()
        number=func.coalesce(counts.c.count,0)
        query=select(model.id,getattr(model,label),number).outerjoin(counts,counts.c.ref==model.id).where(
            model.tenant_id==ids(user)[0],model.status=='ACTIVE',model.is_deleted.is_(False))
        missing+=db.scalar(select(func.count()).select_from(query.where(number==0).subquery()))
        duplicates+=db.scalar(select(func.count()).select_from(query.where(number>1).subquery()))
        condition=number==0 if issue_type=='MISSING' else number>1 if issue_type=='DUPLICATE' else number!=1
        queries.append(query.where(condition).with_only_columns(model.id.label('id'),getattr(model,label).label('name'),
            number.label('count'),literal(kind).label('scope_type')))
    issues=union_all(*queries).subquery()
    output=[{'id':str(identifier),'scopeType':kind,
        'kind':{'COLLEGE':'院系管理员','MAJOR':'专业负责人','CLASS':'班主任／辅导员'}[kind],
        'name':name,'count':count,'statusLabel':'尚无人负责' if count==0 else '多名负责人，请核对审批唯一性'}
        for identifier,name,count,kind in db.execute(select(issues).order_by(issues.c.scope_type,issues.c.id).limit(size).offset((page-1)*size))]
    return {'missing':missing,'duplicates':duplicates,'items':output,'page':page,
        'total':missing if issue_type=='MISSING' else duplicates if issue_type=='DUPLICATE' else missing+duplicates,
        'note':'按有效角色、在职账号与稳定范围关系核对；可逐页查看全部问题并定位原责任关系，实际审批仍须按批次预览。'}


def scope_impact(user, identifier):
    enforce_permission(user,'system.scope.view')
    if not school_wide(user): raise no_permission('责任配置查询限校级授权人员')
    with get_sessionmaker()() as db:
        item=row(db,TeacherStudentScope,identifier,user)
        original=scope_rows(db,user,[item])[0]
        role=db.scalar(tenant_query(Role,user).where(Role.role_code==item.role_code))
        account=db.scalar(tenant_query(User,user).where(User.id==item.user_id)) if item.user_id else None
        return {'scopeId':str(item.id),'original':original,
            'roleName':role.role_name if role else '历史身份待核对',
            'roleImpact':role_change_impact(db,user,item.role_code,role.id if role else None,item.user_id) if account else None,
            'note':'以下列出原负责人在该身份下的全部在办事项，供调整前核对，并非每项都会受本次范围变更影响。保存范围不自动转派待办，请按需要继续办理责任交接。' if account else
                '历史关系尚未定位到有效人员主档，无法核对其在办事项；请先核对原负责人及交接记录，不能将此情况视为没有待办。'}


def save_scope(user, data, identifier=None):
    with transaction(user, 'system.scope.manage') as db:
        if base_role(user) != 'SYSTEM_ADMIN': raise no_permission('责任配置需学校系统管理身份')
        account = row(db, User, data['userId'], user)
        kind = {'COLLEGE': 'colleges', 'MAJOR': 'majors', 'CLASS': 'classes'}[data['scopeType']]
        model, label, _, _ = ORG[kind]
        ref = row(db, model, data['refId'], user)
        if identifier:
            item = row(db, TeacherStudentScope, identifier, user, True)
            edit_version(item.version,data['expectedVersion'],{'userId':str(item.user_id or ''),'scopeType':item.scope_type,
                'refId':str(item.ref_id or ''),'status':item.status})
        else:
            item = TeacherStudentScope(tenant_id=ids(user)[0]); db.add(item)
        # Revoking the original relationship must remain possible after its role or account expires.
        retiring = identifier and data['status']=='DISABLED' and (
            item.user_id,item.role_code,item.scope_type,item.ref_id)==(account.id,data['roleCode'],data['scopeType'],ref.id)
        if not retiring:
            roles = {r.role_code for r in active_roles(db, ids(user)[0], account.id)}
            if (data['roleCode'] not in roles or account.user_type not in {'SCHOOL_ADMIN','TEACHER'}
                or account.status!='ACTIVE' or (account.expires_at and account.expires_at<=datetime.utcnow())):
                raise no_permission('该人员没有指定的有效校内身份；可停用原有关系，不能新增、转派或重新启用')
        before={'userId':str(item.user_id or ''),'roleCode':item.role_code,'scopeType':item.scope_type,
            'refId':str(item.ref_id or ''),'status':item.status,'refName':item.ref_value,'memberName':item.teacher_name}
        duplicate=db.scalar(tenant_query(TeacherStudentScope,user).where(TeacherStudentScope.user_id==account.id,
            TeacherStudentScope.role_code==data['roleCode'],TeacherStudentScope.scope_type==data['scopeType'],
            TeacherStudentScope.ref_id==ref.id,TeacherStudentScope.status=='ACTIVE',TeacherStudentScope.id!=(item.id or 0)))
        if duplicate and data['status']=='ACTIVE':
            raise AppException('DATA_CONFLICT','该负责人已有相同生效关系，请维护原关系',http_status=409)
        item.user_id, item.teacher_key, item.teacher_name = account.id, f'db-{account.id}', account.real_name
        item.role_code, item.scope_type, item.ref_id = data['roleCode'], data['scopeType'], ref.id
        item.ref_value, item.status = getattr(ref, label), data['status']; item.version = (item.version or 0) + 1
        account.version += 1
        db.flush()
        audit(db, user, 'SCOPE_SAVE', 'scope', item.id, {'before':before,'userId': str(account.id), 'roleCode': item.role_code,
            'scopeType': item.scope_type, 'refId': str(ref.id), 'status': item.status, 'reason': data['reason'],
            'after':{'userId':str(account.id),'roleCode':item.role_code,'scopeType':item.scope_type,'refId':str(ref.id),
                'status':item.status,'refName':item.ref_value,'memberName':item.teacher_name}})
        return {'id': str(item.id), 'version': item.version}


def retire_legacy_scope(user,identifier,data):
    with transaction(user,'system.scope.manage') as db:
        if base_role(user)!='SYSTEM_ADMIN': raise no_permission('责任配置需学校系统管理身份')
        item=row(db,TeacherStudentScope,identifier,user,True)
        edit_version(item.version,data['expectedVersion'],{'status':item.status})
        if item.status=='DISABLED' or (item.status!='REVIEW' and item.user_id and item.ref_id):
            raise AppException('DATA_CONFLICT','当前已不是待核对历史关系，请刷新后按原责任关系维护',http_status=409)
        before={'userId':str(item.user_id or ''),'roleCode':item.role_code,'scopeType':item.scope_type,
            'refId':str(item.ref_id or ''),'status':item.status,'refName':item.ref_value,'memberName':item.teacher_name}
        item.status='DISABLED';item.version+=1
        if item.user_id:
            account=db.scalar(tenant_query(User,user).where(User.id==item.user_id).with_for_update())
            if account: account.version+=1
        audit(db,user,'SCOPE_SAVE','scope',item.id,{'before':before,'after':{**before,'status':item.status},'reason':data['reason']})
        return {'id':str(item.id),'version':item.version,'message':'历史责任关系已停用，原人员及对象描述保留；未重新授权或转派在办事项。'}


def sensitive_phone(user,kind,identifier,reason):
    from app.core.field_crypto import decrypt_field
    with transaction(user,'system.person.sensitive') as db:
        enforce_permission(user,f'system.{kind}.view')
        model=StudentProfile if kind=='student' else StaffProfile
        query=scoped_students(db,user) if kind=='student' else scoped_staff(db,user)
        person=db.scalar(query.where(model.id==int(identifier)))
        if not person: raise not_found()
        if kind=='student':
            contact=db.scalar(tenant_query(StudentContact,user).where(StudentContact.student_id==person.id,
                StudentContact.contact_type=='PHONE').order_by(StudentContact.is_primary.desc(),StudentContact.id.desc()).limit(1))
            encrypted=contact.contact_value_encrypted if contact else None
        else: encrypted=person.phone_encrypted
        audit(db,user,'SENSITIVE_CONTACT_VIEW',kind,person.id,{'reason':reason})
        return {'phone':decrypt_field(encrypted,allow_legacy_plaintext=False) if encrypted else '',
                'message':'仅用于本次已登记用途，关闭后不保留明文'}


def binding_review(db,user,student_id,account_id):
    import hashlib,json
    if not school_wide(user): raise no_permission('学生绑定纠正由校级账号管理人员办理')
    student=row(db,StudentProfile,student_id,user)
    account=row(db,User,account_id,user)
    if account.user_type!='STUDENT' or account.status!='ACTIVE' or student.status!='ACTIVE':
        raise no_permission('请选择启用的学生主档与学生账号')
    if account.real_name!=student.real_name:
        raise AppException('VALIDATION_ERROR','账号姓名与学生主档不一致，请先核对真实人员身份')
    if not any(r.role_code=='STUDENT' for r in active_roles(db,ids(user)[0],account.id)):
        raise no_permission('所选账号没有有效学生身份，不能建立本人主档绑定')
    links=db.scalars(tenant_query(StudentAccountLink,user).where(StudentAccountLink.link_status=='ACTIVE',
        or_(StudentAccountLink.student_id==student.id,StudentAccountLink.user_id==account.id)).order_by(StudentAccountLink.id)).all()
    people={r.id:r for r in db.scalars(tenant_query(StudentProfile,user).where(StudentProfile.id.in_({r.student_id for r in links})))}
    accounts={r.id:r for r in db.scalars(tenant_query(User,user).where(User.id.in_({r.user_id for r in links})))}
    facts=[student.id,student.version,account.id,account.version,
        [[r.id,r.version,r.student_id,r.user_id] for r in links],[[r.id,r.version] for r in sorted(people.values(),key=lambda p:p.id)]]
    fingerprint=hashlib.sha256(json.dumps(facts,sort_keys=True).encode()).hexdigest()
    unchanged=len(links)==1 and links[0].student_id==student.id and links[0].user_id==account.id
    return student,account,links,{'studentName':student.real_name,'studentNo':student.student_no,'accountName':account.real_name,
        'loginName':account.login_name,'fingerprint':fingerprint,'expectedVersion':student.version,'unchanged':unchanged,
        'current':[{'studentName':people[r.student_id].real_name if r.student_id in people else '原主档缺失',
            'studentNo':people[r.student_id].student_no if r.student_id in people else '待核对',
            'loginName':accounts[r.user_id].login_name if r.user_id in accounts else '原账号缺失'} for r in links],
        'note':'当前本人绑定已一致，无需调整。' if unchanged else '确认后撤销所列旧绑定并建立新的本人绑定；相关账号旧会话失效，历史单据与绑定记录保留。涉及其他学生时，其原主档暂时成为未绑定，需继续处理。'}


def preview_binding(user,student_id,account_id):
    enforce_permission(user,'system.account.manage')
    enforce_permission(user,'system.student.manage')
    with get_sessionmaker()() as db:
        return binding_review(db,user,student_id,account_id)[3]


def repair_binding(user,student_id,data):
    from app.services.student_account_link_service import revoke_in_session,bind_in_session
    with transaction(user,'system.account.manage') as db:
        enforce_permission(user,'system.student.manage')
        student,account,links,review=binding_review(db,user,student_id,data['userId'])
        check_version(student.version,data['expectedVersion'])
        if review['fingerprint']!=data['fingerprint']:
            raise AppException('DATA_CONFLICT','人员或绑定已变化，请重新预览并核对，不会覆盖原输入',http_status=409)
        if len(links)==1 and links[0].student_id==student.id and links[0].user_id==account.id:
            return {'message':'当前绑定已与本次核对一致，无需重复调整'}
        affected={account.id,*[r.user_id for r in links]}
        for item in db.scalars(tenant_query(User,user).where(User.id.in_(affected)).order_by(User.id).with_for_update()):
            item.credential_version+=1;item.version+=1
        for link in links:
            revoke_in_session(db,tenant_id=ids(user)[0],student_id=link.student_id,remark=data['reason'])
        db.flush()
        result=bind_in_session(db,tenant_id=ids(user)[0],student_id=student.id,user_id=account.id,source='SYSTEM_REPAIR',
            login_name=account.login_name,student_no=student.student_no,remark=data['reason'])
        student.version+=1
        audit(db,user,'STUDENT_BINDING_REPAIR','student',student.id,{'before':review['current'],'accountId':str(account.id),
            'bindingId':str(result.id),'reason':data['reason']})
        return {'message':'绑定已纠正；相关账号需重新登录。历史业务记录保持原编号。','version':student.version}


def directory_rows(db,user,kind,result):
    if kind in ('staff','student'):
        fields=[('number','工号' if kind=='staff' else '学号'),('name','姓名'),('statusLabel','资料状态'),
            ('accountLabel','账号绑定'),('grade','年级'),('organizationLabel','组织归属'),('collegeCode','院系代码')]
        fields+= [('departmentCode','部门代码')] if kind=='staff' else [('majorCode','专业代码'),('classCode','班级代码')]
        headers=[label for _,label in fields];rows=[[r[key] for key,_ in fields] for r in result['items']]
    else:
        headers=['组织代码','组织名称','状态'];parents={}
        if kind in ('majors','classes'):
            parent_model,parent_name,parent_code,_=ORG['colleges' if kind=='majors' else 'majors']
            refs={int(r['parentId']) for r in result['items'] if r['parentId']}
            parents={r.id:[getattr(r,parent_code),getattr(r,parent_name)] for r in db.scalars(
                tenant_query(parent_model,user).where(parent_model.id.in_(refs)))}
            headers+=['上级组织代码','上级组织名称']
        if kind=='majors':headers+=['国家专业目录代码','学制（年）','培养层次']
        elif kind=='classes':headers+=['年级']
        rows=[]
        for item in result['items']:
            values=[item['code'],item['name'],item['statusLabel']]
            if kind in ('majors','classes'):values+=parents.get(int(item['parentId'] or 0),['',''])
            if kind=='majors':values += [item['nationalCode'],item['educationYears'],
                {'SECONDARY':'中职','HIGHER':'高职专科','FIVE_YEAR':'五年一贯制'}.get(item['trainingLevel'],'未登记')]
            elif kind=='classes':values.append(item['grade'])
            rows.append(values)
    return headers,rows


def export_directory(user,kind,keyword='',account_status=''):
    from app.services.xlsx_util import build_ledger_xlsx
    with transaction(user,'system.person.export') as db:
        enforce_permission(user,'system.person.export')
        result=list_people(user,kind,1,5000,keyword,account_status) if kind in ('staff','student') else list_organizations(user,kind,1,5000,keyword)
        if result['total']>5000: raise AppException('VALIDATION_ERROR','结果超过5000条，请缩小筛选条件再导出')
        headers,rows=directory_rows(db,user,kind,result)
        # Authorization is rechecked at download; never issue an unguarded static result URL.
        job=ExcelImportJob(tenant_id=ids(user)[0],module_key='system',biz_type='DIRECTORY_EXPORT',file_name=DIRECTORY_LABELS[kind]+'资料导出.xlsx',
            status='SUCCESS',total_rows=result['total'],success_rows=result['total'],operator_id=ids(user)[1],
            operator_name=user.get('realName'),started_at=datetime.utcnow(),finished_at=datetime.utcnow(),
            expires_at=datetime.utcnow()+timedelta(hours=24),preview_json={'kind':kind,'keyword':keyword,'accountStatus':account_status,'headers':headers,'rows':rows,
                'objectIds':[r['id'] for r in result['items']]})
        db.add(job);db.flush();audit(db,user,'DIRECTORY_EXPORT',kind,job.id,{'rows':result['total'],'keyword':keyword,'accountStatus':account_status})
        return build_ledger_xlsx('基础资料',headers,rows)


def export_result(user,identifier):
    from app.services.xlsx_util import build_ledger_xlsx
    with transaction(user,'system.person.export') as db:
        job=row(db,ExcelImportJob,identifier,user)
        if job.module_key!='system' or job.biz_type!='DIRECTORY_EXPORT' or job.operator_id!=ids(user)[1]:raise no_permission('仅导出任务发起人可领取结果')
        if not job.expires_at or job.expires_at<=datetime.utcnow():raise AppException('RESULT_EXPIRED','结果已过期，请从原页面重新导出',http_status=410)
        snapshot=job.preview_json or {};kind=snapshot.get('kind');object_ids=snapshot.get('objectIds',[])
        enforce_permission(user,f'system.{kind}.view' if kind in ('staff','student') else 'system.org.view')
        model=StudentProfile if kind=='student' else StaffProfile if kind=='staff' else ORG[kind][0]
        query=scoped_students(db,user) if kind=='student' else scoped_staff(db,user) if kind=='staff' else org_query(db,user,kind)
        authorized=set(db.scalars(query.with_only_columns(model.id).where(model.id.in_(object_ids))))
        if authorized!={int(v) for v in object_ids}:raise no_permission('结果包含已移出当前管理范围的资料，请按现有范围重新导出')
        audit(db,user,'EXPORT_RESULT_DOWNLOAD','import',job.id,{'rows':job.total_rows})
        return build_ledger_xlsx('基础资料',snapshot['headers'],snapshot['rows'])
