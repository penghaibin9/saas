"""学生/教师移动教务最终公开入口。

移动端其余教务能力继续委托统一 facade；学生评教改为正式教学班名单工作清单和稳定身份
匿名提交，不再按行政班猜测评教范围。

Stage C3：学生 PC / 学生小程序的毕业进度必须和正式毕业预审调用同一个只读 evaluator。
学生刷新只做实时自查，不创建 ``GraduationEvaluationRun``；最新正式预审结果只作为
formal status/conclusion 元数据展示，不能再反过来充当学生当前毕业判定的事实源。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import mobile_academic_affairs_facade as _base


def __getattr__(name):
    return getattr(_base, name)


def graduation_progress_my(user) -> dict:
    """本人毕业进度：共享 evaluator 的实时只读结果 + 最近正式审核元数据。

    该函数绝不写 ``GraduationEvaluationRun``。因此学生频繁刷新不会制造正式审核历史，
    同时也不会继续读取可变 ``AaGraduationAuditResult.item_results_json`` 作为当前事实。
    """
    from app.models import AaGraduationAuditResult
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as graduation

    with session() as db:
        student = _base._me(db, user)
        evaluated = graduation.evaluate_student(db, student)
        formal = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(),
            AaGraduationAuditResult.student_id == student.id,
            AaGraduationAuditResult.is_deleted.is_(False),
        ).order_by(AaGraduationAuditResult.id.desc())).first()

        return {
            "hasAudit": bool(formal),
            "overall": evaluated["overall"],
            "items": evaluated["items"],
            "inputHash": evaluated["inputHash"],
            "formalRunCreated": False,
            "conclusion": formal.conclusion if formal else None,
            "status": formal.status if formal else None,
            "formalOverall": formal.overall if formal else None,
            "note": None if formal else "尚未纳入正式毕业预审；当前结果仅为实时自查",
        }


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
