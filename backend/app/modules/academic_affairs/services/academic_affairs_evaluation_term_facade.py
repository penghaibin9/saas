"""评教服务最终学期写保护层。

评教批次拥有强 ``term_id``。所有真实写动作均在原事务内回链批次并执行
``guard_term_writable``：建批次、生成任务、窗口流转、提交评价、核算/发布结果、提交/处理申诉。
"""
from __future__ import annotations

import json
from contextvars import ContextVar

from app.core.affairs_security import _derive_keys, no_data_scope
from app.core.exceptions import AppException, not_found

from . import academic_affairs_evaluation_facade as _base

_legacy = _base._legacy
_BATCH_WRITE = ContextVar("aa_evaluation_batch_write", default=False)
_original_get_batch = _legacy._get_batch


def __getattr__(name):
    return getattr(_base, name)


def _guard_term(db, term_id):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    if not term_id:
        raise AppException("DATA_CONFLICT", "评教业务未绑定正式学期termId", http_status=409)
    guard_term_writable(db, int(term_id))


def _get_batch(db, batch_id):
    batch = _original_get_batch(db, int(batch_id))
    if _BATCH_WRITE.get():
        _guard_term(db, batch.term_id)
    return batch


def _wrap_batch(fn):
    def wrapped(*args, **kwargs):
        token = _BATCH_WRITE.set(True)
        try:
            return fn(*args, **kwargs)
        finally:
            _BATCH_WRITE.reset(token)
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    wrapped.__module__ = __name__
    return wrapped


def create_batch(user, body):
    from app.models import AaEvaluationBatch, AaTerm

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        term_id = getattr(body, "termId", None)
        if not term_id:
            raise _legacy._bad("评教批次必须绑定正式学期termId")
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id),
            AaTerm.tenant_id == _legacy._tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            raise not_found("学期不存在")
        _guard_term(db, term.id)
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _legacy._bad("批次名称必填")
        row = AaEvaluationBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            term_id=term.id,
            scope_json=(
                json.dumps(getattr(body, "scope", None), ensure_ascii=False)
                if getattr(body, "scope", None) else None
            ),
            template_json=(
                json.dumps(getattr(body, "template", None), ensure_ascii=False)
                if getattr(body, "template", None) else None
            ),
            anonymous=bool(getattr(body, "anonymous", True)),
            status=_legacy._B_DRAFT,
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, row.id, "EVAL_BATCH_CREATE", name)
        db.commit()
        return _legacy._batch_dto(row)


def submit_appeal(user, result_id, reason):
    from app.models import AaEvaluationAppeal, AaEvaluationBatch, AaEvaluationResult

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("申诉理由必填且不少于5字")
    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        result = db.query(AaEvaluationResult).filter(
            AaEvaluationResult.id == int(result_id),
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.is_deleted.is_(False),
        ).first()
        if not result:
            raise not_found("评价结果不存在")
        batch = db.query(AaEvaluationBatch).filter(
            AaEvaluationBatch.id == result.batch_id,
            AaEvaluationBatch.tenant_id == _legacy._tid(),
            AaEvaluationBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise AppException("DATA_CONFLICT", "评价结果未关联有效评教批次", http_status=409)
        _guard_term(db, batch.term_id)
        if ctx.scope_type != "TENANT_ALL":
            if not result.teacher_key or result.teacher_key not in _derive_keys(user):
                raise no_data_scope("仅可对本人的评价结果发起申诉")
        active = db.query(AaEvaluationAppeal).filter(
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.result_id == result.id,
            AaEvaluationAppeal.status.in_(["SUBMITTED", "COLLEGE_REVIEW"]),
            AaEvaluationAppeal.is_deleted.is_(False),
        ).first()
        if active:
            raise _legacy._invalid("该评价结果已有在途申诉")
        appeal = AaEvaluationAppeal(
            tenant_id=_legacy._tid(),
            result_id=result.id,
            teacher_key=_legacy._tkey(),
            reason=reason,
            current_node="COLLEGE",
            status="COLLEGE_REVIEW",
        )
        db.add(appeal)
        db.flush()
        _legacy._audit(db, appeal.id, "EVAL_APPEAL_SUBMIT", "申诉")
        db.commit()
        return {"appealId": str(appeal.id), "status": appeal.status}


def review_appeal(user, appeal_id, action, reason=""):
    from app.models import AaEvaluationAppeal, AaEvaluationBatch, AaEvaluationResult

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        appeal = db.query(AaEvaluationAppeal).filter(
            AaEvaluationAppeal.id == int(appeal_id),
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.is_deleted.is_(False),
        ).first()
        if not appeal:
            raise not_found("申诉不存在")
        result = db.query(AaEvaluationResult).filter(
            AaEvaluationResult.id == appeal.result_id,
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.is_deleted.is_(False),
        ).first()
        if not result:
            raise AppException("DATA_CONFLICT", "申诉未关联有效评价结果", http_status=409)
        batch = db.query(AaEvaluationBatch).filter(
            AaEvaluationBatch.id == result.batch_id,
            AaEvaluationBatch.tenant_id == _legacy._tid(),
            AaEvaluationBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise AppException("DATA_CONFLICT", "评价结果未关联有效评教批次", http_status=409)
        _guard_term(db, batch.term_id)
        if appeal.status not in ("SUBMITTED", "COLLEGE_REVIEW"):
            raise _legacy._invalid("该申诉已处理")
        action = str(action or "").upper()
        if action == "RESOLVE":
            appeal.status = "RESOLVED"
            appeal.review_reason = (reason or "").strip() or None
        elif action == "REJECT":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _legacy._bad("驳回原因必填且不少于5字")
            appeal.status = "REJECTED"
            appeal.review_reason = reason
        else:
            raise _legacy._bad("非法动作")
        _legacy._audit(db, appeal.id, "EVAL_APPEAL_REVIEW", action)
        db.commit()
        return {"appealId": str(appeal.id), "status": appeal.status}


# 原服务所有批次型写动作都通过_get_batch；ContextVar确保校验发生在同一事务内。
_legacy._get_batch = _get_batch
for _name in (
    "generate_tasks",
    "generate_role_tasks",
    "publish_batch",
    "open_batch",
    "archive_batch",
    "close_and_score",
    "publish_results",
    "submit_evaluation",
):
    _wrapped = _wrap_batch(getattr(_legacy, _name))
    globals()[_name] = _wrapped
    setattr(_legacy, _name, _wrapped)

_legacy.create_batch = create_batch
_legacy.submit_appeal = submit_appeal
_legacy.review_appeal = review_appeal
