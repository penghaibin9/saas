"""学生 PC 教务最终安全门面。

在成绩查询件安全门面的基础上，将评教任务读取和匿名提交统一切换到正式教学班名单、
稳定学生身份和单人单次提交实现；其余学生教务能力继续显式委托既有门面。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_evaluation_service as evaluation
from app.services.mobile_student_service import _require_student

from . import academic_transcript_safety_facade as _base


def __getattr__(name):
    return getattr(_base, name)


def evaluation_tasks(user: dict) -> dict:
    _require_student(user)
    all_items = evaluation.my_student_tasks(user, include_closed=True)
    # 旧学生 PC 评教卡只区分“可提交/已提交”，因此关闭但未提交的任务不伪装成可操作按钮。
    items = [item for item in all_items if item.get("canSubmit") or item.get("submitted")]
    pending = sum(1 for item in items if item.get("canSubmit"))
    return {
        "list": items,
        "total": len(items),
        "pending": pending,
        "note": "仅展示本人正式教学班内可提交或已完成的评教任务；答卷匿名保存。",
    }


def evaluation_submit(user: dict, body: dict) -> dict:
    # 权限必须先于参数与业务数据校验，防止非学生通过错误差异探测评教任务是否存在。
    _require_student(user)
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
