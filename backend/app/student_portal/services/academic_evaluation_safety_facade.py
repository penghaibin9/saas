"""学生 PC 教务最终安全门面。

在成绩查询件安全门面的基础上，将评教任务读取和匿名提交统一切换到正式教学班名单、
稳定学生身份和单人单次提交实现；其余学生教务能力继续显式委托既有门面。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_evaluation_service as evaluation

from . import academic_transcript_safety_facade as _base


def __getattr__(name):
    return getattr(_base, name)


def evaluation_tasks(user: dict) -> dict:
    items = evaluation.my_student_tasks(user, include_closed=True)
    pending = sum(1 for item in items if item.get("canSubmit"))
    return {
        "list": items,
        "total": len(items),
        "pending": pending,
        "note": "仅展示当前账号在正式教学班名单内的评教任务；答卷匿名保存。",
    }


def evaluation_submit(user: dict, body: dict) -> dict:
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
