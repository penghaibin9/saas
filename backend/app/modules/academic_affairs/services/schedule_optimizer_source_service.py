"""Read-only source adapter for the verified 815d7160 archive.
No ensure_* roster helper is called: missing projections are blockers, not seed requests.
"""
from datetime import datetime, date
from sqlalchemy import select, or_
from app.services.db_service import _tid
from app.modules.academic_affairs.optimizer.contracts import InputError
from app.modules.academic_affairs.optimizer.source_builder import source_revision
from app.modules.academic_affairs.services import academic_affairs_autoschedule_service as auto
from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as schedule
from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy

MAX_TASKS = 1000
MAX_ROWS = 50000


def _scalar(value):
    if isinstance(value, (datetime,date)):
        return value.isoformat()
    return value


def _row(row, fields):
    return {key:(str(getattr(row,key)) if (key=='id' or key.endswith('_id')) and getattr(row,key) is not None
                 else _scalar(getattr(row,key))) for key in fields.split()}


def _read(db, model, conditions, fields, limit=MAX_ROWS):
    query=select(model).where(model.tenant_id==_tid(),model.is_deleted.is_(False),*conditions).order_by(model.id).limit(limit+1)
    if db.info.get('optimizer_source_lock'):
        query=query.with_for_update(read=True).execution_options(populate_existing=True)
    rows=db.scalars(query).all()
    if len(rows)>limit:
        raise InputError('SOURCE_READ_LIMIT',model.__tablename__)
    return [_row(row,fields) for row in rows]


def _formal_rosters(db, teaching_classes, task_ids):
    """Bounded current-version read; selection projections still use their canonical reconciliation."""
    from collections import defaultdict
    from app.models import AaTeachingClassRosterVersion, AaTeachingClassMember, StudentProfile, AaSelectionCourse
    from . import academic_affairs_teaching_class_service as classes
    from .academic_affairs_roster_consumer_service import roster_hash
    version_ids=[int(c['current_roster_version_id']) for c in teaching_classes if c['current_roster_version_id']]
    versions={v['id']:v for v in _read(db,AaTeachingClassRosterVersion,
        [AaTeachingClassRosterVersion.id.in_(version_ids or [-1]),AaTeachingClassRosterVersion.status=='LOCKED'],
        'id teaching_class_id version_no member_count roster_hash')}
    members=defaultdict(list)
    for m in _read(db,AaTeachingClassMember,[AaTeachingClassMember.roster_version_id.in_(version_ids or [-1]),
            AaTeachingClassMember.status=='ACTIVE'],'id teaching_class_id roster_version_id student_id'):
        version=versions.get(m['roster_version_id'])
        if not version or m['teaching_class_id']!=version['teaching_class_id']:
            raise InputError('ROSTER_HASH_MISMATCH',m['teaching_class_id'])
        members[m['roster_version_id']].append(m['student_id'])
    student_ids={int(s) for values in members.values() for s in values}
    profiles={p['id'] for p in _read(db,StudentProfile,[StudentProfile.id.in_(student_ids or [-1])],'id')}
    selection_tasks={c['teaching_task_id'] for c in _read(db,AaSelectionCourse,
        [AaSelectionCourse.teaching_task_id.in_(task_ids or [-1])],'id teaching_task_id')}
    result={}
    for tc in teaching_classes:
        tid=tc['teaching_task_id'];version=versions.get(tc['current_roster_version_id'])
        if tc['roster_status']!='LOCKED' or not version or version['teaching_class_id']!=tc['id']:
            continue
        ids=sorted(members[version['id']],key=int)
        if not ids or len(ids)!=version['member_count'] or not set(ids)<=profiles or roster_hash(ids)!=version['roster_hash']:
            raise InputError('ROSTER_HASH_MISMATCH',tid)
        if tid in selection_tasks:
            reconciled=classes.resolve_teaching_task_roster(db,int(tid))
            if not reconciled.get('ready') or str(reconciled.get('rosterVersionId'))!=version['id'] or set(map(str,reconciled.get('studentIds',[])))!=set(ids):
                raise InputError('FORMAL_ROSTER_REQUIRED',tid)
        result[tid]={'ready':True,'studentIds':ids,'teachingClassId':tc['id'],
                     'rosterVersionId':version['id'],'rosterHash':version['roster_hash']}
    return result


