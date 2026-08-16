"""D-W3 teaching-evaluation scoped read projection and close/score implementation.

Permission grants and data scope are independent authorities. ``evaluation.view`` is also
used by ordinary teachers for self-service endpoints, so full management reads are narrowed
here instead of widening every holder to tenant-wide visibility.

No new evaluation truth is introduced. State machine, DTOs, anonymity, batch lock protocol
and composite-score policy remain owned by the canonical evaluation service. During OPEN
windows, submission counts are projected from active answer facts so student submissions do
not serialize on a shared task counter row; close/score reconciles the legacy projection.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, case, func, or_, select

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import not_found

from . import academic_affairs_evaluation_term_facade as _base

_legacy = _base._legacy


def _page(page, page_size, *, default_size: int, max_size: int = 100) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = int(page_size or default_size)
    if page_size < 1 or page_size > max_size:
        raise _legacy._bad(f"pageSize 必须在 1-{max_size} 之间")
    return page, page_size


def _scope_spec(user, db) -> dict:
    """Resolve evaluation visibility without inventing a new global COURSE scope type."""
    ctx = build_affairs_context(user or {}, db)
    if ctx.scope_type == "TENANT_ALL":
        return {"type": "TENANT_ALL", "collegeIds": [], "teacherKeys": []}
    if ctx.scope_type == "COLLEGE":
        college_ids = sorted({int(value) for value in (ctx.college_ids or set())})
        if not college_ids:
            raise no_data_scope("当前学院身份未配置可管理学院范围")
        return {"type": "COLLEGE", "collegeIds": college_ids, "teacherKeys": []}
    teacher_keys = sorted({str(value) for value in _derive_keys(user or {}) if str(value).strip()})
    if teacher_keys:
        return {"type": "OWNER", "collegeIds": [], "teacherKeys": teacher_keys}
    raise no_data_scope("当前身份无评教管理数据范围")


def _visible_batch_ids(spec: dict):
    from app.models import AaEvaluationTask, AaTeachingTask, AaTeachingTaskBatch

    query = select(AaEvaluationTask.batch_id).where(
        AaEvaluationTask.tenant_id == _legacy._tid(),
        AaEvaluationTask.is_deleted.is_(False),
    )
    if spec["type"] == "TENANT_ALL":
        return query.distinct()
    if spec["type"] == "COLLEGE":
        return query.join(
            AaTeachingTask,
            and_(
                AaTeachingTask.id == AaEvaluationTask.teaching_task_id,
                AaTeachingTask.tenant_id == AaEvaluationTask.tenant_id,
                AaTeachingTask.is_deleted.is_(False),
            ),
        ).join(
            AaTeachingTaskBatch,
            and_(
                AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
                AaTeachingTaskBatch.tenant_id == AaTeachingTask.tenant_id,
                AaTeachingTaskBatch.is_deleted.is_(False),
            ),
        ).where(AaTeachingTaskBatch.college_id.in_(spec["collegeIds"])).distinct()
    return query.where(AaEvaluationTask.teacher_key.in_(spec["teacherKeys"])).distinct()


def _apply_task_scope(query, spec: dict):
    from app.models import AaEvaluationTask, AaTeachingTask, AaTeachingTaskBatch

    if spec["type"] == "TENANT_ALL":
        return query
    if spec["type"] == "COLLEGE":
        return query.join(
            AaTeachingTask,
            and_(
                AaTeachingTask.id == AaEvaluationTask.teaching_task_id,
                AaTeachingTask.tenant_id == AaEvaluationTask.tenant_id,
                AaTeachingTask.is_deleted.is_(False),
            ),
        ).join(
            AaTeachingTaskBatch,
            and_(
                AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
                AaTeachingTaskBatch.tenant_id == AaTeachingTask.tenant_id,
                AaTeachingTaskBatch.is_deleted.is_(False),
            ),
        ).filter(AaTeachingTaskBatch.college_id.in_(spec["collegeIds"]))
    return query.filter(AaEvaluationTask.teacher_key.in_(spec["teacherKeys"]))


def _apply_result_scope(query, spec: dict):
    from app.models import AaEvaluationResult, AaTeachingTask, AaTeachingTaskBatch

    if spec["type"] == "TENANT_ALL":
        return query
    if spec["type"] == "COLLEGE":
        return query.join(
            AaTeachingTask,
            and_(
                AaTeachingTask.id == AaEvaluationResult.teaching_task_id,
                AaTeachingTask.tenant_id == AaEvaluationResult.tenant_id,
                AaTeachingTask.is_deleted.is_(False),
            ),
        ).join(
            AaTeachingTaskBatch,
            and_(
                AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
                AaTeachingTaskBatch.tenant_id == AaTeachingTask.tenant_id,
                AaTeachingTaskBatch.is_deleted.is_(False),
            ),
        ).filter(AaTeachingTaskBatch.college_id.in_(spec["collegeIds"]))
    return query.filter(AaEvaluationResult.teacher_key.in_(spec["teacherKeys"]))


def _get_scoped_batch_model(db, user, batch_id: int, *, spec: dict | None = None):
    from app.models import AaEvaluationBatch

    spec = spec or _scope_spec(user, db)
    query = db.query(AaEvaluationBatch).filter(
        AaEvaluationBatch.id == int(batch_id),
        AaEvaluationBatch.tenant_id == _legacy._tid(),
        AaEvaluationBatch.is_deleted.is_(False),
    )
    if spec["type"] != "TENANT_ALL":
        query = query.filter(AaEvaluationBatch.id.in_(_visible_batch_ids(spec)))
    batch = query.first()
    if batch:
        return batch
    if spec["type"] == "TENANT_ALL":
        raise not_found("评教批次不存在")
    raise no_data_scope("该评教批次不在当前数据范围内")


def _record_counts_for_tasks(db, task_ids) -> dict[int, int]:
    """Return active answer-fact counts in one GROUP BY query."""
    from app.models import AaEvaluationRecord

    ids = sorted({int(value) for value in (task_ids or []) if value is not None})
    if not ids:
        return {}
    rows = db.query(
        AaEvaluationRecord.task_id,
        func.count(AaEvaluationRecord.id),
    ).filter(
        AaEvaluationRecord.tenant_id == _legacy._tid(),
        AaEvaluationRecord.task_id.in_(ids),
        AaEvaluationRecord.is_deleted.is_(False),
    ).group_by(AaEvaluationRecord.task_id).all()
    return {int(task_id): int(count or 0) for task_id, count in rows}


def list_batches(user, status=None, page=1, page_size=20):
    """True DB pagination plus object visibility for college/teaching-owner scopes."""
    from app.models import AaEvaluationBatch

    page, page_size = _page(page, page_size, default_size=20)
    with _legacy.session() as db:
        spec = _scope_spec(user, db)
        query = db.query(AaEvaluationBatch).filter(
            AaEvaluationBatch.tenant_id == _legacy._tid(),
            AaEvaluationBatch.is_deleted.is_(False),
        )
        if spec["type"] != "TENANT_ALL":
            query = query.filter(AaEvaluationBatch.id.in_(_visible_batch_ids(spec)))
        if status:
            query = query.filter(AaEvaluationBatch.status == status)
        total = query.count()
        rows = query.order_by(AaEvaluationBatch.id.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return [_legacy._batch_dto(batch) for batch in rows], int(total)


def get_batch(user, bid):
    with _legacy.session() as db:
        spec = _scope_spec(user, db)
        return _legacy._batch_dto(_get_scoped_batch_model(db, user, int(bid), spec=spec))


def list_tasks(user, bid, evaluator_type=None):
    """Management task counts come from answer facts, never an OPEN-window hot counter row."""
    from app.models import AaEvaluationTask

    with _legacy.session() as db:
        spec = _scope_spec(user, db)
        _get_scoped_batch_model(db, user, int(bid), spec=spec)
        query = db.query(AaEvaluationTask).filter(
            AaEvaluationTask.batch_id == int(bid),
            AaEvaluationTask.tenant_id == _legacy._tid(),
            AaEvaluationTask.is_deleted.is_(False),
        )
        query = _apply_task_scope(query, spec)
        if evaluator_type:
            query = query.filter(AaEvaluationTask.evaluator_type == evaluator_type)
        rows = query.order_by(AaEvaluationTask.id).all()
        counts = _record_counts_for_tasks(db, [task.id for task in rows])
        return [{
            "taskId": str(task.id),
            "courseName": task.course_name,
            "teacherName": task.teacher_name,
            "evaluatorType": task.evaluator_type,
            "submittedCount": counts.get(int(task.id), 0),
            "status": task.status,
        } for task in rows]


def _result_query(db, bid: int, spec: dict):
    from app.models import AaEvaluationResult

    query = db.query(AaEvaluationResult).filter(
        AaEvaluationResult.batch_id == int(bid),
        AaEvaluationResult.tenant_id == _legacy._tid(),
        AaEvaluationResult.is_deleted.is_(False),
    )
    query = _apply_result_scope(query, spec)
    if spec["type"] == "OWNER":
        query = query.filter(AaEvaluationResult.published.is_(True))
    return query


def _result_dto(row) -> dict:
    def _float(value):
        return float(value) if value is not None else None

    return {
        "resultId": str(row.id),
        "teacherName": row.teacher_name,
        "courseName": row.course_name,
        "studentAvg": _float(row.student_avg),
        "studentCount": row.student_count,
        "selfScore": _float(row.self_score),
        "peerAvg": _float(row.peer_avg),
        "peerCount": row.peer_count,
        "supervisorAvg": _float(row.supervisor_avg),
        "supervisorCount": row.supervisor_count,
        "compositeScore": _float(row.composite_score),
        "level": row.level,
        "published": row.published,
    }


def list_results(user, bid, mine=False, page=1, page_size=50):
    """Results are object-scoped; OWNER visibility is publication-gated."""
    from app.models import AaEvaluationResult

    page, page_size = _page(page, page_size, default_size=50)
    with _legacy.session() as db:
        spec = _scope_spec(user, db)
        _get_scoped_batch_model(db, user, int(bid), spec=spec)
        query = _result_query(db, int(bid), spec)
        if mine:
            keys = list(_derive_keys(user or {})) or [""]
            query = query.filter(
                AaEvaluationResult.teacher_key.in_(keys),
                AaEvaluationResult.published.is_(True),
            )
        total = query.count()
        rows = query.order_by(AaEvaluationResult.id).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return [_result_dto(row) for row in rows], int(total)


def _stats_in_session(db, user, bid: int, spec: dict) -> dict:
    from app.models import AaEvaluationRecord, AaEvaluationResult, AaEvaluationTask

    _get_scoped_batch_model(db, user, int(bid), spec=spec)
    result_query = _result_query(db, int(bid), spec)
    level_rows = result_query.with_entities(
        AaEvaluationResult.level,
        func.count(AaEvaluationResult.id).label("result_count"),
        func.sum(AaEvaluationResult.student_avg).label("score_sum"),
        func.count(AaEvaluationResult.student_avg).label("scored_count"),
    ).group_by(AaEvaluationResult.level).all()
    result_count = sum(int(count or 0) for _level, count, _score_sum, _scored_count in level_rows)
    score_sum = sum(float(value or 0) for _level, _count, value, _scored_count in level_rows)
    scored_count = sum(int(count or 0) for _level, _count, _score_sum, count in level_rows)
    overall_avg = score_sum / scored_count if scored_count else None
    by_level = {(level or "N/A"): int(count or 0) for level, count, _score_sum, _scored_count in level_rows}

    record_counts = select(
        AaEvaluationRecord.task_id.label("task_id"),
        func.count(AaEvaluationRecord.id).label("record_count"),
    ).where(
        AaEvaluationRecord.tenant_id == _legacy._tid(),
        AaEvaluationRecord.batch_id == int(bid),
        AaEvaluationRecord.is_deleted.is_(False),
    ).group_by(AaEvaluationRecord.task_id).subquery()

    submitted_condition = func.coalesce(record_counts.c.record_count, 0) > 0
    task_query = db.query(
        AaEvaluationTask.evaluator_type,
        func.count(AaEvaluationTask.id).label("total"),
        func.sum(case((submitted_condition, 1), else_=0)).label("submitted"),
    ).outerjoin(
        record_counts,
        record_counts.c.task_id == AaEvaluationTask.id,
    ).filter(
        AaEvaluationTask.batch_id == int(bid),
        AaEvaluationTask.tenant_id == _legacy._tid(),
        AaEvaluationTask.is_deleted.is_(False),
    )
    task_query = _apply_task_scope(task_query, spec)
    participation_rows = task_query.group_by(AaEvaluationTask.evaluator_type).all()
    participation = {}
    for evaluator_type, total, submitted in participation_rows:
        total = int(total or 0)
        submitted = int(submitted or 0)
        participation[evaluator_type] = {
            "total": total,
            "submitted": submitted,
            "rate": round(submitted / total * 100, 1) if total else 0.0,
        }
    return {
        "batchId": str(bid),
        "resultCount": int(result_count or 0),
        "overallAvg": round(float(overall_avg), 2) if overall_avg is not None else None,
        "byLevel": by_level,
        "participation": participation,
    }


def stats(user, bid):
    with _legacy.session() as db:
        spec = _scope_spec(user, db)
        return _stats_in_session(db, user, int(bid), spec)


def export_evaluation_xlsx(user, bid, domain, purpose):
    """Export exactly the same scoped projection; never bypass list scope with pageSize=10000."""
    from app.models import AaEvaluationResult
    from app.services.xlsx_util import build_ledger_xlsx

    purpose = (purpose or "").strip()
    if len(purpose) < 5:
        raise _legacy._bad("导出用途必填（≥5字）")

    with _legacy.session() as db:
        spec = _scope_spec(user, db)
        batch = _get_scoped_batch_model(db, user, int(bid), spec=spec)
        current = get_current_user_ctx() or {}
        watermark = (
            f"导出人：{current.get('realName') or current.get('loginName') or '-'}  "
            f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}"
        )
        if domain == "stats":
            summary = _stats_in_session(db, user, int(bid), spec)
            headers = ["评价类型", "应评数", "已评数", "参评率(%)"]
            rows = [
                [key, value["total"], value["submitted"], value["rate"]]
                for key, value in (summary.get("participation") or {}).items()
            ]
            content = build_ledger_xlsx(f"{batch.batch_name}-参评统计", headers, rows, watermark=watermark)
        elif domain == "results":
            headers = ["教师", "课程", "均分", "评价数", "等级", "已发布"]
            rows = []
            for result in _result_query(db, int(bid), spec).order_by(AaEvaluationResult.id).yield_per(500):
                item = _result_dto(result)
                rows.append([
                    item["teacherName"], item["courseName"], item["studentAvg"],
                    item["studentCount"], item["level"], "是" if item["published"] else "否",
                ])
            content = build_ledger_xlsx(f"{batch.batch_name}-评价结果", headers, rows, watermark=watermark)
        else:
            raise _legacy._bad("非法导出域，仅支持 results/stats")

        _legacy._audit(db, int(bid), "EVAL_EXPORT", f"{domain} 用途={purpose[:100]}")
        db.commit()
        return content


def _score_rows(db, batch_id: int):
    """Return score aggregates for exactly one evaluation batch."""
    from app.models import AaEvaluationRecord, AaEvaluationTask

    return db.execute(
        select(
            AaEvaluationTask.teaching_task_id,
            AaEvaluationTask.evaluator_type,
            func.avg(AaEvaluationRecord.objective_score).label("average_score"),
            func.count(AaEvaluationRecord.objective_score).label("score_count"),
        )
        .select_from(AaEvaluationTask)
        .outerjoin(
            AaEvaluationRecord,
            and_(
                AaEvaluationRecord.task_id == AaEvaluationTask.id,
                AaEvaluationRecord.tenant_id == AaEvaluationTask.tenant_id,
                AaEvaluationRecord.batch_id == AaEvaluationTask.batch_id,
                AaEvaluationRecord.is_deleted.is_(False),
            ),
        )
        .where(
            AaEvaluationTask.batch_id == int(batch_id),
            AaEvaluationTask.tenant_id == _legacy._tid(),
            AaEvaluationTask.is_deleted.is_(False),
        )
        .group_by(AaEvaluationTask.teaching_task_id, AaEvaluationTask.evaluator_type)
    ).all()


def close_and_score(user, bid):
    """Close OPEN batch after submissions finish, then reconcile task-count projections."""
    from app.models import AaEvaluationResult, AaEvaluationTask

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _base._writable_batch(db, bid, lock="update")
        if batch.status != _legacy._B_OPEN:
            raise _legacy._invalid("仅 OPEN 批次可关闭核算")

        tasks = db.query(AaEvaluationTask).filter(
            AaEvaluationTask.batch_id == batch.id,
            AaEvaluationTask.tenant_id == _legacy._tid(),
            AaEvaluationTask.is_deleted.is_(False),
        ).all()
        record_counts = _record_counts_for_tasks(db, [task.id for task in tasks])
        aggregate: dict[int, dict[str, tuple[float | None, int]]] = {}
        metadata: dict[int, tuple[str | None, str | None, str | None]] = {}
        for task in tasks:
            # submitted_count remains a backward-compatible closed-batch projection only.
            task.submitted_count = record_counts.get(int(task.id), 0)
            if task.teaching_task_id is None:
                raise _legacy._invalid("评教任务未绑定正式教学任务，禁止核算")
            teaching_task_id = int(task.teaching_task_id)
            aggregate.setdefault(teaching_task_id, {}).setdefault(task.evaluator_type, (None, 0))
            metadata[teaching_task_id] = (task.teacher_key, task.teacher_name, task.course_name)

        for teaching_task_id, evaluator_type, average_score, score_count in _score_rows(db, batch.id):
            if teaching_task_id is None:
                continue
            teaching_task_id = int(teaching_task_id)
            aggregate.setdefault(teaching_task_id, {})[evaluator_type] = (
                round(float(average_score), 2) if average_score is not None else None,
                int(score_count or 0),
            )

        teaching_task_ids = list(aggregate)
        existing_results = {}
        if teaching_task_ids:
            rows = db.query(AaEvaluationResult).filter(
                AaEvaluationResult.tenant_id == _legacy._tid(),
                AaEvaluationResult.batch_id == batch.id,
                AaEvaluationResult.teaching_task_id.in_(teaching_task_ids),
            ).all()
            deleted_keys = [int(row.teaching_task_id) for row in rows if row.is_deleted]
            if deleted_keys:
                raise _legacy._invalid("评价结果唯一键被历史软删除记录占用，禁止静默复活；请先完成数据治理")
            existing_results = {int(result.teaching_task_id): result for result in rows}

        for teaching_task_id, by_type in aggregate.items():
            student_average, student_count = by_type.get("STUDENT", (None, 0))
            self_average, _self_count = by_type.get("SELF", (None, 0))
            peer_average, peer_count = by_type.get("PEER", (None, 0))
            supervisor_average, supervisor_count = by_type.get("SUPERVISOR", (None, 0))
            composite = _legacy._composite(student_average, self_average, peer_average, supervisor_average)
            teacher_key, teacher_name, course_name = metadata[teaching_task_id]
            result = existing_results.get(teaching_task_id)
            if not result:
                result = AaEvaluationResult(
                    tenant_id=_legacy._tid(), batch_id=batch.id, teaching_task_id=teaching_task_id,
                    teacher_key=teacher_key, teacher_name=teacher_name, course_name=course_name, published=False,
                )
                db.add(result)
                existing_results[teaching_task_id] = result
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
        _legacy._audit(db, batch.id, "EVAL_BATCH_SCORE", f"多来源核算 {len(aggregate)} 门结果")
        db.commit()
        return _legacy._batch_dto(batch)
