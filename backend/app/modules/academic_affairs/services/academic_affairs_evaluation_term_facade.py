"""评教服务最终公开入口。

评教批次拥有强 ``term_id``。所有真实写动作都在自身事务内回链批次并执行
``guard_term_writable``：建批次、生成任务、窗口流转、提交评价、核算/发布结果、提交/处理申诉。
本模块不覆盖旧 Service 函数，不依赖导入顺序安装写保护。
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.affairs_security import _derive_keys, no_data_scope
from app.core.exceptions import AppException, no_permission, not_found

from . import academic_affairs_evaluation_facade as _base

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def _guard_term(db, term_id):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    if not term_id:
        raise AppException("DATA_CONFLICT", "评教业务未绑定正式学期termId", http_status=409)
    guard_term_writable(db, int(term_id))


def _writable_batch(db, batch_id):
    batch = _legacy._get_batch(db, int(batch_id))
    _guard_term(db, batch.term_id)
    return batch


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


def generate_tasks(user, bid, teaching_task_ids, evaluator_type="STUDENT"):
    from app.models import AaEvaluationTask, AaTeachingTask

    evaluator_type = (evaluator_type or "STUDENT").upper()
    if evaluator_type != "STUDENT":
        raise _legacy._bad(
            "本入口仅支持 STUDENT 评教；SELF/PEER/SUPERVISOR 请使用 /role-tasks 并指定 evaluatorKey"
        )
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _writable_batch(db, bid)
        if batch.status != _legacy._B_DRAFT:
            raise _legacy._invalid("仅 DRAFT 批次可生成应评任务")
        count = 0
        for teaching_task_id in [int(value) for value in teaching_task_ids if str(value).isdigit()]:
            teaching_task = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == teaching_task_id,
                AaTeachingTask.tenant_id == _legacy._tid(),
            ).first()
            if not teaching_task:
                continue
            duplicate = db.query(AaEvaluationTask).filter(
                AaEvaluationTask.tenant_id == _legacy._tid(),
                AaEvaluationTask.batch_id == batch.id,
                AaEvaluationTask.teaching_task_id == teaching_task_id,
                AaEvaluationTask.evaluator_type == evaluator_type,
            ).first()
            if duplicate:
                continue
            db.add(AaEvaluationTask(
                tenant_id=_legacy._tid(),
                batch_id=batch.id,
                teaching_task_id=teaching_task_id,
                course_id=getattr(teaching_task, "course_id", None),
                course_name=getattr(teaching_task, "course_name", None),
                class_id=getattr(teaching_task, "class_id", None),
                teacher_key=getattr(teaching_task, "teacher_key", None),
                teacher_name=getattr(teaching_task, "teacher_name", None),
                evaluator_type=evaluator_type,
                status="PENDING",
            ))
            count += 1
        _legacy._audit(db, batch.id, "EVAL_TASK_GENERATE", f"{evaluator_type} {count} 条应评任务")
        db.commit()
        return {"batchId": str(batch.id), "taskCount": count, "evaluatorType": evaluator_type}


def generate_role_tasks(user, bid, evaluator_type, assignments):
    from app.models import AaEvaluationTask, AaTeachingTask

    evaluator_type = str(evaluator_type or "").upper()
    if evaluator_type not in _legacy._ROLE_EVAL_TYPES:
        raise _legacy._bad("非法评价类型，仅支持 SELF/PEER/SUPERVISOR")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _writable_batch(db, bid)
        if batch.status != _legacy._B_DRAFT:
            raise _legacy._invalid("仅 DRAFT 批次可生成应评任务")
        count = 0
        for assignment in assignments or []:
            teaching_task_id = (
                assignment.get("teachingTaskId")
                if isinstance(assignment, dict)
                else getattr(assignment, "teachingTaskId", None)
            )
            if not (teaching_task_id and str(teaching_task_id).isdigit()):
                continue
            teaching_task_id = int(teaching_task_id)
            teaching_task = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == teaching_task_id,
                AaTeachingTask.tenant_id == _legacy._tid(),
            ).first()
            if not teaching_task:
                continue
            evaluator_key = (
                assignment.get("evaluatorKey")
                if isinstance(assignment, dict)
                else getattr(assignment, "evaluatorKey", None)
            )
            evaluator_key = str(evaluator_key or "").strip()
            if evaluator_type == "SELF":
                evaluator_key = evaluator_key or str(getattr(teaching_task, "teacher_key", None) or "")
            if not evaluator_key:
                raise _legacy._bad(f"{evaluator_type} 类型必须指定评价人 evaluatorKey")
            duplicate = db.query(AaEvaluationTask).filter(
                AaEvaluationTask.tenant_id == _legacy._tid(),
                AaEvaluationTask.batch_id == batch.id,
                AaEvaluationTask.teaching_task_id == teaching_task_id,
                AaEvaluationTask.evaluator_type == evaluator_type,
                AaEvaluationTask.evaluator_key == evaluator_key,
            ).first()
            if duplicate:
                continue
            db.add(AaEvaluationTask(
                tenant_id=_legacy._tid(),
                batch_id=batch.id,
                teaching_task_id=teaching_task_id,
                course_id=getattr(teaching_task, "course_id", None),
                course_name=getattr(teaching_task, "course_name", None),
                class_id=getattr(teaching_task, "class_id", None),
                teacher_key=getattr(teaching_task, "teacher_key", None),
                teacher_name=getattr(teaching_task, "teacher_name", None),
                evaluator_type=evaluator_type,
                evaluator_key=evaluator_key,
                status="PENDING",
            ))
            count += 1
        _legacy._audit(db, batch.id, "EVAL_TASK_GENERATE", f"{evaluator_type} {count} 条应评任务")
        db.commit()
        return {"batchId": str(batch.id), "evaluatorType": evaluator_type, "taskCount": count}


def publish_batch(user, bid):
    from app.models import AaEvaluationTask

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _writable_batch(db, bid)
        if batch.status != _legacy._B_DRAFT:
            raise _legacy._invalid("仅 DRAFT 批次可发布")
        count = db.query(AaEvaluationTask).filter(
            AaEvaluationTask.batch_id == batch.id,
            AaEvaluationTask.tenant_id == _legacy._tid(),
        ).count()
        if not count:
            raise _legacy._bad("批次无应评任务，不可发布")
        batch.status = _legacy._B_PUBLISHED
        _legacy._audit(db, batch.id, "EVAL_BATCH_PUBLISH", "发布")
        db.commit()
        return _legacy._batch_dto(batch)


def open_batch(user, bid):
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _writable_batch(db, bid)
        if batch.status != _legacy._B_PUBLISHED:
            raise _legacy._invalid(f"仅 PUBLISHED 批次可OPEN，当前 {batch.status}")
        batch.status = _legacy._B_OPEN
        _legacy._audit(db, batch.id, "EVAL_BATCH_OPEN", "OPEN")
        db.commit()
        return _legacy._batch_dto(batch)


def archive_batch(user, bid):
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _writable_batch(db, bid)
        if batch.status == _legacy._B_ARCHIVED:
            return _legacy._batch_dto(batch)
        if batch.status != _legacy._B_RESULT:
            raise _legacy._invalid("仅 RESULT_READY 批次可归档")
        batch.status = _legacy._B_ARCHIVED
        _legacy._audit(db, batch.id, "EVAL_BATCH_ARCHIVE", "归档")
        db.commit()
        return _legacy._batch_dto(batch)


def close_and_score(user, bid):
    from app.models import AaEvaluationRecord, AaEvaluationResult, AaEvaluationTask

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _writable_batch(db, bid)
        if batch.status != _legacy._B_OPEN:
            raise _legacy._invalid("仅 OPEN 批次可关闭核算")
        tasks = db.query(AaEvaluationTask).filter(
            AaEvaluationTask.batch_id == batch.id,
            AaEvaluationTask.tenant_id == _legacy._tid(),
        ).all()
        aggregate = {}
        metadata = {}
        for task in tasks:
            records = db.query(AaEvaluationRecord).filter(
                AaEvaluationRecord.task_id == task.id,
                AaEvaluationRecord.tenant_id == _legacy._tid(),
            ).all()
            scores = [float(record.objective_score) for record in records if record.objective_score is not None]
            aggregate.setdefault(task.teaching_task_id, {}).setdefault(task.evaluator_type, []).extend(scores)
            metadata[task.teaching_task_id] = (task.teacher_key, task.teacher_name, task.course_name)
        for teaching_task_id, by_type in aggregate.items():
            def average(evaluator_type):
                values = by_type.get(evaluator_type, [])
                return (round(sum(values) / len(values), 2) if values else None), len(values)

            student_average, student_count = average("STUDENT")
            self_average, _self_count = average("SELF")
            peer_average, peer_count = average("PEER")
            supervisor_average, supervisor_count = average("SUPERVISOR")
            composite = _legacy._composite(
                student_average,
                self_average,
                peer_average,
                supervisor_average,
            )
            teacher_key, teacher_name, course_name = metadata[teaching_task_id]
            result = db.query(AaEvaluationResult).filter(
                AaEvaluationResult.tenant_id == _legacy._tid(),
                AaEvaluationResult.batch_id == batch.id,
                AaEvaluationResult.teaching_task_id == teaching_task_id,
            ).first()
            if not result:
                result = AaEvaluationResult(
                    tenant_id=_legacy._tid(),
                    batch_id=batch.id,
                    teaching_task_id=teaching_task_id,
                    teacher_key=teacher_key,
                    teacher_name=teacher_name,
                    course_name=course_name,
                    published=False,
                )
                db.add(result)
            result.student_avg = student_average
            result.student_count = student_count
            result.self_score = self_average
            result.peer_avg = peer_average
            result.peer_count = peer_count
            result.supervisor_avg = supervisor_average
            result.supervisor_count = supervisor_count
            result.composite_score = composite
            result.level = _legacy._level(composite if composite is not None else student_average)
        batch.status = _legacy._B_RESULT
        batch.result_published_at = datetime.utcnow()
        _legacy._audit(db, batch.id, "EVAL_BATCH_SCORE", f"多来源核算 {len(aggregate)} 门结果")
        db.commit()
        return _legacy._batch_dto(batch)


def publish_results(user, bid):
    from app.models import AaEvaluationResult

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _writable_batch(db, bid)
        if batch.status != _legacy._B_RESULT:
            raise _legacy._invalid("仅 RESULT_READY 批次可发布结果")
        db.query(AaEvaluationResult).filter(
            AaEvaluationResult.batch_id == batch.id,
            AaEvaluationResult.tenant_id == _legacy._tid(),
        ).update({AaEvaluationResult.published: True}, synchronize_session=False)
        _legacy._audit(db, batch.id, "EVAL_RESULT_PUBLISH", "发布结果")
        db.commit()
        return {"batchId": str(batch.id), "published": True}


def submit_evaluation(user, task_id, answers, objective_score, comment=None):
    from app.models import AaEvaluationRecord, AaEvaluationTask

    with _legacy.session() as db:
        _legacy._ctx(user, db)
        task = db.query(AaEvaluationTask).filter(
            AaEvaluationTask.id == int(task_id),
            AaEvaluationTask.tenant_id == _legacy._tid(),
        ).first()
        if not task:
            raise not_found("应评任务不存在")
        if task.evaluator_type != "STUDENT":
            keys = _derive_keys(user)
            if not task.evaluator_key or task.evaluator_key not in keys:
                raise no_permission("仅本任务指定的评价人本人可提交")
            if task.status == "SUBMITTED":
                raise _legacy._invalid("该任务已提交，不可重复提交")
        batch = _writable_batch(db, task.batch_id)
        if batch.status != _legacy._B_OPEN:
            raise _legacy._invalid("评教窗口未开放")
        record = AaEvaluationRecord(
            tenant_id=_legacy._tid(),
            batch_id=batch.id,
            task_id=task.id,
            teacher_key=task.teacher_key,
            evaluator_type=task.evaluator_type,
            answers_json=json.dumps(answers, ensure_ascii=False) if answers else None,
            objective_score=objective_score,
            comment=comment,
        )
        db.add(record)
        task.submitted_count = (task.submitted_count or 0) + 1
        if task.evaluator_type != "STUDENT":
            task.status = "SUBMITTED"
        db.flush()
        _legacy._audit(
            db,
            task.id,
            "EVAL_SUBMIT",
            f"{task.evaluator_type} 提交" + ("(匿名)" if task.evaluator_type == "STUDENT" else ""),
        )
        db.commit()
        return {"taskId": str(task.id), "submittedCount": task.submitted_count}


def submit_appeal(user, result_id, reason):
    from app.models import AaEvaluationAppeal, AaEvaluationBatch, AaEvaluationResult

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _legacy._bad("申诉理由必填且不少于5字")
    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
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
        if context.scope_type != "TENANT_ALL":
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
