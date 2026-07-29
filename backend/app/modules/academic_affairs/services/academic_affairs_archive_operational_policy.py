"""课表与考务归档纯规则。

本模块只查询当前事务中的真实业务事实并返回语义结果，不修改归档 Service、Router 或其它模块。
"""
from __future__ import annotations

from app.services.db_service import _tid

from . import academic_affairs_archive_core_service as _core


def _status(value) -> str:
    return str(value or "").strip().upper()


def schedule_gate_result(rows, voided_batch_ids=None, active_changes: int = 0):
    rows = list(rows or [])
    voided_ids = {int(value) for value in (voided_batch_ids or set())}
    if not rows:
        return _core._result(0, False, "本学期没有课表批次")

    published, formal_archived, voided = [], [], []
    drafts, pre_published, unknown = [], [], []
    for row in rows:
        status = _status(getattr(row, "status", None))
        row_id = int(getattr(row, "id", 0) or 0)
        if status == "PUBLISHED":
            published.append(row)
        elif status == "ARCHIVED":
            (voided if row_id in voided_ids else formal_archived).append(row)
        elif status == "VOIDED":
            voided.append(row)
        elif status == "DRAFT":
            drafts.append(row)
        elif status == "PRE_PUBLISHED":
            pre_published.append(row)
        else:
            unknown.append(row)

    formal = published + formal_archived
    blockers = []
    if pre_published:
        blockers.append(f"仍有预发布批次 {len(pre_published)} 个")
    if active_changes:
        blockers.append(f"仍有在途调停课 {int(active_changes)} 条")
    if unknown:
        blockers.append(f"存在未知状态批次 {len(unknown)} 个")
    if not formal:
        if voided and not drafts and not pre_published and not unknown:
            blockers.append(f"仅有已作废批次 {len(voided)} 个，必须先发布替代课表")
        elif drafts and not voided and not pre_published and not unknown:
            blockers.append(f"仅有草稿批次 {len(drafts)} 个，尚未形成正式课表")
        else:
            blockers.append("没有 PUBLISHED 或正式 ARCHIVED 课表")

    if blockers:
        remark = "；".join(blockers)
        if drafts and formal:
            remark += f"；另有历史草稿 {len(drafts)} 个，因已有正式版本不单独阻断"
        if voided and formal:
            remark += f"；另有作废批次 {len(voided)} 个，已有替代正式版本"
    else:
        remark = (
            f"正式发布 {len(published)} 个、正式归档 {len(formal_archived)} 个；"
            f"历史草稿 {len(drafts)} 个、作废批次 {len(voided)} 个不覆盖正式版本"
        )
    return _core._result(len(rows), not blockers, remark)


def evaluate_schedule(db, term_id, college_ids=None):
    from app.models import AaScheduleBatch, AaScheduleChange, AaSchedulePublish

    query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.is_deleted.is_(False),
    )
    if term_id:
        query = query.filter(AaScheduleBatch.term_id == int(term_id))
    if college_ids:
        query = query.filter(AaScheduleBatch.college_id.in_(list(college_ids)))
    rows = query.all()
    batch_ids = [int(row.id) for row in rows]
    voided_ids = {
        int(row.batch_id)
        for row in db.query(AaSchedulePublish).filter(
            AaSchedulePublish.tenant_id == _tid(),
            AaSchedulePublish.batch_id.in_(batch_ids or [0]),
            AaSchedulePublish.action == "VOID_REISSUE",
            AaSchedulePublish.is_deleted.is_(False),
        ).all()
    }
    changes = db.query(AaScheduleChange).filter(
        AaScheduleChange.tenant_id == _tid(),
        AaScheduleChange.status.in_([
            "SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW", "APPROVED",
        ]),
        AaScheduleChange.is_deleted.is_(False),
    )
    if term_id:
        changes = changes.filter(AaScheduleChange.term_id == int(term_id))
    return schedule_gate_result(rows, voided_ids, int(changes.count() or 0))


def exam_gate_result(
    batches,
    *,
    active_defers: int = 0,
    pending_courses: int = 0,
    not_started_seats: int = 0,
    unresolved_incidents: int = 0,
    active_course_count: int = 0,
):
    batches = list(batches or [])
    if not batches:
        return _core._result(0, False, "本学期没有考务批次")
    unfinished = [
        row for row in batches
        if _status(getattr(row, "status", None)) not in {"FINISHED", "ARCHIVED"}
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未结束/未归档批次 {len(unfinished)} 个")
    if active_course_count <= 0:
        blockers.append("考务批次没有有效考试课程")
    if pending_courses:
        blockers.append(f"仍有待确认考试课程 {int(pending_courses)} 门")
    if not_started_seats:
        blockers.append(f"仍有未登记到考状态考生 {int(not_started_seats)} 人")
    if active_defers:
        blockers.append(f"仍有在途缓考申请 {int(active_defers)} 条")
    if unresolved_incidents:
        blockers.append(f"仍有未闭环考场异常 {int(unresolved_incidents)} 条")
    return _core._result(
        len(batches),
        not blockers,
        "考务批次、到考状态、缓考与异常均已收口" if not blockers else "；".join(blockers),
    )


def evaluate_exam(db, term_id):
    from app.models import (
        AaDeferredExam,
        AaExamBatch,
        AaExamCourse,
        AaExamIncident,
        AaExamRoomStudent,
    )

    query = db.query(AaExamBatch).filter(
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.is_deleted.is_(False),
    )
    if term_id:
        query = query.filter(AaExamBatch.term_id == int(term_id))
    batches = query.all()
    batch_ids = [int(row.id) for row in batches]
    if not batch_ids:
        return exam_gate_result([])

    courses = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _tid(),
        AaExamCourse.batch_id.in_(batch_ids),
        AaExamCourse.status != "REMOVED",
        AaExamCourse.is_deleted.is_(False),
    ).all()
    course_ids = [int(row.id) for row in courses]
    pending_courses = sum(1 for row in courses if _status(row.status) == "PENDING_CONFIRM")
    not_started = active_defers = unresolved = 0
    if course_ids:
        not_started = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.tenant_id == _tid(),
            AaExamRoomStudent.exam_course_id.in_(course_ids),
            AaExamRoomStudent.attendance_status == "NOT_STARTED",
            AaExamRoomStudent.is_deleted.is_(False),
        ).count()
        active_defers = db.query(AaDeferredExam).filter(
            AaDeferredExam.tenant_id == _tid(),
            AaDeferredExam.exam_course_id.in_(course_ids),
            AaDeferredExam.status.notin_(["APPROVED", "REJECTED"]),
            AaDeferredExam.is_deleted.is_(False),
        ).count()
        incidents = db.query(AaExamIncident).filter(
            AaExamIncident.tenant_id == _tid(),
            AaExamIncident.exam_course_id.in_(course_ids),
            AaExamIncident.status == "ACTIVE",
            AaExamIncident.is_deleted.is_(False),
        ).all()
        for incident in incidents:
            if _status(getattr(incident, "incident_type", None)) == "ABSENT" and bool(
                getattr(incident, "risk_alert_sent", False)
            ):
                continue
            if str(getattr(incident, "discipline_case_ref", None) or "").strip():
                continue
            unresolved += 1
    return exam_gate_result(
        batches,
        active_defers=int(active_defers or 0),
        pending_courses=pending_courses,
        not_started_seats=int(not_started or 0),
        unresolved_incidents=unresolved,
        active_course_count=len(courses),
    )
