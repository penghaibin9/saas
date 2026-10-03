"""Teacher mobile read-only positions within batches containing their scoped students."""
from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, not_found
from app.models import InternshipPosition, InternshipRecord
from app.modules.internship.services.internship_batch_context import resolve_batch
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.modules.internship.services import internship_position_service as positions
from app.services.db_service import _tid, session

_SUMMARY = (
    'id', 'title', 'companyName', 'batchId', 'batchName', 'campaignId', 'status', 'statusLabel',
    'statusTone', 'headcount', 'remaining', 'workLocation', 'salaryRange', 'majorRequirement', 'updatedAt',
)
_DETAIL = (
    'workContent', 'workAddress', 'gradeRequirement', 'dailyHours', 'weeklyHours', 'shiftType',
    'nightShift', 'overtimeAllowed', 'restDaysPerWeek', 'remunerationType', 'remunerationAmount',
    'remunerationCycle', 'accommodationProvided', 'mealProvided', 'hazardousFlag', 'specialEquipment',
    'subsidy', 'mentorName', 'riskFlag',
)


def _scoped_batch(db, batch_id, user):
    batch = resolve_batch(db, batch_id)
    records = select(InternshipRecord.id).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == batch.id,
        InternshipRecord.is_deleted.is_(False),
    )
    if db.scalar(apply_internship_record_scope(records, user).limit(1)) is None:
        raise not_found('此批次不在当前指导学生范围内')
    return batch


def _project(db, position, *, detail=False):
    source = positions._row(position, db)
    return {key: source.get(key) for key in _SUMMARY + (_DETAIL if detail else ())}


def list_positions(user, *, batch_id, page=1, page_size=20, keyword='', status=''):
    with session() as db:
        batch = _scoped_batch(db, batch_id, user)
        query = select(InternshipPosition).where(
            InternshipPosition.tenant_id == _tid(), InternshipPosition.batch_id == batch.id,
            InternshipPosition.is_deleted.is_(False),
        )
        if status:
            if status not in positions.STATUS_LABEL:
                raise AppException('VALIDATION_ERROR', '岗位状态不正确')
            query = query.where(InternshipPosition.status == status)
        if keyword.strip():
            pattern = '%' + keyword.strip() + '%'
            query = query.where(or_(InternshipPosition.title.like(pattern), InternshipPosition.company_name.like(pattern)))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.scalars(query.order_by(InternshipPosition.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
        return [_project(db, row) for row in rows], total


def get_position(user, *, batch_id, position_id):
    with session() as db:
        batch = _scoped_batch(db, batch_id, user)
        position = db.scalar(select(InternshipPosition).where(
            InternshipPosition.tenant_id == _tid(), InternshipPosition.batch_id == batch.id,
            InternshipPosition.id == position_id, InternshipPosition.is_deleted.is_(False),
        ))
        if position is None:
            raise not_found('岗位不存在或不属于当前批次')
        return _project(db, position, detail=True)
