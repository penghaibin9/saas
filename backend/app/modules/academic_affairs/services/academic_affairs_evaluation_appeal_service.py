"""D-W3 evaluation appeal state machine and archive guard.

This module keeps the existing evaluation models/routes/permission codes. It only closes the
business-state and concurrency gaps of the appeal chain:
- appeals are allowed only for the teacher's own published result while the batch is RESULT_READY;
- one result may be appealed only once (the current product policy forbids re-appeal after reject);
- teachers see only their own appeals, college reviewers only their college, TENANT_ALL sees all;
- SUBMITTED must be reviewed by the owning college before TENANT_ALL academic final review;
- batch archive is blocked while SUBMITTED/COLLEGE_REVIEW appeals exist;
- batch/result/appeal locks serialize submit/review/archive races without introducing a migration.
"""
from __future__ import annotations

from app.core.affairs_security import _derive_keys, no_data_scope
from app.core.exceptions import AppException, no_permission, not_found

from . import academic_affairs_evaluation_term_facade as _base

_legacy = _base._legacy
_ACTIVE_APPEAL_STATUSES = ("SUBMITTED", "COLLEGE_REVIEW")


def _published_result_hint(db, result_id: int):
    from app.models import AaEvaluationResult

    result = db.query(AaEvaluationResult).filter(
        AaEvaluationResult.id == int(result_id),
        AaEvaluationResult.tenant_id == _legacy._tid(),
        AaEvaluationResult.is_deleted.is_(False),
    ).first()
    if not result:
        raise not_found("评价结果不存在")
    return result


def _result_for_update(db, result_id: int):
    from app.models import AaEvaluationResult

    result = db.query(AaEvaluationResult).filter(
        AaEvaluationResult.id == int(result_id),
        AaEvaluationResult.tenant_id == _legacy._tid(),
        AaEvaluationResult.is_deleted.is_(False),
    ).populate_existing().with_for_update().first()
    if not result:
        raise not_found("评价结果不存在")
    return result


def _require_result_open_for_appeal(batch, result) -> None:
    if batch.status != _legacy._B_RESULT:
        raise _legacy._invalid("仅 RESULT_READY 批次的已发布评价结果可申诉")
    if not bool(result.published):
        raise _legacy._invalid("评价结果尚未正式发布，不可申诉")
    if int(result.batch_id) != int(batch.id):
        raise AppException("DATA_CONFLICT", "评价结果与评教批次关系已变化，请刷新后重试", http_status=409)


def _require_teacher_owner(user, result) -> None:
    keys = _derive_keys(user)
    if not result.teacher_key or result.teacher_key not in keys:
        raise no_permission("仅被评价教师本人可对该结果发起申诉")


def _college_id_for_result(db, result) -> int:
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    if not result.teaching_task_id:
        raise AppException("DATA_CONFLICT", "评价结果未绑定正式教学任务，无法确定学院审核范围", http_status=409)
    row = db.query(AaTeachingTaskBatch.college_id).join(
        AaTeachingTask,
        AaTeachingTask.batch_id == AaTeachingTaskBatch.id,
    ).filter(
        AaTeachingTask.id == int(result.teaching_task_id),
        AaTeachingTask.tenant_id == _legacy._tid(),
        AaTeachingTask.is_deleted.is_(False),
        AaTeachingTaskBatch.tenant_id == _legacy._tid(),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).first()
    college_id = row[0] if row else None
    if college_id is None:
        raise AppException("DATA_CONFLICT", "评价结果对应教学任务缺少学院归属，禁止跳过学院初审", http_status=409)
    return int(college_id)


def _require_college_review_scope(db, context, result) -> int:
    if context.scope_type != "COLLEGE":
        raise no_data_scope("评价申诉必须先由所属学院完成初审")
    college_id = _college_id_for_result(db, result)
    allowed = {int(value) for value in (context.college_ids or set())}
    if college_id not in allowed:
        raise no_data_scope("该评价申诉不在您的学院数据范围内")
    return college_id


