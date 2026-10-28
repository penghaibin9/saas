"""Student intention entry: explicit context, existing ledger and shared intention commands."""
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import or_, select

from app.core.exceptions import AppException
from app.models import EmpCompany, InternshipBatch, InternshipEnterpriseCollegeScope, InternshipIntention, InternshipPosition, StudentProfile
from app.modules.internship.services import internship_match_service as commands
from app.modules.internship.services import internship_application_service as application
from app.modules.internship.services import internship_student_application_context_service as catalog
from app.modules.internship.services.internship_student_context_guard import require_explicit_context, require_expected_version
from app.modules.internship.services.internship_record_resolver import _is_active_record
from app.services.db_service import _as_id, _tid, session


def _writable(record, batch):
    return (_is_active_record(record, batch) and record.status in ('PREPARING', 'READY')
            and not record.position_id and record.destination_type not in ('ASSIGNED', 'SELF_ARRANGED', 'EXEMPTED'))


def _latest(db, record):
    return db.scalar(select(InternshipIntention).where(
        InternshipIntention.tenant_id == _tid(), InternshipIntention.record_id == record.id,
        InternshipIntention.student_id == record.student_id, InternshipIntention.batch_id == record.batch_id,
        InternshipIntention.is_deleted.is_(False)).order_by(
            InternshipIntention.status.in_(('DRAFT', 'SUBMITTED')).desc(), InternshipIntention.id.desc()).limit(1))


def _view(db, record, batch, row):
    writable = _writable(record, batch)
    return {'hasData': True, 'batchId': str(record.batch_id), 'internshipId': str(record.id),
            'intention': commands._intention_row(db, row) if row else None,
            'canEdit': writable and (not row or row.status in ('DRAFT', 'SUBMITTED')),
            'canSubmit': writable and bool(row and row.status in ('DRAFT', 'WITHDRAWN')),
            'canWithdraw': writable and bool(row and row.status == 'SUBMITTED'),
            'canCreateNew': writable and bool(row and row.status == 'WITHDRAWN'),
            'readOnlyReason': '' if writable else '当前实习已落实去向或进入后续阶段，仅可查看意向。'}


def get_my(user, *, batch_id, internship_id, page=1):
    with session() as db:
        record, _, bid = require_explicit_context(db, user, {'batchId': batch_id, 'internshipId': internship_id}, for_write=False)
        result = _view(db, record, db.get(InternshipBatch, bid), _latest(db, record))
    positions = catalog.list_positions(user, batch_id=batch_id, internship_id=internship_id, page=page)
    return {**result, 'positions': positions['items'], 'positionsPage': positions['page'],
            'positionsTotal': positions['total'], 'positionsHasMore': positions['hasMore']}


def _preferred_position(db, record, student, raw_id):
    if not raw_id:
        return None
    if not str(raw_id).isascii() or not str(raw_id).isdigit() or int(raw_id) <= 0:
        raise AppException('VALIDATION_ERROR', '意向岗位编号无效，请从目录重新选择')
    from app.modules.internship.services.internship_student_position_eligibility_service import _major_sql_predicate
    from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
    org_query, org = application._application_org_query(select(StudentProfile).where(
        StudentProfile.id == student.id, StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)))
    college, major = db.execute(org_query.with_only_columns(org['collegeId'], org['majorName'])).one()
    scopes = select(InternshipEnterpriseCollegeScope.company_id).where(
        InternshipEnterpriseCollegeScope.tenant_id == _tid(), InternshipEnterpriseCollegeScope.is_deleted.is_(False))
    allowed = scopes.where(InternshipEnterpriseCollegeScope.college_id == college) if college else scopes.where(False)
    result = db.execute(select(InternshipPosition, EmpCompany).join(EmpCompany, EmpCompany.id == InternshipPosition.company_id).where(
        InternshipPosition.id == _as_id(raw_id), InternshipPosition.tenant_id == _tid(),
        InternshipPosition.batch_id == record.batch_id, InternshipPosition.campaign_id.is_(None),
        InternshipPosition.is_deleted.is_(False), InternshipPosition.status == 'PUBLISHED',
        InternshipPosition.allocated_count < InternshipPosition.headcount,
        EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False), EmpCompany.coop_status == 'ACTIVE',
        EmpCompany.blacklist.is_(False), or_(EmpCompany.access_valid_until.is_(None), EmpCompany.access_valid_until >= datetime.utcnow()),
        or_(~EmpCompany.id.in_(scopes), EmpCompany.id.in_(allowed)), _major_sql_predicate(major or ''))).first()
    if not result:
        raise AppException('DATA_CONFLICT', '意向岗位当前不可选择，请重新读取岗位目录', http_status=409)
    position, company = result
    rights = evaluate_position_publishability(position, company, db.get(InternshipBatch, record.batch_id), student, operation='APPLY', db=db, record=record)
    if not rights['passed']:
        raise AppException('DATA_CONFLICT', '意向岗位条件尚未核验通过，请重新选择', http_status=409)
    return position


def mutate(user, body, action):
    with session() as db:
        record, student, bid = require_explicit_context(db, user, body, for_write=True)
        batch = db.get(InternshipBatch, bid)
        if not _writable(record, batch):
            raise AppException('DATA_CONFLICT', '当前实习已落实去向或进入后续阶段，不能修改选岗意向', http_status=409)
        row = _latest(db, record)
        raw_id = body.get('id')
        creating = action == 'SAVE' and not raw_id
        if creating:
            if row and (row.status != 'WITHDRAWN' or body.get('newAfterWithdraw') is not True or str(body.get('previousIntentionId')) != str(row.id)):
                raise AppException('DATA_CONFLICT', '已有意向记录，请读取原单后继续', http_status=409)
            if row:
                require_expected_version(body.get('previousExpectedVersion'), row.version, entity_name='意向')
        else:
            if not row or str(row.id) != str(raw_id):
                raise AppException('DATA_CONFLICT', '意向不属于当前本人实习记录，请重新读取', http_status=409)
            require_expected_version(body.get('expectedVersion'), row.version, entity_name='意向')
        payload = None
        if action == 'SAVE':
            values = {}
            for key, maximum in [('preferredCity', 100), ('preferredIndustry', 100), ('intentionNote', 500)]:
                value = body.get(key, '')
                if not isinstance(value, str) or len(value.strip()) > maximum:
                    raise AppException('VALIDATION_ERROR', '城市、行业或说明长度不符合要求')
                values[key] = value.strip()
            if not any(values.values()):
                raise AppException('VALIDATION_ERROR', '请至少填写城市、行业或说明中的一项')
            position = _preferred_position(db, record, student, body.get('preferredPositionId'))
            payload = SimpleNamespace(recordId=str(record.id), **values,
                preferredPositionId=str(position.id) if position else '', preferredCompanyId=str(position.company_id) if position else '')
            command = 'CREATE' if creating else 'UPDATE'
        else:
            if action == 'SUBMIT' and row.preferred_position_id:
                _preferred_position(db, record, student, row.preferred_position_id)
            command = action
        row = commands.intention_command_in_tx(db, command, body=payload, iid=None if creating else row.id,
            user=user, self_service=True, expected_version=None if creating else body.get('expectedVersion'))
        db.commit()
        db.refresh(row)
        return _view(db, record, batch, row)
