"""D9-U 学生评教任务批量读侧。

保持 student_evaluation_router 的正式 owner、稳定学生身份、正式教学班 roster 与匿名 HMAC
去重语义不变；只把“每个任务再查一次 AaEvaluationRecord”的 N+1 收口为一次批量 SQL。
"""
from __future__ import annotations

from sqlalchemy import and_, or_, select

from . import academic_affairs_evaluation_public_service as _service


def my_student_tasks(user, batch_id=None, include_closed=True) -> list[dict]:
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
        if not include_closed:
            query = query.filter(AaEvaluationBatch.status == legacy._B_OPEN)
        rows = query.distinct().order_by(
            AaEvaluationBatch.id.desc(),
            AaEvaluationTask.id.desc(),
        ).all()

        task_ids = [int(task.id) for task, _batch in rows]
        submitted_ids: set[int] = set()
        if task_ids:
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

        return [{
            "taskId": str(task.id),
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "teachingTaskId": str(task.teaching_task_id),
            "courseName": task.course_name,
            "teacherName": task.teacher_name,
            "windowStatus": batch.status,
            "anonymous": True,
            "submitted": int(task.id) in submitted_ids,
            "canSubmit": batch.status == legacy._B_OPEN and int(task.id) not in submitted_ids,
        } for task, batch in rows]