def capture_source(db,user,batch_id,*,lock=False):
    from app.models import (AaTeachingTask,AaTeachingTaskBatch,AaTimeSlot,AaClassroom,AaCalendarEvent,
                            AaScheduleItem,AaTeacherAvailability,AaClassroomBooking,AaScheduleRule,
                            AaTeachingClass,AaTeachingClassTeacher,AaClassTimeBand,AaLabBooking)
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    auto._require_school(user,db)
    db.info['optimizer_source_lock']=lock
    batch=schedule._load_batch(db,int(batch_id),writable=False,lock=False)
    from .academic_affairs_schedule_write_scope_r3 import assert_schedule_write_scope
    assert_schedule_write_scope(db,user,batch)
    term,_,weeks=policy.resolve_scope(db,term_id=batch.term_id,batch_id=batch.id,writable=False)
    if db.new or db.dirty or db.deleted:
        raise InputError('SOURCE_READER_NOT_CLEAN','Reader must not initialize business records')
    if not term.start_date or not term.end_date:
        raise InputError('TERM_DATES_REQUIRED','Formal term dates are missing')
    task_batch_ids=schedule._task_batch_ids(db,batch)
    task_fields='id batch_id course_id course_name class_id teaching_class_name teacher_key teacher_name expected_students weekly_hours total_hours start_week end_week required_room_type formation_mode status no_auto_schedule'
    target=_read(db,AaTeachingTask,[AaTeachingTask.batch_id.in_(task_batch_ids or [-1]),
        AaTeachingTask.status=='READY',AaTeachingTask.no_auto_schedule.is_(False)],task_fields,MAX_TASKS)
    active_ids=truth._live_batch_ids(db,batch.term_id,batch.id,replacing_batch_id=batch.supersedes_batch_id)
    existing=_read(db,AaScheduleItem,[AaScheduleItem.batch_id.in_([batch.id,*active_ids]),AaScheduleItem.status=='EFFECTIVE'],
        'id batch_id task_id teacher_key class_id classroom_id weekday slot_no start_week end_week week_parity source')
    task_ids={int(t['id']) for t in target}|{int(i['task_id']) for i in existing if i['task_id']}
    tasks=_read(db,AaTeachingTask,[AaTeachingTask.id.in_(task_ids or [-1])],task_fields,MAX_TASKS)
    rooms=_read(db,AaClassroom,[],
        'id campus_code room_type capacity status allow_schedule is_exclusive room_name building_name room_code')
    slots=_read(db,AaTimeSlot,[],'id campus_code slot_no start_time end_time enabled status')
    time_bands=_read(db,AaClassTimeBand,[AaClassTimeBand.status=='ENABLED'],
        'id slot_id campus_code effective_start effective_end start_time end_time status')
    events=_read(db,AaCalendarEvent,[AaCalendarEvent.term_id==term.id],
        'id event_type start_date end_date swap_to_date')
    availability=_read(db,AaTeacherAvailability,[AaTeacherAvailability.term_id==term.id,AaTeacherAvailability.status=='ADOPTED'],
        'id teacher_key weekday slot_no')
    bookings=_read(db,AaClassroomBooking,[AaClassroomBooking.status=='APPROVED',
        AaClassroomBooking.booking_date>=term.start_date.date().isoformat(),
        AaClassroomBooking.booking_date<=term.end_date.date().isoformat()],
        'id classroom_id booking_date slot_no')
    for row in _read(db,AaLabBooking,[AaLabBooking.status=='APPROVED',
            AaLabBooking.booking_date>=term.start_date.date().isoformat(),
            AaLabBooking.booking_date<=term.end_date.date().isoformat()],
            'id classroom_id booking_date slot_no'):
        bookings.append({**row,'id':'LAB:'+str(row['id'])})
    rules=_read(db,AaScheduleRule,[AaScheduleRule.status=='ENABLED',or_(AaScheduleRule.batch_id==batch.id,
        (AaScheduleRule.batch_id.is_(None)) & (AaScheduleRule.term_id==term.id))],
        'id term_id batch_id rule_key rule_value_json status')
    for rule in rules:
        if rule['rule_key'] not in policy.RULE_SCHEMAS:
            raise InputError('UNSUPPORTED_SOURCE_RULE',str(rule['rule_key']))
    if not any(r['rule_key']=='AUTO_WEEKDAYS' for r in rules):
        raise InputError('WEEKDAYS_REQUIRED','请先在排课规则中保存允许排课星期')
    from . import academic_affairs_scheduling_rule_final_facade as governed_rules
    params=governed_rules.load_effective_params(db,term.id,batch.id)
    teaching_classes=_read(db,AaTeachingClass,[AaTeachingClass.teaching_task_id.in_(task_ids or [-1]),AaTeachingClass.status=='ACTIVE'],
        'id teaching_task_id term_id current_roster_version_id current_roster_version_no roster_status status')
    by_class={int(row['id']):str(row['teaching_task_id']) for row in teaching_classes}
    staff=_read(db,AaTeachingClassTeacher,[AaTeachingClassTeacher.teaching_class_id.in_(list(by_class) or [-1]),
        AaTeachingClassTeacher.status=='ACTIVE'],'id teaching_class_id teacher_key teacher_name start_week end_week role_type')
    rosters=_formal_rosters(db,teaching_classes,list(task_ids))
    teachers={}
    for task in tasks:
        if type(task['start_week']) is not int or type(task['end_week']) is not int or not 1<=task['start_week']<=task['end_week']<=weeks:
            raise InputError('TASK_WEEK_RANGE_REQUIRED',str(task['id']))
        tid=str(task['id'])
        if tid not in rosters:
            raise InputError('FORMAL_ROSTER_REQUIRED',tid)
        associated=[r for r in staff if by_class[int(r['teaching_class_id'])]==tid]
        for row in associated:
            if (row['start_week'] is not None and row['start_week']>task['start_week']) or (row['end_week'] is not None and row['end_week']<task['end_week']):
                raise InputError('SEGMENTED_TEACHER_ASSIGNMENT',tid)
        keys={row['teacher_key'] for row in associated}
        if task['teacher_key']:keys.add(task['teacher_key'])
        if not keys or any(not isinstance(k,str) or not k for k in keys):
            raise InputError('TEACHER_ASSIGNMENT_REQUIRED',tid)
        teachers[tid]=sorted(keys)
    facts={'scope':{'tenantId':str(_tid()),'termId':str(term.id),'batchId':str(batch.id)},
        'batch':_row(batch,'id term_id status college_id supersedes_batch_id'),
        'term':_row(term,'id start_date end_date teaching_weeks status'),
        'targetTaskIds':sorted(str(t['id']) for t in target),'tasks':tasks,'rooms':rooms,'slots':slots,'timeBands':time_bands,
        'events':events,'existingItems':existing,'availability':availability,'bookings':bookings,
        'params':params,'ruleRows':rules,
        'teachingClasses':teaching_classes,'teacherRows':staff,'teachers':teachers,'rosters':rosters}
    if db.new or db.dirty or db.deleted:
        raise InputError('SOURCE_READER_SIDE_EFFECT','No source writer is permitted')
    return facts,source_revision(facts)
