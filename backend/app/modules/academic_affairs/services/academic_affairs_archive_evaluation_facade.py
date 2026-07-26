"""教务归档第12域：学生评教。

学期归档前评教批次必须 CLOSED；有提交数据的任务必须生成结果；评教申诉必须 RESOLVED/REJECTED。
未启用评教时不阻断。
"""
from __future__ import annotations

from app.services.db_service import _tid

from . import academic_affairs_archive_makeup_facade as _base

_legacy = _base._legacy
_archive_executor = _base._archive_executor
_previous_evaluate_domains = _archive_executor._evaluate_domains


def __getattr__(name):
    return getattr(_base, name)


def _evaluation_gate_result(
    batches,
    *,
    missing_results: int = 0,
    active_appeals: int = 0,
):
    batches = list(batches or [])
    if not batches:
        return _legacy._result(0, True, "本学期未启用学生评教，不作为归档阻断")
    unfinished = [
        row for row in batches
        if str(getattr(row, "status", None) or "").upper() != "CLOSED"
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未关闭评教批次 {len(unfinished)} 个")
    if missing_results:
        blockers.append(f"有提交但未生成结果的评教任务 {int(missing_results)} 个")
    if active_appeals:
        blockers.append(f"仍有在途评教申诉 {int(active_appeals)} 条")
    passed = not blockers
    return _legacy._result(
        len(batches),
        passed,
        "评教窗口、结果和申诉均已收口" if passed else "；".join(blockers),
    )


def _evaluate_evaluation(db, term_id):
    from app.models import (
        AaEvaluationAppeal,
        AaEvaluationBatch,
        AaEvaluationResult,
        AaEvaluationTask,
    )

    if not term_id:
        return _legacy._result(0, False, "未指定学期，无法核验学生评教")
    batches = db.query(AaEvaluationBatch).filter(
        AaEvaluationBatch.tenant_id == _tid(),
        AaEvaluationBatch.term_id == int(term_id),
        AaEvaluationBatch.is_deleted.is_(False),
    ).all()
    batch_ids = [int(row.id) for row in batches]
    if not batch_ids:
        return _evaluation_gate_result([])
    tasks = db.query(AaEvaluationTask).filter(
        AaEvaluationTask.tenant_id == _tid(),
        AaEvaluationTask.batch_id.in_(batch_ids),
        AaEvaluationTask.is_deleted.is_(False),
    ).all()
    task_ids = [int(row.id) for row in tasks]
    result_task_ids = set()
    active_appeals = 0
    if task_ids:
        results = db.query(AaEvaluationResult).filter(
            AaEvaluationResult.tenant_id == _tid(),
            AaEvaluationResult.task_id.in_(task_ids),
            AaEvaluationResult.is_deleted.is_(False),
        ).all()
        result_task_ids = {int(row.task_id) for row in results}
        result_ids = [int(row.id) for row in results]
        if result_ids:
            active_appeals = db.query(AaEvaluationAppeal).filter(
                AaEvaluationAppeal.tenant_id == _tid(),
                AaEvaluationAppeal.result_id.in_(result_ids),
                AaEvaluationAppeal.status.in_(["SUBMITTED", "REVIEWING"]),
                AaEvaluationAppeal.is_deleted.is_(False),
            ).count()
    missing_results = sum(
        1 for task in tasks
        if int(task.submitted_count or 0) > 0 and int(task.id) not in result_task_ids
    )
    return _evaluation_gate_result(
        batches,
        missing_results=missing_results,
        active_appeals=int(active_appeals or 0),
    )


def _evaluate_domains(db, term_id, term_code, college_ids=None):
    results = _previous_evaluate_domains(db, term_id, term_code, college_ids)
    try:
        results["EVALUATION"] = _evaluate_evaluation(db, term_id)
    except Exception as exc:
        results["EVALUATION"] = _legacy._result(0, False, f"该域语义检查失败：{type(exc).__name__}")
    return results


if not any(code == "EVALUATION" for code, _label in _legacy._DOMAINS):
    _legacy._DOMAINS.append(("EVALUATION", "学生评教"))

_archive_executor._evaluate_domains = _evaluate_domains
