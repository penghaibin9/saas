"""教学评价服务兼容入口。

申诉列表按真实数据范围裁决；D-W3 管理读通过同一 scoped scale service 收敛。
写状态机继续委托既有 service，不复制评教业务真值。
"""
from __future__ import annotations

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.services.db_service import _tid, session

from . import academic_affairs_evaluation_service as _legacy


def __getattr__(name):
    return getattr(_legacy, name)


def get_batch(user, bid):
    from . import academic_affairs_evaluation_scale_service as _scale
    return _scale.get_batch(user, bid)


def list_tasks(user, bid, evaluator_type=None):
    from . import academic_affairs_evaluation_scale_service as _scale
    return _scale.list_tasks(user, bid, evaluator_type=evaluator_type)


def export_evaluation_xlsx(user, bid, domain, purpose):
    from . import academic_affairs_evaluation_scale_service as _scale
    return _scale.export_evaluation_xlsx(user, bid, domain, purpose)


def list_appeals(user, status=None, page=1, page_size=50):
    """申诉理由按真实业务范围返回。"""
    from app.models import AaEvaluationAppeal, AaEvaluationResult, AaTeachingTask, AaTeachingTaskBatch

    with session() as db:
        ctx = build_affairs_context(user, db)
        query = db.query(AaEvaluationAppeal).join(
            AaEvaluationResult, AaEvaluationResult.id == AaEvaluationAppeal.result_id,
        ).outerjoin(
            AaTeachingTask, AaTeachingTask.id == AaEvaluationResult.teaching_task_id,
        ).outerjoin(
            AaTeachingTaskBatch, AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
        ).filter(
            AaEvaluationAppeal.tenant_id == _tid(),
            AaEvaluationAppeal.is_deleted.is_(False),
            AaEvaluationResult.tenant_id == _tid(),
        )

        if ctx.scope_type == "TENANT_ALL":
            pass
        elif ctx.scope_type == "COLLEGE":
            college_ids = [int(x) for x in (ctx.college_ids or [])]
            if not college_ids:
                raise no_data_scope("当前学院身份未配置可管理学院范围")
            query = query.filter(
                AaTeachingTaskBatch.tenant_id == _tid(),
                AaTeachingTaskBatch.college_id.in_(college_ids),
            )
        elif ctx.scope_type == "COURSE":
            keys = list(_derive_keys(user))
            if not keys:
                raise no_data_scope("当前教师身份缺少稳定教师标识")
            query = query.filter(AaEvaluationResult.teacher_key.in_(keys))
        else:
            raise no_data_scope("当前身份无权查看评教申诉理由")

        if status:
            query = query.filter(AaEvaluationAppeal.status == status)

        total = query.count()
        rows = query.order_by(AaEvaluationAppeal.id.desc()).offset(
            (max(1, int(page)) - 1) * int(page_size)
        ).limit(int(page_size)).all()
        return [{
            "appealId": str(row.id),
            "resultId": str(row.result_id),
            "teacherKey": row.teacher_key,
            "reason": row.reason,
            "status": row.status,
        } for row in rows], total
