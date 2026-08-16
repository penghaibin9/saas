"""D-W3 teaching-evaluation scale projection and close/score implementation.

No new evaluation truth is introduced here. The public evaluation service keeps the same
state machine, DTOs, anonymity rules and composite formula; this module only replaces
high-cardinality Python materialization/N+1 execution with bounded SQL pagination,
aggregate queries and one result prefetch.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, case, func, or_, select

from app.core.affairs_security import _derive_keys

from . import academic_affairs_evaluation_term_facade as _base

_legacy = _base._legacy


def _page(page, page_size, *, default_size: int, max_size: int = 100) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = int(page_size or default_size)
    if page_size < 1 or page_size > max_size:
        raise _legacy._bad(f"pageSize 必须在 1-{max_size} 之间")
    return page, page_size


def list_batches(user, status=None, page=1, page_size=20):
    """Evaluation batches use true COUNT/OFFSET/LIMIT instead of all()+Python slicing."""
    from app.models import AaEvaluationBatch

    page, page_size = _page(page, page_size, default_size=20)
    with _legacy.session() as db:
        _legacy._ctx(user, db)
        query = db.query(AaEvaluationBatch).filter(
            AaEvaluationBatch.tenant_id == _legacy._tid(),
            AaEvaluationBatch.is_deleted.is_(False),
        )
        if status:
            query = query.filter(AaEvaluationBatch.status == status)
        total = query.count()
        rows = query.order_by(AaEvaluationBatch.id.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return [_legacy._batch_dto(batch) for batch in rows], int(total)


def list_results(user, bid, mine=False, page=1, page_size=50):
    """Evaluation results use true pagination while preserving teacher self-scope semantics."""
    from app.models import AaEvaluationResult

    page, page_size = _page(page, page_size, default_size=50)
    with _legacy.session() as db:
        _legacy._ctx(user, db)
        query = db.query(AaEvaluationResult).filter(
            AaEvaluationResult.batch_id == int(bid),
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.is_deleted.is_(False),
        )
        if mine:
            keys = _derive_keys(user)
            query = query.filter(
                AaEvaluationResult.teacher_key.in_(list(keys) or [""]),
                AaEvaluationResult.published.is_(True),
            )
        total = query.count()
        rows = query.order_by(AaEvaluationResult.id).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        def _float(value):
            return float(value) if value is not None else None

        return [{
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
        } for row in rows], int(total)


def stats(user, bid):
    """Evaluation summary is computed in SQL; soft-deleted projections never re-enter stats."""
    from app.models import AaEvaluationResult, AaEvaluationTask

    with _legacy.session() as db:
        _legacy._ctx(user, db)
        result_filter = (
            AaEvaluationResult.batch_id == int(bid),
            AaEvaluationResult.tenant_id == _legacy._tid(),
            AaEvaluationResult.is_deleted.is_(False),
        )
        result_count, overall_avg = db.execute(
            select(
                func.count(AaEvaluationResult.id),
                func.avg(AaEvaluationResult.student_avg),
            ).where(*result_filter)
        ).one()
        level_rows = db.execute(
            select(
                AaEvaluationResult.level,
                func.count(AaEvaluationResult.id),
            ).where(*result_filter).group_by(AaEvaluationResult.level)
        ).all()
        by_level = {
            (level or "N/A"): int(count or 0)
            for level, count in level_rows
        }

        submitted_condition = or_(
            AaEvaluationTask.status == "SUBMITTED",
            and_(
                AaEvaluationTask.evaluator_type == "STUDENT",
                AaEvaluationTask.submitted_count > 0,
            ),
        )
        participation_rows = db.execute(
            select(
                AaEvaluationTask.evaluator_type,
                func.count(AaEvaluationTask.id).label("total"),
                func.sum(case((submitted_condition, 1), else_=0)).label("submitted"),
            ).where(
                AaEvaluationTask.batch_id == int(bid),
                AaEvaluationTask.tenant_id == _legacy._tid(),
                AaEvaluationTask.is_deleted.is_(False),
            ).group_by(AaEvaluationTask.evaluator_type)
        ).all()
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


def _score_rows(db, batch_id: int):
    """Return (teaching_task_id, evaluator_type, average, count) in one SQL aggregation."""
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
    """Close an OPEN batch and calculate results without per-task/per-result queries."""
    from app.models import AaEvaluationResult, AaEvaluationTask

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _base._writable_batch(db, bid)
        if batch.status != _legacy._B_OPEN:
            raise _legacy._invalid("仅 OPEN 批次可关闭核算")

        tasks = db.query(AaEvaluationTask).filter(
            AaEvaluationTask.batch_id == batch.id,
            AaEvaluationTask.tenant_id == _legacy._tid(),
            AaEvaluationTask.is_deleted.is_(False),
        ).all()

        aggregate: dict[int, dict[str, tuple[float | None, int]]] = {}
        metadata: dict[int, tuple[str | None, str | None, str | None]] = {}
        for task in tasks:
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
                raise _legacy._invalid(
                    "评价结果唯一键被历史软删除记录占用，禁止静默复活；请先完成数据治理"
                )
            existing_results = {
                int(result.teaching_task_id): result
                for result in rows
            }

        for teaching_task_id, by_type in aggregate.items():
            student_average, student_count = by_type.get("STUDENT", (None, 0))
            self_average, _self_count = by_type.get("SELF", (None, 0))
            peer_average, peer_count = by_type.get("PEER", (None, 0))
            supervisor_average, supervisor_count = by_type.get("SUPERVISOR", (None, 0))
            composite = _legacy._composite(
                student_average,
                self_average,
                peer_average,
                supervisor_average,
            )
            teacher_key, teacher_name, course_name = metadata[teaching_task_id]
            result = existing_results.get(teaching_task_id)
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
        batch.result_published_at = datetime.utcnow()
        _legacy._audit(db, batch.id, "EVAL_BATCH_SCORE", f"多来源核算 {len(aggregate)} 门结果")
        db.commit()
        return _legacy._batch_dto(batch)