def _require_academic_final_scope(context) -> None:
    if context.scope_type != "TENANT_ALL":
        raise no_data_scope("学院初审通过后，仅教务处/学校级教务管理可完成终审")


def list_appeals(user, status=None):
    """List appeals by canonical scope: self teacher / owning college / tenant-wide academic."""
    from app.models import AaEvaluationAppeal, AaEvaluationResult, AaTeachingTask, AaTeachingTaskBatch

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        query = db.query(AaEvaluationAppeal).join(
            AaEvaluationResult,
            AaEvaluationResult.id == AaEvaluationAppeal.result_id,
        ).outerjoin(
            AaTeachingTask,
            AaTeachingTask.id == AaEvaluationResult.teaching_task_id,
        ).outerjoin(
            AaTeachingTaskBatch,
            AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
        ).filter(
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.is_deleted.is_(False),
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.is_deleted.is_(False),
        )
        if status:
            query = query.filter(AaEvaluationAppeal.status == status)

        if context.scope_type == "TENANT_ALL":
            pass
        elif context.scope_type == "COLLEGE":
            allowed_colleges = {int(value) for value in (context.college_ids or set())}
            if not allowed_colleges:
                return []
            query = query.filter(
                AaTeachingTask.tenant_id == _legacy._tid(),
                AaTeachingTask.is_deleted.is_(False),
                AaTeachingTaskBatch.tenant_id == _legacy._tid(),
                AaTeachingTaskBatch.is_deleted.is_(False),
                AaTeachingTaskBatch.college_id.in_(allowed_colleges),
            )
        else:
            keys = _derive_keys(user)
            if not keys:
                return []
            query = query.filter(
                AaEvaluationAppeal.teacher_key.in_(list(keys)),
                AaEvaluationResult.teacher_key.in_(list(keys)),
            )

        rows = query.order_by(AaEvaluationAppeal.id.desc()).all()
        return [{
            "appealId": str(row.id),
            "resultId": str(row.result_id),
            "reason": row.reason,
            "reviewReason": row.review_reason,
            "currentNode": row.current_node,
            "status": row.status,
        } for row in rows]


def archive_batch(user, bid):
    """Archive one RESULT_READY batch only when no active appeal remains."""
    from app.models import AaEvaluationAppeal, AaEvaluationResult

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _base._writable_batch(db, bid, lock="update")
        if batch.status == _legacy._B_ARCHIVED:
            return _legacy._batch_dto(batch)
        if batch.status != _legacy._B_RESULT:
            raise _legacy._invalid("仅 RESULT_READY 批次可归档")

        # Locking/current read is deliberate under MySQL REPEATABLE READ: after waiting for any
        # in-flight appeal shared lock, archive must observe the just-committed appeal state.
        active = db.query(AaEvaluationAppeal.id).join(
            AaEvaluationResult,
            AaEvaluationResult.id == AaEvaluationAppeal.result_id,
        ).filter(
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.status.in_(_ACTIVE_APPEAL_STATUSES),
            AaEvaluationAppeal.is_deleted.is_(False),
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.batch_id == batch.id,
            AaEvaluationResult.is_deleted.is_(False),
        ).with_for_update().first()
        if active:
            raise _legacy._invalid("该评教批次存在未完成评价申诉，不可归档")

        batch.status = _legacy._B_ARCHIVED
        _legacy._audit(db, batch.id, "EVAL_BATCH_ARCHIVE", "归档")
        db.commit()
        return _legacy._batch_dto(batch)


