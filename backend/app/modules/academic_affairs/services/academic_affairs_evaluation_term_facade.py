"""评教服务最终学期写保护层。

评教批次拥有强 ``term_id``。所有写动作都在原事务内回链批次并执行 ``guard_term_writable``：
建批次、生成任务、开关窗口、匿名提交、结果计算、申诉提交与申诉复核。
"""
from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from datetime import datetime

from app.core.exceptions import AppException, not_found

from . import academic_affairs_evaluation_facade as _base

_legacy = _base._legacy
_BATCH_WRITE = ContextVar("aa_evaluation_batch_write", default=False)
_TASK_WRITE = ContextVar("aa_evaluation_task_write", default=False)
_RESULT_WRITE = ContextVar("aa_evaluation_result_write", default=False)
_original_get_batch = _legacy._get_batch
_original_get_task = _legacy._get_task
_original_get_result = _legacy._get_result


def __getattr__(name):
    return getattr(_base, name)


def _guard_term(db, term_id):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    guard_term_writable(db, int(term_id))


def _get_batch(db, batch_id):
    batch = _original_get_batch(db, batch_id)
    if _BATCH_WRITE.get():
        _guard_term(db, batch.term_id)
    return batch


def _get_task(db, task_id):
    task = _original_get_task(db, task_id)
    if _TASK_WRITE.get():
        batch = _original_get_batch(db, task.batch_id)
        _guard_term(db, batch.term_id)
    return task


def _get_result(db, result_id):
    result = _original_get_result(db, result_id)
    if _RESULT_WRITE.get():
        task = _original_get_task(db, result.task_id)
        batch = _original_get_batch(db, task.batch_id)
        _guard_term(db, batch.term_id)
    return result


def _wrap(flag, fn):
    def wrapped(*args, **kwargs):
        token = flag.set(True)
        try:
            return fn(*args, **kwargs)
        finally:
            flag.reset(token)
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    wrapped.__module__ = __name__
    return wrapped


def create_batch(user, body):
    from app.models import AaEvaluationBatch

    with _legacy.session() as db:
        _legacy._require_manage(_legacy._ctx(user, db))
        term_id = getattr(body, "termId", None)
        if not term_id:
            raise _legacy._bad("评教批次必须绑定正式学期termId")
        _guard_term(db, int(term_id))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _legacy._bad("批次名称必填")
        anonymous = bool(getattr(body, "isAnonymous", True))
        if not anonymous:
            raise _legacy._bad("正式学生评教必须匿名，isAnonymous须为true")
        row = AaEvaluationBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            term_id=int(term_id),
            start_at=_legacy._dt(getattr(body, "startAt", None)),
            end_at=_legacy._dt(getattr(body, "endAt", None)),
            is_anonymous=True,
            status=_legacy._EB_DRAFT,
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "AA_EVALUATION_BATCH", row.id, "EVAL_BATCH_CREATE", name)
        db.commit()
        return _legacy._batch_dto(row)


def compute_result(user, task_id, valid_min=3):
    from app.models import AaEvaluationResult, AaEvaluationSubmission, AaEvaluationTask

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        _legacy._require_manage(context)
        task = _original_get_task(db, int(task_id))
        batch = _original_get_batch(db, task.batch_id)
        _guard_term(db, batch.term_id)
        submissions = db.query(AaEvaluationSubmission).filter(
            AaEvaluationSubmission.tenant_id == _legacy._tid(),
            AaEvaluationSubmission.task_id == task.id,
            AaEvaluationSubmission.is_deleted.is_(False),
        ).all()
        count = len(submissions)
        average = round(sum(row.overall_score for row in submissions) / count, 2) if count else None
        valid = count >= int(valid_min)
        result = db.query(AaEvaluationResult).filter(
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.task_id == task.id,
            AaEvaluationResult.is_deleted.is_(False),
        ).first()
        if not result:
            result = AaEvaluationResult(tenant_id=_legacy._tid(), task_id=task.id)
            db.add(result)
        result.average_score = average
        result.submission_count = count
        result.is_valid = valid
        result.invalid_reason = None if valid else f"有效问卷不足{valid_min}份"
        result.generated_at = datetime.utcnow()
        task.submitted_count = count
        task.status = _legacy._ET_SUBMITTED if count else _legacy._ET_DRAFT
        db.flush()
        _legacy._audit(
            db,
            "AA_EVALUATION_RESULT",
            result.id,
            "EVAL_RESULT_COMPUTE",
            f"count={count};valid={valid}",
        )
        db.commit()
        return _legacy._result_dto(result, task)


