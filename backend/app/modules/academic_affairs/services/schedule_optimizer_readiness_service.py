"""Bounded, read-only checks of the school's scheduling authorities."""
from sqlalchemy import select, func
from app.services.db_service import session, _tid
from app.modules.academic_affairs.optimizer.contracts import InputError
from .schedule_optimizer_source_service import capture_source


def readiness(user, batch_id):
    from app.models import AaTeachingTask, AaClassroom, AaScheduleItem
    from .schedule_optimizer_jobs_service import _authorize, _enabled
    from . import academic_affairs_schedule_final_service as schedule
    from . import academic_affairs_teaching_class_service as classes
    _authorize(user, str(batch_id))
    with session() as db:
        batch = schedule._load_batch(db, int(batch_id), writable=False, lock=False)
        ids = schedule._task_batch_ids(db, batch)
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id.in_(ids or [-1]),
            AaTeachingTask.status == 'READY', AaTeachingTask.no_auto_schedule.is_(False),
            AaTeachingTask.is_deleted.is_(False)).order_by(AaTeachingTask.id).limit(1001)).all()
        blockers = []
        if len(tasks) > 1000: blockers.append({'code': 'SOURCE_READ_LIMIT'})
        roster_checks = [classes.resolve_teaching_task_roster(db, t.id) for t in tasks[:1000]]
        missing_roster = sum(not r.get('ready') or not r.get('rosterVersionId') for r in roster_checks)
        rooms = db.scalar(select(func.count()).select_from(AaClassroom).where(
            AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False),
            AaClassroom.status == 'AVAILABLE', AaClassroom.allow_schedule.is_(True),
            AaClassroom.is_exclusive.is_(False)))
        existing = db.scalar(select(func.count()).select_from(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == batch.id,
            AaScheduleItem.is_deleted.is_(False), AaScheduleItem.status == 'EFFECTIVE'))
        summary = {'taskCount': len(tasks), 'teacherCount': len({t.teacher_key for t in tasks if t.teacher_key}),
                   'classCount': len({t.teaching_class_name for t in tasks if t.teaching_class_name}),
                   'roomCount': rooms, 'existingCount': existing,
                   'missingHeadcount': sum(not t.expected_students or t.expected_students < 1 for t in tasks),
                   'missingRoster': missing_roster, 'truncated': len(tasks) > 1000}
        if not tasks: blockers.append({'code': 'NO_READY_TASKS'})
        if summary['missingHeadcount']: blockers.append({'code': 'HEADCOUNT_MISSING'})
        if missing_roster: blockers.append({'code': 'FORMAL_ROSTER_REQUIRED'})
        if batch.status not in {'DRAFT', 'PRE_PUBLISHED'}: blockers.append({'code': 'BATCH_NOT_EDITABLE'})
        try:
            capture_source(db, user, str(batch.id))
        except InputError as exc:
            if not any(b['code'] == exc.code for b in blockers): blockers.append({'code': exc.code})
        if not _enabled(): blockers.append({'code': 'MYSQL_AND_WORKER_ACCEPTANCE_REQUIRED'})
        return {'batchId': str(batch.id), 'batchStatus': batch.status, 'summary': summary,
                'confirmedPlanRequired': True, 'canGenerateFromLiveData': not blockers,
                'canApply': False, 'blockers': blockers}