def submit_appeal(user, result_id, reason):
    """Submit exactly one appeal for the caller's own published evaluation result."""
    from app.models import AaEvaluationAppeal

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("申诉理由必填且不少于5字")

    with _legacy.session() as db:
        _legacy._ctx(user, db)
        hint = _published_result_hint(db, int(result_id))
        # Shared batch lock prevents publish/archive state from changing while the appeal commits.
        batch = _base._writable_batch(db, hint.batch_id, lock="share")
        result = _result_for_update(db, int(result_id))
        _require_result_open_for_appeal(batch, result)
        _require_teacher_owner(user, result)

        # Result row lock serializes same-result submissions. The appeal lookup is also a locking
        # current read so a waiter cannot miss the winner's committed row under REPEATABLE READ.
        existing = db.query(AaEvaluationAppeal).filter(
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.result_id == result.id,
            AaEvaluationAppeal.is_deleted.is_(False),
        ).with_for_update().first()
        if existing:
            raise _legacy._invalid("该评价结果已提交过申诉，当前规则不允许重复申诉")

        appeal = AaEvaluationAppeal(
            tenant_id=_legacy._tid(),
            result_id=result.id,
            teacher_key=result.teacher_key,
            reason=reason,
            current_node="COLLEGE",
            status="SUBMITTED",
        )
        db.add(appeal)
        db.flush()
        _legacy._audit(db, appeal.id, "EVAL_APPEAL_SUBMIT", "提交学院初审")
        db.commit()
        return {
            "appealId": str(appeal.id),
            "status": appeal.status,
            "currentNode": appeal.current_node,
        }


def review_appeal(user, appeal_id, action, reason=""):
    """Review one appeal strictly as COLLEGE initial review then TENANT_ALL final review."""
    from app.models import AaEvaluationAppeal, AaEvaluationResult

    action = str(action or "").upper()
    if action not in {"RESOLVE", "REJECT"}:
        raise _legacy._bad("非法动作")
    note = (reason or "").strip()
    if len(note) < 5:
        raise _legacy._bad("审核意见必填且不少于5字")

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        hint = db.query(AaEvaluationAppeal).filter(
            AaEvaluationAppeal.id == int(appeal_id),
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.is_deleted.is_(False),
        ).first()
        if not hint:
            raise not_found("申诉不存在")
        result_hint = _published_result_hint(db, hint.result_id)
        batch = _base._writable_batch(db, result_hint.batch_id, lock="share")

        appeal = db.query(AaEvaluationAppeal).filter(
            AaEvaluationAppeal.id == int(appeal_id),
            AaEvaluationAppeal.tenant_id == _legacy._tid(),
            AaEvaluationAppeal.is_deleted.is_(False),
        ).populate_existing().with_for_update().first()
        if not appeal:
            raise not_found("申诉不存在")
        result = db.query(AaEvaluationResult).filter(
            AaEvaluationResult.id == appeal.result_id,
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.is_deleted.is_(False),
        ).first()
        if not result:
            raise AppException("DATA_CONFLICT", "申诉未关联有效评价结果", http_status=409)
        _require_result_open_for_appeal(batch, result)

        if appeal.status == "SUBMITTED":
            _require_college_review_scope(db, context, result)
            stage = "COLLEGE"
        elif appeal.status == "COLLEGE_REVIEW":
            _require_academic_final_scope(context)
            stage = "ACADEMIC"
        else:
            raise _legacy._invalid("该申诉已处理")

        if action == "REJECT":
            appeal.status = "REJECTED"
            appeal.current_node = None
        elif stage == "COLLEGE":
            appeal.status = "COLLEGE_REVIEW"
            appeal.current_node = "ACADEMIC"
        else:
            appeal.status = "RESOLVED"
            appeal.current_node = None
        appeal.review_reason = note

        audit_action = (
            "EVAL_APPEAL_COLLEGE_REVIEW" if stage == "COLLEGE"
            else "EVAL_APPEAL_ACADEMIC_REVIEW"
        )
        _legacy._audit(db, appeal.id, audit_action, f"{action}: {note}")
        db.commit()
        return {
            "appealId": str(appeal.id),
            "status": appeal.status,
            "currentNode": appeal.current_node,
        }