def review_appeal(user, appeal_id, action, reason=""):
    from app.models import AaEvaluationAppeal, AaEvaluationResult, AaEvaluationTask

    with _legacy.session() as db:
        _legacy._require_manage(_legacy._ctx(user, db))
        appeal = db.query(AaEvaluationAppeal).filter(
            AaEvaluationAppeal.id == int(appeal_id),
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.is_deleted.is_(False),
        ).first()
        if not appeal:
            raise not_found("申诉不存在")
        result = _original_get_result(db, appeal.result_id)
        task = _original_get_task(db, result.task_id)
        batch = _original_get_batch(db, task.batch_id)
        _guard_term(db, batch.term_id)
        if appeal.status not in (_legacy._AP_SUBMITTED, _legacy._AP_REVIEWING):
            raise AppException("APPROVAL_VERSION_CONFLICT", "申诉已终结", http_status=409)
        action = str(action or "").upper()
        reason = (reason or "").strip()
        if action == "REJECT":
            if len(reason) < 5:
                raise _legacy._bad("驳回原因必填且不少于5字")
            appeal.status = _legacy._AP_REJECTED
            appeal.review_reason = reason
        elif action == "RESOLVE":
            if len(reason) < 5:
                raise _legacy._bad("处理说明必填且不少于5字")
            appeal.status = _legacy._AP_RESOLVED
            appeal.review_reason = reason
        elif action == "RECOMPUTE":
            submissions = db.query(__import__(
                "app.models", fromlist=["AaEvaluationSubmission"]
            ).AaEvaluationSubmission).filter(
                __import__("app.models", fromlist=["AaEvaluationSubmission"]).AaEvaluationSubmission.tenant_id == _legacy._tid(),
                __import__("app.models", fromlist=["AaEvaluationSubmission"]).AaEvaluationSubmission.task_id == task.id,
                __import__("app.models", fromlist=["AaEvaluationSubmission"]).AaEvaluationSubmission.is_deleted.is_(False),
            ).all()
            count = len(submissions)
            result.average_score = round(sum(row.overall_score for row in submissions) / count, 2) if count else None
            result.submission_count = count
            result.is_valid = count >= 3
            result.invalid_reason = None if result.is_valid else "有效问卷不足3份"
            result.generated_at = datetime.utcnow()
            appeal.status = _legacy._AP_RESOLVED
            appeal.review_reason = reason or "已重新计算评教结果"
        else:
            raise _legacy._bad("action仅支持 REJECT/RESOLVE/RECOMPUTE")
        appeal.reviewed_at = datetime.utcnow()
        _legacy._audit(db, "AA_EVALUATION_APPEAL", appeal.id, f"EVAL_APPEAL_{action}", appeal.review_reason or "")
        db.commit()
        return _legacy._appeal_dto(appeal, result, task)


_legacy._get_batch = _get_batch
_legacy._get_task = _get_task
_legacy._get_result = _get_result

for _name in ("generate_tasks", "open_batch", "close_batch"):
    _wrapped = _wrap(_BATCH_WRITE, getattr(_legacy, _name))
    globals()[_name] = _wrapped
    setattr(_legacy, _name, _wrapped)

submit = _wrap(_TASK_WRITE, _legacy.submit)
submit_appeal = _wrap(_RESULT_WRITE, _legacy.submit_appeal)
_legacy.submit = submit
_legacy.submit_appeal = submit_appeal
_legacy.create_batch = create_batch
_legacy.compute_result = compute_result
_legacy.review_appeal = review_appeal
