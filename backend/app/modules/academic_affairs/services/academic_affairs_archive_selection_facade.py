"""教务归档的选课名单补充门禁。

现有归档原为9域，遗漏选课批次，导致学期封存后仍可能存在OPEN/CLOSED选课。当前模型支持动态domain，
本兼容层追加第10域 ``SELECTION``，不改归档批次事实和导出机制。
"""
from __future__ import annotations

from app.services.db_service import _tid

from . import academic_affairs_archive_policy_facade as _base

_legacy = _base._legacy
_archive_executor = _base._base
_previous_evaluate_domains = _archive_executor._evaluate_domains


def __getattr__(name):
    return getattr(_base, name)


def _selection_gate_result(
    batches,
    *,
    pending_records: int = 0,
    active_rounds: int = 0,
    count_mismatches: int = 0,
    missing_task_courses: int = 0,
):
    batches = list(batches or [])
    if not batches:
        return _legacy._result(0, True, "本学期未启用选课批次，不作为归档阻断")
    unfinished = [
        batch for batch in batches
        if str(getattr(batch, "status", None) or "").upper() not in {"LOCKED", "ARCHIVED"}
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未锁定/未归档选课批次 {len(unfinished)} 个")
    if active_rounds:
        blockers.append(f"仍有未终结选课轮次 {int(active_rounds)} 个")
    if pending_records:
        blockers.append(f"仍有未转正式名单记录 {int(pending_records)} 条")
    if count_mismatches:
        blockers.append(f"课程人数计数与LOCKED名单不一致 {int(count_mismatches)} 门")
    if missing_task_courses:
        blockers.append(f"未关联教学任务的有效课程 {int(missing_task_courses)} 门")
    passed = not blockers
    return _legacy._result(
        len(batches),
        passed,
        "选课批次和正式教学名单均已锁定" if passed else "；".join(blockers),
    )


def _evaluate_selection(db, term_id):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord, AaSelectionRound

    query = db.query(AaSelectionBatch).filter(
        AaSelectionBatch.tenant_id == _tid(),
        AaSelectionBatch.is_deleted.is_(False),
    )
    if term_id:
        query = query.filter(AaSelectionBatch.term_id == int(term_id))
    batches = query.all()
    batch_ids = [int(batch.id) for batch in batches]
    if not batch_ids:
        return _selection_gate_result([])

    active_rounds = db.query(AaSelectionRound).filter(
        AaSelectionRound.tenant_id == _tid(),
        AaSelectionRound.batch_id.in_(batch_ids),
        AaSelectionRound.status.in_(["DRAFT", "OPEN", "CLOSED"]),
        AaSelectionRound.is_deleted.is_(False),
    ).count()
    pending_records = db.query(AaSelectionRecord).filter(
        AaSelectionRecord.tenant_id == _tid(),
        AaSelectionRecord.batch_id.in_(batch_ids),
        AaSelectionRecord.status.in_(["SELECTED", "PENDING_LOTTERY"]),
        AaSelectionRecord.is_deleted.is_(False),
    ).count()
    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.batch_id.in_(batch_ids),
        AaSelectionCourse.status == "OPEN",
        AaSelectionCourse.is_deleted.is_(False),
    ).all()
    missing_task_courses = sum(1 for course in courses if not course.teaching_task_id)
    count_mismatches = 0
    batch_by_id = {int(batch.id): batch for batch in batches}
    for course in courses:
        batch = batch_by_id.get(int(course.batch_id))
        if not batch or str(batch.status or "").upper() not in {"LOCKED", "ARCHIVED"}:
            continue
        locked_count = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.status == "LOCKED",
            AaSelectionRecord.is_deleted.is_(False),
        ).count()
        if int(course.selected_count or 0) != int(locked_count or 0):
            count_mismatches += 1
    return _selection_gate_result(
        batches,
        pending_records=int(pending_records or 0),
        active_rounds=int(active_rounds or 0),
        count_mismatches=count_mismatches,
        missing_task_courses=missing_task_courses,
    )


def _evaluate_domains(db, term_id, term_code, college_ids=None):
    results = _previous_evaluate_domains(db, term_id, term_code, college_ids)
    try:
        results["SELECTION"] = _evaluate_selection(db, term_id)
    except Exception as exc:
        results["SELECTION"] = _legacy._result(0, False, f"该域语义检查失败：{type(exc).__name__}")
    return results


if not any(code == "SELECTION" for code, _label in _legacy._DOMAINS):
    _legacy._DOMAINS.append(("SELECTION", "选课名单"))

# 真正执行run_check/precheck的是archive_facade函数，其globals属于_archive_executor；必须改这里。
_archive_executor._evaluate_domains = _evaluate_domains
