"""Student master basic facts, shared by normal student and authorized school actions."""
from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipRecord, StudentAccountLink, StudentProfile
from app.modules.internship.services.internship_audit_service import add_audit
from app.modules.internship.services.internship_batch_context import resolve_batch
from app.modules.internship.services.internship_student_context_guard import require_context_fields
from app.modules.internship.services.internship_record_resolver import resolve_student_internship_context
from app.services.db_service import _as_id, _tid, session
from app.services.mobile_student_service import _require_student, resolve_student

FIELDS = {'sourceRegion': ('source_region', '生源地', 100),
          'nation': ('nation', '民族', 50), 'gender': ('gender', '性别', 10)}
GENDERS = {'男': '男', '女': '女', 'M': '男', 'F': '女', 'MALE': '男', 'FEMALE': '女'}
IMPORT_HEADERS = ['学号', '生源地', '民族', '性别']
IMPORT_MAP = dict(zip(IMPORT_HEADERS, ['studentNo', 'sourceRegion', 'nation', 'gender']))


def _text(value, label, maximum):
    if not isinstance(value, str):
        raise AppException('VALIDATION_ERROR', f'{label}应填写文字')
    value = value.strip()
    if len(value) > maximum or any(ord(c) < 32 for c in value) or any(c in value for c in '<>'):
        raise AppException('VALIDATION_ERROR', f'{label}格式不正确')
    if value in {'未采集', '未填写', '未知', '待补充', '-', '--'} or '*' in value:
        raise AppException('VALIDATION_ERROR', f'请填写真实{label}，暂未采集时保持为空')
    return value or None


def clean_fields(body):
    values = {}
    for field, (_, label, maximum) in FIELDS.items():
        try:
            values[field] = _text(body.get(field), label, maximum)
        except AppException as exc:
            raise AppException(exc.code, exc.message, details={'field': field}) from None
    if values['gender'] and values['gender'] not in GENDERS:
        raise AppException('VALIDATION_ERROR', '性别请选择男或女，暂未采集时保持为空', details={'field': 'gender'})
    if values['gender']:
        values['gender'] = GENDERS[values['gender']]
    for field in ('sourceRegion', 'nation'):
        if values[field] and len(values[field]) < 2:
            raise AppException('VALIDATION_ERROR', f'{FIELDS[field][1]}请至少填写两个字', details={'field': field})
    return values


def present(student, *, editable=False):
    gender = GENDERS.get(str(student.gender or '').strip(), '')
    values = {'sourceRegion': student.source_region or '', 'nation': student.nation or '', 'gender': gender}
    missing = [label for field, (_, label, _) in FIELDS.items() if not values[field]]
    return {'studentId': str(student.id), 'studentNo': student.student_no,
            'name': student.real_name, **values, 'version': int(student.version or 0),
            'complete': not missing, 'missingFields': missing, 'todoCount': int(bool(missing)),
            'statusLabel': '已完善' if not missing else '待完善', 'editable': editable}


def _lock_student(db, student_id):
    row = db.scalar(select(StudentProfile).where(
        StudentProfile.id == student_id, StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False), StudentProfile.status == 'ACTIVE'
    ).with_for_update().execution_options(populate_existing=True))
    if not row:
        raise not_found('学生主档不存在或已停用')
    return row


def _own(db, user, batch_id, internship_id, *, write=False):
    require_context_fields({'batchId': batch_id, 'internshipId': internship_id})
    subject = _require_student(user)
    student = resolve_student(db, subject)
    if not student:
        raise no_permission('当前学生账号没有有效主档绑定')
    if write:
        uid = _as_id(str(subject.get('userId') or subject.get('id') or '').removeprefix('db-'))
        binding = db.scalar(select(StudentAccountLink).where(
            StudentAccountLink.tenant_id == _tid(), StudentAccountLink.user_id == uid,
            StudentAccountLink.student_id == student.id, StudentAccountLink.link_status == 'ACTIVE',
            StudentAccountLink.is_deleted.is_(False)
        ).with_for_update().execution_options(populate_existing=True))
        if not binding:
            raise no_permission('当前学生账号没有有效主档绑定')
        student = _lock_student(db, student.id)
    ctx = resolve_student_internship_context(db, student=student, batch_id=batch_id, for_write=write)
    record = ctx.record
    if not record or str(record.id) != str(internship_id):
        raise not_found('实习记录不存在或不属于本人当前批次')
    editable = ctx.mode != 'history' and record.status != 'ARCHIVED' and student.status == 'ACTIVE'
    if write and not editable:
        raise no_permission('历史实习批次仅可查看基础资料')
    return student, record, editable


