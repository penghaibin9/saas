"""Candidate job facade; never grants a new formal timetable write authority.
Disabled by default until isolated MySQL and current-actor worker checks pass.
"""
import os
from sqlalchemy import select
from app.core.exceptions import AppException
from app.services.db_service import _tid,session
from app.modules.academic_affairs.optimizer.contracts import InputError,numeric_id
from app.modules.academic_affairs.optimizer.options import normalize_options
from app.modules.academic_affairs.optimizer.source_builder import compile_source
from app.modules.academic_affairs.optimizer.persistence import Repository,snapshots,jobs,unpack_snapshot
from .schedule_optimizer_source_service import capture_source
from . import academic_affairs_autoschedule_service as auto
from . import academic_affairs_schedule_final_service as schedule


def _repository(user):
    def audit(db,action,job_id,detail):
        import json
        from datetime import datetime
        from app.models import AffairsAuditTrail
        db.add(AffairsAuditTrail(tenant_id=_tid(),biz_type='AA_SCHEDULE_CANDIDATE',biz_id=int(job_id),
            action=action,operator=str(user.get('userId') or ''),
            role_name=str(user.get('currentRoleCode') or (user.get('currentRole') or {}).get('roleCode') or ''),
            detail=json.dumps(detail,ensure_ascii=False,sort_keys=True)[:990],occurred_at=datetime.utcnow()))
    def admission(db,snapshot):
        from sqlalchemy import func
        auto._require_school(user,db)
        batch=schedule._load_batch(db,int(snapshot.batch),writable=False,lock=True)
        if batch.status not in {'DRAFT','PRE_PUBLISHED'}:
            raise InputError('BATCH_NOT_EDITABLE','Current batch state changed')
        from . import academic_affairs_schedule_policy as policy
        policy.resolve_scope(db,term_id=batch.term_id,batch_id=batch.id,writable=True)
    return Repository(session,tenant_id=str(_tid()),audit_hook=audit,admission_hook=admission)

def _enabled():
    return os.environ.get('YUEKE_OPTIMIZER_CANDIDATES_ENABLED','')=='1'


def _raise(error):
    if error.code=='QUEUE_BUSY':raise AppException('RATE_LIMITED','Candidate queue is full',http_status=429) from error
    if error.code=='JOB_NOT_FOUND':
        raise AppException('DATA_NOT_FOUND','Candidate job not found',http_status=404) from error
    conflict=any(k in error.code for k in ['VERSION','STALE','CONFLICT','REQUIRED','UNRESOLVED','LIMIT'])
    raise AppException('DATA_CONFLICT' if conflict else 'VALIDATION_ERROR',error.code,
                       details={'reasonCode':error.code,'detail':error.detail},http_status=409 if conflict else 422) from error


def _authorize(user,batch_id):
    try:numeric_id(batch_id,'batchId')
    except InputError as error:_raise(error)
    with session() as db:
        auto._require_school(user,db)
        batch=schedule._load_batch(db,int(batch_id),writable=False,lock=False)
        from .academic_affairs_schedule_write_scope_r3 import assert_schedule_write_scope
        assert_schedule_write_scope(db,user,batch)
        return batch.status


def dispatch_worker(tenant_id):
    from .schedule_optimizer_worker_service import run_pending
    return run_pending(tenant_id)


