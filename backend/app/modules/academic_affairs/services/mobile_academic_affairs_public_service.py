"""学生/教师移动教务最终公开入口。

移动端其余教务能力继续委托统一 facade；学生评教改为正式教学班名单工作清单和稳定身份
匿名提交，不再按行政班猜测评教范围。
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import mobile_academic_affairs_facade as _base


def __getattr__(name):
    return getattr(_base, name)


def evaluation_tasks_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as evaluation

    items = evaluation.my_student_tasks(user, include_closed=True)
    return {
        "list": items,
        "total": len(items),
        "pending": sum(1 for item in items if item.get("canSubmit")),
        "note": "仅展示本人正式教学班内的评教任务；提交后答卷保持匿名。",
    }


def evaluation_submit_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as evaluation

    data = body or {}
    task_id = data.get("taskId")
    if not task_id or not str(task_id).isdigit():
        raise AppException("VALIDATION_ERROR", "taskId 必填")
    score = data.get("objectiveScore")
    if score is None:
        raise AppException("VALIDATION_ERROR", "objectiveScore 必填")
    try:
        score_value = float(score)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "objectiveScore 须为数字") from exc
    if not 0 <= score_value <= 100:
        raise AppException("VALIDATION_ERROR", "objectiveScore 须在 0-100")
    return evaluation.submit_evaluation(
        user,
        int(task_id),
        data.get("answers") or {},
        score_value,
        data.get("comment"),
    )