def _school(db, user, record_id, batch_id, *, write=False):
    from app.modules.internship.services import internship_student_service as records
    if write:
        from app.modules.internship.services.internship_service import assert_admin_tenant
        assert_admin_tenant(user, '维护学生基础资料')
    batch = resolve_batch(db, batch_id, for_write=write)
    record = records._get(db, record_id)
    if record.batch_id != batch.id:
        raise not_found('实习记录不属于当前批次')
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == record.student_id, StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False), StudentProfile.status == 'ACTIVE'))
    if not student or not records._rec_in_scope(records._current_scope(user), db, record, student):
        raise no_permission('该学生不在当前数据范围内')
    if write:
        student = _lock_student(db, student.id)
    return student, record


def _save(db, student, record, user, body, action):
    expected = body.get('expectedVersion')
    if type(expected) is not int or expected < 0:
        raise AppException('VALIDATION_ERROR', '请先读取学生基础资料的当前版本')
    if expected != int(student.version or 0):
        raise AppException('DATA_CONFLICT', '基础资料已在其他页面更新，当前输入已保留，请重新读取后核对')
    values = clean_fields(body)
    changed = [field for field, (attribute, _, _) in FIELDS.items()
               if getattr(student, attribute) != values[field]]
    if changed:
        for field, (attribute, _, _) in FIELDS.items():
            setattr(student, attribute, values[field])
        student.version = expected + 1
        student.updated_by = _as_id(str(user.get('userId') or user.get('id')).removeprefix('db-'))
        add_audit(db, target_type='STUDENT_BASIC_INFO', target_id=student.id, action=action,
                  user=user, batch_id=record.batch_id, internship_id=record.id,
                  expected_version=expected, new_version=student.version,
                  detail={'changedFields': changed, 'source': 'STUDENT' if action.endswith('_SELF') else 'SCHOOL'})
    return present(student, editable=True)


def get_my(user, batch_id, internship_id):
    with session() as db:
        student, _, editable = _own(db, user, batch_id, internship_id)
        return present(student, editable=editable)


def save_my(user, batch_id, internship_id, body):
    with session() as db:
        student, record, _ = _own(db, user, batch_id, internship_id, write=True)
        result = _save(db, student, record, user, body, 'BASIC_INFO_SAVE_SELF')
        db.commit()
        return result


def get_school(user, record_id, batch_id):
    with session() as db:
        student, _ = _school(db, user, record_id, batch_id)
        return present(student)


def save_school(user, record_id, batch_id, body):
    with session() as db:
        student, record = _school(db, user, record_id, batch_id, write=True)
        result = _save(db, student, record, user, body, 'BASIC_INFO_SAVE_SCHOOL')
        db.commit()
        return result


def preview_import(user, batch_id, rows):
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, '导入学生基础资料')
    if not rows or len(rows) > 1000:
        raise AppException('VALIDATION_ERROR', '每次请导入1至1000行基础资料')
    result, errors, seen = [], [], set()
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=True)
        numbers = [str(row.get('studentNo') or '').strip() for row in rows]
        pairs = db.execute(select(StudentProfile, InternshipRecord).join(
            InternshipRecord, InternshipRecord.student_id == StudentProfile.id
        ).where(StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                StudentProfile.status == 'ACTIVE', StudentProfile.student_no.in_(numbers),
                InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False))).all()
        lookup = {student.student_no: (student, record) for student, record in pairs}
        for i, row in enumerate(rows):
            number = numbers[i]
            item = {key: row.get(key, '') for key in IMPORT_MAP.values()}
            item['studentNo'] = number
            try:
                if not number or number in seen:
                    raise AppException('VALIDATION_ERROR', '学号不能为空或重复')
                seen.add(number)
                if number not in lookup:
                    raise AppException('VALIDATION_ERROR', '学号未匹配当前批次的有效学生')
                student, record = lookup[number]
                clean_fields(item)
                item.update(recordId=str(record.id), expectedVersion=int(student.version or 0))
            except AppException as exc:
                errors.append({'rowNo': i + 1, 'field': (exc.details or {}).get('field', 'studentNo'), 'message': exc.message})
            result.append(item)
    return {'rows': result, 'total': len(rows), 'validRows': len(rows) - len(errors),
            'invalidRows': len(errors), 'errors': errors}


def confirm_import(user, batch_id, rows):
    preview = preview_import(user, batch_id, rows)
    if preview['invalidRows']:
        raise AppException('VALIDATION_ERROR', '存在未通过预校验的基础资料，请修正后重新上传')
    # Never replace the submitted versions with preview's fresh versions.
    submitted = {str(row.get('studentNo') or '').strip(): row for row in rows}
    with session() as db:
        for item in sorted(preview['rows'], key=lambda row: row['studentNo']):
            original = submitted[item['studentNo']]
            student, record = _school(db, user, item['recordId'], batch_id, write=True)
            if str(original.get('recordId')) != str(record.id):
                raise AppException('DATA_CONFLICT', '导入对象已变化，请重新预校验')
            _save(db, student, record, user, original, 'BASIC_INFO_IMPORT')
        db.commit()
    return {'updated': len(rows), 'total': len(rows)}
