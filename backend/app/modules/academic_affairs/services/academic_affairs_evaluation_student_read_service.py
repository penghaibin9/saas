"""D9-U 学生评教任务批量读侧。

保持 student_evaluation_router 的正式 owner、稳定学生身份、正式教学班 roster 与匿名 HMAC
去重语义不变；读侧用固定 SQL 批量返回“本人是否已交 + 班级已交数”，不把聚合成本放进提交事务。
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException

from . import academic_affairs_evaluation_public_service as _service


def _page_arguments(page, page_size) -> tuple[int, int]:
    if isinstance(page, bool) or isinstance(page_size, bool):
        raise AppException("VALIDATION_ERROR", "评教任务页码格式不正确")
    try:
        page_number = int(page)
        size = int(page_size)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "评教任务页码格式不正确") from exc
    if page_number < 1 or page_number > 100000 or size < 1 or size > 50:
        raise AppException("VALIDATION_ERROR", "评教任务每页最多50条")
    return page_number, size


def my_student_tasks(
    user,
    batch_id=None,
    include_closed=True,
    *,
    page=None,
    page_size=20,
    task_id=None,
    pending_summary=False,
):
    """读取本人评教任务。

    保留未传 ``page`` 的旧调用返回列表；移动端传页码时由数据库完成
    COUNT/OFFSET/LIMIT，避免把全校学期内的可评课程塞入小程序后再切片。
    """
    from app.models import (
        AaEvaluationBatch,
        AaEvaluationRecord,
        AaEvaluationTask,
        AaTeachingClass,
        AaTeachingClassMember,
    )

    legacy = _service._legacy
    visible_statuses = [
        legacy._B_PUBLISHED,
        legacy._B_OPEN,
        legacy._B_RESULT,
        legacy._B_ARCHIVED,
    ]
    with _service.session() as db:
        profile = _service._resolve_student(db, user)
        query = db.query(AaEvaluationTask, AaEvaluationBatch).join(
            AaEvaluationBatch,
            AaEvaluationBatch.id == AaEvaluationTask.batch_id,
        ).join(
            AaTeachingClass,
            AaTeachingClass.teaching_task_id == AaEvaluationTask.teaching_task_id,
        ).join(
            AaTeachingClassMember,
            (AaTeachingClassMember.teaching_class_id == AaTeachingClass.id)
            & (AaTeachingClassMember.roster_version_id == AaTeachingClass.current_roster_version_id),
        ).filter(
            AaEvaluationTask.tenant_id == _service._tid(),
            AaEvaluationTask.evaluator_type == "STUDENT",
            AaEvaluationTask.is_deleted.is_(False),
            AaEvaluationBatch.tenant_id == _service._tid(),
            AaEvaluationBatch.status.in_(visible_statuses),
            AaEvaluationBatch.anonymous.is_(True),
            AaEvaluationBatch.is_deleted.is_(False),
            AaTeachingClass.tenant_id == _service._tid(),
            AaTeachingClass.is_deleted.is_(False),
            AaTeachingClass.roster_status == "LOCKED",
            AaTeachingClassMember.tenant_id == _service._tid(),
            AaTeachingClassMember.student_id == int(profile.id),
            AaTeachingClassMember.status == "ACTIVE",
            AaTeachingClassMember.is_deleted.is_(False),
        )
        if batch_id:
            query = query.filter(AaEvaluationBatch.id == int(batch_id))
        if task_id:
            query = query.filter(AaEvaluationTask.id == int(task_id))
        if not include_closed:
            query = query.filter(AaEvaluationBatch.status == legacy._B_OPEN)

        pending = {"count": 0, "nextTaskId": None}
        if pending_summary:
            # 首页只读一页任务，但待办数字必须代表所有仍可办理的本人任务。
            # 匿名去重凭证由 taskId+稳定 studentId HMAC 派生，不能用一条固定
            # SQL 字段比较；这里用两次批量查询完成，不做逐任务 N+1，也不把候选
            # 交给手机本地统计。
            open_task_ids = [
                int(task_value)
                for task_value, _batch_value in query.filter(
                    AaEvaluationBatch.status == legacy._B_OPEN,
                ).with_entities(
                    AaEvaluationTask.id,
                    AaEvaluationBatch.id,
                ).distinct().order_by(
                    AaEvaluationBatch.id.desc(),
                    AaEvaluationTask.id.desc(),
                ).all()
            ]
            submitted_open_ids: set[int] = set()
            if open_task_ids:
                token_rows = db.execute(select(
                    AaEvaluationRecord.task_id,
                    AaEvaluationRecord.answers_json,
                ).where(
                    AaEvaluationRecord.tenant_id == _service._tid(),
                    AaEvaluationRecord.task_id.in_(open_task_ids),
                    AaEvaluationRecord.evaluator_type == "STUDENT",
                    AaEvaluationRecord.is_deleted.is_(False),
                )).all()
                for recorded_task_id, answers_json in token_rows:
                    task_value = int(recorded_task_id)
                    marker = _service._token_pattern(task_value, profile.id)[1:-1]
                    if marker in str(answers_json or ""):
                        submitted_open_ids.add(task_value)
            pending_task_ids = [task_value for task_value in open_task_ids if task_value not in submitted_open_ids]
            pending = {
                "count": len(pending_task_ids),
                "nextTaskId": str(pending_task_ids[0]) if pending_task_ids else None,
            }

        if page is None:
            rows = query.distinct().order_by(
                AaEvaluationBatch.id.desc(),
                AaEvaluationTask.id.desc(),
            ).all()
            total = len(rows)
        else:
            page, page_size = _page_arguments(page, page_size)
            total = int(query.with_entities(
                func.count(func.distinct(AaEvaluationTask.id))
            ).scalar() or 0)
            rows = query.distinct().order_by(
                AaEvaluationBatch.id.desc(),
                AaEvaluationTask.id.desc(),
            ).offset((page - 1) * page_size).limit(page_size).all()

        task_ids = [int(task.id) for task, _batch in rows]
        submitted_ids: set[int] = set()
        submitted_counts: dict[int, int] = {}
        if task_ids:
            count_rows = db.execute(
                select(
                    AaEvaluationRecord.task_id,
                    func.count(AaEvaluationRecord.id),
                ).where(
                    AaEvaluationRecord.tenant_id == _service._tid(),
                    AaEvaluationRecord.task_id.in_(task_ids),
                    AaEvaluationRecord.evaluator_type == "STUDENT",
                    AaEvaluationRecord.is_deleted.is_(False),
                ).group_by(AaEvaluationRecord.task_id)
            ).all()
            submitted_counts = {
                int(task_id): int(count or 0)
                for task_id, count in count_rows
            }

            token_predicates = [
                and_(
                    AaEvaluationRecord.task_id == task_id,
                    AaEvaluationRecord.answers_json.like(_service._token_pattern(task_id, profile.id)),
                )
                for task_id in task_ids
            ]
            submitted_ids = {
                int(value)
                for value in db.scalars(select(AaEvaluationRecord.task_id).where(
                    AaEvaluationRecord.tenant_id == _service._tid(),
                    AaEvaluationRecord.evaluator_type == "STUDENT",
                    AaEvaluationRecord.is_deleted.is_(False),
                    or_(*token_predicates),
                )).all()
            }

        output = [{
            "taskId": str(task.id),
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "teachingTaskId": str(task.teaching_task_id),
            "courseName": task.course_name,
            "teacherName": task.teacher_name,
            "windowStatus": batch.status,
            "anonymous": True,
            "submittedCount": submitted_counts.get(int(task.id), 0),
            "submitted": int(task.id) in submitted_ids,
            "canSubmit": batch.status == legacy._B_OPEN and int(task.id) not in submitted_ids,
        } for task, batch in rows]
        if pending_summary:
            return output, total, pending
        return (output, total) if page is not None else output