def context(user,batch_id):
    _authorize(user,batch_id)
    try:
        with session() as db:
            facts,revision=capture_source(db,user,batch_id)
        pending=set(facts['targetTaskIds'])
        from collections import Counter
        counts=Counter(str(row['task_id']) for row in facts['existingItems']
                       if str(row['batch_id'])==str(batch_id) and row.get('task_id'))
        auto_counts=Counter(str(row['task_id']) for row in facts['existingItems']
                            if str(row['batch_id'])==str(batch_id) and row.get('source')=='AUTO')
        tasks=[{**t,'remainingPeriods':t['weekly_hours']-counts[str(t['id'])], 'autoPeriods':auto_counts[str(t['id'])]}
               for t in facts['tasks'] if str(t['id']) in pending]
        return {'sourceRevision':revision,'scope':facts['scope'],'batchStatus':facts['batch']['status'],
            'summary':{'taskCount':len(tasks),'teacherCount':len({k for t in tasks for k in facts['teachers'][str(t['id'])]}),
                       'classCount':len({facts['rosters'][str(t['id'])]['teachingClassId'] for t in tasks}),
                       'roomCount':sum(r['status']=='AVAILABLE' and r['allow_schedule'] and not r['is_exclusive'] for r in facts['rooms']),
                       'existingCount':sum(str(i['batch_id'])==str(batch_id) for i in facts['existingItems']),
                       'missingHeadcount':sum(not t.get('expected_students') for t in tasks),'missingRoster':0},
            'term':facts['term'],'tasks':tasks,
            'rooms':[{'id':str(r['id']),'campus':r['campus_code'],'capacity':r['capacity'],'roomType':r['room_type']} for r in facts['rooms']],
            'slots':facts['slots'],'calendarEvents':facts['events'],'canGenerate':_enabled() and bool(tasks) and facts['batch']['status'] in {'DRAFT','PRE_PUBLISHED'},
            'canApply':False,'previewOnly':True,
            'blockers':[] if _enabled() else [{'code':'MYSQL_AND_WORKER_ACCEPTANCE_REQUIRED'}]}
    except InputError as exc:
        from .schedule_optimizer_readiness_service import readiness
        checked=readiness(user,batch_id)
        return {'sourceRevision':None,'canGenerate':False,'canApply':False,'previewOnly':True,
                'summary':checked['summary'],'blockers':checked['blockers'] or [{'code':exc.code}]}


def enqueue(user,batch_id,body):
    from app.core.permissions import enforce_permission, require_module
    enforce_permission(user,'academicAffairs.schedule.rule.manage')
    require_module('academicAffairs')(user)
    from app.services.module_access_service import assert_module_access
    assert_module_access(_tid(), 'academicAffairs', write=True)
    if not _enabled():
        raise AppException('DATA_CONFLICT','Candidate jobs are disabled until integration acceptance',http_status=409)
    if _authorize(user,batch_id) not in {'DRAFT','PRE_PUBLISHED'}:
        raise AppException('DATA_CONFLICT','Published timetable requires the existing change workflow',http_status=409)
    from app.services.tenant_effective_state_service import background_execution_policy
    if background_execution_policy(_tid()).get('writable') is not True:
        raise AppException('NO_PERMISSION','Current school is not writable',http_status=403)
    try:
        reason=body['reason'].strip()
        if not 5<=len(reason)<=500:raise InputError('REASON_REQUIRED','5..500 characters')
        with session() as db:
            facts,revision=capture_source(db,user,batch_id)
        snapshot,_=compile_source(facts,body['plan'],expected_revision=body['expectedSourceRevision'])
        options=normalize_options(body.get('options',{}),snapshot)
        actor=str(user.get('userId') or '')
        if not actor:raise InputError('ACTOR_REQUIRED','authenticated actor')
        role=user.get('currentRole') or {}
        actor_context={'userId':actor,'tenantId':str(_tid()),
            'roleCode':str(user.get('currentRoleCode') or role.get('roleCode') or ''),
            'activeContextId':str(user.get('activeContextId') or role.get('contextId') or '')}
        repository=_repository(user)
        return repository.enqueue_verified(snapshot,actor=actor,
            idempotency_key=body['idempotencyKey'],options=options,reason=reason,actor_context=actor_context)
    except InputError as exc:_raise(exc)


def get_job(user,batch_id,job_id):
    batch_status=_authorize(user,batch_id)
    try:
        repository=_repository(user)
        result=repository.get(str(_tid()),numeric_id(job_id,'jobId'))
        if result['batchId']!=str(batch_id):raise InputError('JOB_NOT_FOUND','current batch')
        from app.core.permissions import has_permission
        result.update({'previewOnly':False,'canApply':_enabled() and batch_status in {'DRAFT','PRE_PUBLISHED'} and result['state']=='SUCCEEDED'
                       and has_permission(user,'academicAffairs.schedule.edit')
                       and has_permission(user,'academicAffairs.schedule.rule.manage')})
        return result
    except InputError as exc:_raise(exc)


