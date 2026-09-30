"""Recover only warning effects; this module never calls the grade publisher."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import uuid4
import logging

from sqlalchemy import and_, or_, select, text

from app.core.exceptions import AppException
from app.models.academic_grade_effect_job import AcademicGradeEffectJob as Job
from app.services.db_service import _tid, session

log = logging.getLogger(__name__)


def enqueue_grade_warning_scan(db, grade_task_id, *, correction_request_id=None):
    """Called before the existing grade transaction commits; never commits by itself."""
    job = Job(tenant_id=_tid(), grade_task_id=int(grade_task_id), state='PENDING',
              source_kind='CORRECTION' if correction_request_id is not None else 'PUBLISH',
              source_id=int(correction_request_id if correction_request_id is not None else grade_task_id))
    db.add(job)
    db.flush()
    return job.id


def _query(job_id=None):
    query = select(Job).where(Job.tenant_id == _tid(), Job.is_deleted.is_(False))
    return query.where(Job.id == int(job_id)) if job_id is not None else query


def effect_receipt(job):
    return {
        'warningScanJobId': str(job.id),
        'warningScanState': job.state,
        'warningScanOk': job.state == 'SUCCEEDED',
        'warningScanError': None if job.state == 'SUCCEEDED' else '预警扫描尚未完成，结果待核对；请勿重复发布成绩。',
        'warningScanResult': job.result_json,
        'notificationState': 'NOT_VERIFIED',
    }


def publication_effect(user, task_id):
    """Read a visible task's publication effect; never claim or replay it.

    Tenant-wide scan counts are deliberately not exposed through a task-scoped read.
    """
    from app.core.exceptions import not_found
    from . import academic_affairs_grade_task_read_service as tasks

    with session() as db:
        found = db.execute(tasks._base_query().where(
            *tasks._scope_conditions(db, user, task_id=int(task_id))
        )).first()
        if not found:
            raise not_found('成绩任务不存在或不在当前范围内')
        task = found[0]
        job = db.scalars(_query().where(Job.grade_task_id == task.id,
                                       Job.source_kind == 'PUBLISH',
                                       Job.source_id == task.id)).first()
        result = effect_receipt(job) if job else {
            'warningScanJobId': None, 'warningScanState': 'NOT_RECORDED',
            'warningScanOk': None, 'warningScanError': '没有该任务的持久化扫描记录，扫描结果待核对。',
            'notificationState': 'NOT_VERIFIED',
        }
        result.pop('warningScanResult', None)
        return {'gradeTaskId': str(task.id), 'status': task.status, **result}


@contextmanager
def warning_scan_lock():
    """Serialize fail-course scans for one tenant, including manual scans."""
    with session() as db:
        if db.get_bind().dialect.name != 'mysql':
            raise RuntimeError('Durable academic warning effects require MySQL')
        key = f'aa:grade-warning:{_tid()}'
        acquired = db.scalar(text('SELECT GET_LOCK(:key, 0)'), {'key': key})
        if acquired != 1:
            raise AppException('DATA_CONFLICT', '本校预警扫描正在处理，请稍后核对', http_status=409)
        try:
            yield
        finally:
            try:
                db.scalar(text('SELECT RELEASE_LOCK(:key)'), {'key': key})
            except Exception:
                # MySQL releases the lock if its owning connection is lost.
                log.exception('Failed to release academic warning scan lock')


def lock_effect_for_scan(db, job_id, lease_token):
    """Hold the effect row until warning facts and SUCCEEDED commit together."""
    job = db.scalars(_query(job_id).with_for_update().execution_options(populate_existing=True)).first()
    if not job or job.state != 'RUNNING' or job.lease_token != lease_token:
        raise AppException('DATA_CONFLICT', '扫描任务租约已变化，停止旧执行', http_status=409)
    return job


def finish_effect_in_scan(job, result):
    # The warning scanner's existing transaction performs the only commit.
    job.state = 'SUCCEEDED'
    job.result_json = {**result, 'notificationState': 'NOT_VERIFIED'}
    job.completed_at = datetime.utcnow()
    job.lease_token = None
    job.lease_until = None
    job.last_error = None


def run_effect(job_id=None, user=None, *, enforce_background_policy=True):
    """Claim one due effect. Crashed workers are recoverable after their lease expires.

    Scheduled/background workers must obey the tenant lifecycle gate. A synchronous
    post-commit continuation belongs to the request that already passed its write gate,
    so it must be allowed to finish the durable effect it just created.
    """
    if enforce_background_policy:
        from app.services.tenant_effective_state_service import background_execution_policy
        if not background_execution_policy(_tid()).get('writable'):
            return None
    now = datetime.utcnow()
    with session() as db:
        # Background workers must respect retry backoff. A synchronous post-commit
        # continuation for one exact job has just committed that job and should claim
        # PENDING/RETRY immediately; otherwise MySQL DATETIME precision can leave the
        # final-approval receipt stuck at PENDING until a later worker happens to run.
        pending_due = (
            Job.state.in_(('PENDING', 'RETRY'))
            if job_id is not None and not enforce_background_policy
            else and_(Job.state.in_(('PENDING', 'RETRY')), Job.next_run_at <= now)
        )
        runnable = or_(
            pending_due,
            and_(Job.state == 'RUNNING', Job.lease_until <= now),
        )
        job = db.scalars(_query(job_id).where(runnable).order_by(Job.next_run_at, Job.id)
                         .limit(1).with_for_update(skip_locked=True)).first()
        if job is None:
            current = db.scalars(_query(job_id)).first() if job_id is not None else None
            return effect_receipt(current) if current else None
        claimed_id = job.id
        token = str(uuid4())
        job.state, job.lease_token = 'RUNNING', token
        job.attempts += 1
        job.lease_until = now + timedelta(minutes=5)
        db.commit()
    try:
        # Explicit canonical bounded reader; no dependency on router import order.
        from .academic_affairs_warning_effective_grade_guard import scan_warnings
        scan_warnings(user or {}, effect_job=(claimed_id, token))
    except Exception as exc:
        log.exception('Academic grade effect failed job=%s', claimed_id)
        with session() as db:
            job = db.scalars(_query(claimed_id).with_for_update()).first()
            if job and job.state == 'RUNNING' and job.lease_token == token:
                job.state = 'RETRY'
                job.next_run_at = datetime.utcnow() + timedelta(seconds=min(3600, 5 * 2 ** min(job.attempts, 10)))
                job.last_error = type(exc).__name__[:200]
                job.lease_token, job.lease_until = None, None
                db.commit()
    with session() as db:
        job = db.scalars(_query(claimed_id)).first()
        return effect_receipt(job) if job else None


def try_run_effect(job_id, user):
    """An effect failure must never turn a committed publication into an error receipt."""
    try:
        result = run_effect(job_id, user, enforce_background_policy=False)
        if result is not None:
            return result
    except Exception:
        log.exception('Academic grade effect receipt unavailable job=%s', job_id)
    return {
        'warningScanJobId': str(job_id), 'warningScanState': 'UNKNOWN',
        'warningScanOk': False,
        'warningScanError': '正式成绩已提交，预警扫描结果待核对；请勿重复发布成绩。',
        'warningScanResult': None, 'notificationState': 'NOT_VERIFIED',
    }