def cancel_job(user,batch_id,job_id,version):
    from app.core.permissions import enforce_permission
    from app.services.module_access_service import assert_module_access
    enforce_permission(user,'academicAffairs.schedule.rule.manage')
    assert_module_access(_tid(),'academicAffairs',write=True)
    get_job(user,batch_id,job_id)  # Scope checked before mutation; row version remains atomic.
    try:return _repository(user).cancel(str(_tid()),job_id,version)
    except InputError as exc:_raise(exc)


def preview_rows(user,batch_id,job_id,task_id=None,week=None):
    import re
    if week is not None and not re.fullmatch(r'W(?:0[1-9]|[12][0-9]|30)',week):
        raise AppException('VALIDATION_ERROR','Invalid teaching week filter',http_status=422)
    result=get_job(user,batch_id,job_id)
    with session() as db:
        record=db.execute(select(jobs.c.snapshot_id).where(jobs.c.tenant_id==_tid(),jobs.c.id==int(job_id),jobs.c.batch_id==int(batch_id))).scalar_one()
        row=db.execute(select(snapshots).where(snapshots.c.id==record,snapshots.c.tenant_id==_tid())).mappings().one()
        snapshot=unpack_snapshot(row)
    provenance=snapshot.raw.get('provenance') or {};bindings=provenance.get('bindings',{})
    task_ids=sorted({a.task_id for a in snapshot.activities},key=int)
    if task_id is not None and task_id not in task_ids:raise AppException('DATA_NOT_FOUND','候选方案中没有该课程',http_status=404)
    rows=[];activities={a.id:a for a in snapshot.activities}
    for aid,oid in (result.get('result') or {}).get('choices',{}).items():
        binding=bindings.get(aid+'|'+oid)
        if not binding:raise AppException('DATA_CONFLICT','Stored candidate binding is incomplete',http_status=409)
        if task_id is not None and binding['taskId']!=task_id:continue
        option=next(o for o in activities[aid].options if o.id==oid)
        for occurrence in option.occurrences:
            if week and occurrence.key!=week:continue
            from datetime import date
            for slot in binding['slotNos']:
                rows.append({'itemId':'candidate:'+aid+':'+occurrence.key+':'+str(slot),
                    'taskId':binding['taskId'],'weekday':date.fromisoformat(occurrence.day).isoweekday(),
                    'teacherKeys':list(activities[aid].teachers),
                    'teachingClassId':binding.get('teachingClassId') or binding['taskId'],
                    'teacherLabels':{k:binding.get('teacherLabels',{}).get(k) or binding.get('teacherName') or k for k in activities[aid].teachers},
                    'slotNo':slot,'classroomId':binding['roomId'],'campus':binding['campus'],
                    'courseName':binding.get('courseName') or '课程名称待补充',
                    'teacherName':binding.get('teacherName',''),'className':binding.get('className',''),
                    'classroom':binding.get('classroomText',''),
                    'startWeek':int(occurrence.key[1:]),'endWeek':int(occurrence.key[1:]),'weekParity':'ALL',
                    'date':occurrence.day,'weekKey':occurrence.key,'candidateOnly':True})
    return {'job':result,'rows':rows[:500],'truncated':len(rows)>500,'taskIds':task_ids,
            'previewOnly':True,'canApply':False,
            'note':'Read-only candidate. Filter by task and teaching week; actual dates govern swaps.'}


def lookup_job(user,batch_id,key):
    _authorize(user,batch_id)
    try:
        job=Repository(session,tenant_id=str(_tid())).find_by_key(str(_tid()),batch_id,key)
        return {'found':job is not None,'job':get_job(user,batch_id,job['jobId']) if job else None,'absenceIsFinal':False}
    except InputError as exc:_raise(exc)
