"""教务归档语义策略层。

V1 冻结产品高度，V2 冻结施工规则，当前代码/模型是事实基线。本模块不建立第二套归档事实，
只在既有 ``academic_affairs_archive_facade`` 上替换三类容易误判的语义门禁：

1. 课表：正式发布/正式归档可归档学期；预发布永远阻断；历史废弃草稿不覆盖正式版本；
   VOID_REISSUE 作废批次必须有替代的正式发布版本；在途调停课必须先落成 APPLIED。
2. 考务：批次须 FINISHED/ARCHIVED；课程确认、考生到考状态、缓考审批和考场异常均须收口。
3. 成绩：除成绩复查外，记录级成绩更正工作流 RUNNING 也属于在途事项，必须按本学期阻断。

原归档批次、导出、下载审计、解冻、确认归档和写保护继续委托既有 facade。
"""
from __future__ import annotations

from sqlalchemy import select

from app.services.db_service import _tid

from . import academic_affairs_archive_facade as _base

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def _status(value) -> str:
    return str(value or "").strip().upper()


def _schedule_gate_result(rows, voided_batch_ids=None, active_changes: int = 0):
    """纯规则函数，供真实查询与回归测试共用。"""
    rows = list(rows or [])
    voided_ids = {int(value) for value in (voided_batch_ids or set())}
    if not rows:
        return _legacy._result(0, False, "本学期没有课表批次")

    published = []
    formal_archived = []
    voided = []
    drafts = []
    pre_published = []
    unknown = []

    for row in rows:
        status = _status(getattr(row, "status", None))
        row_id = int(getattr(row, "id", 0) or 0)
        if status == "PUBLISHED":
            published.append(row)
        elif status == "ARCHIVED":
            if row_id in voided_ids:
                voided.append(row)
            else:
                formal_archived.append(row)
        elif status == "VOIDED":  # 兼容未来把作废从 ARCHIVED 中拆出的迁移态
            voided.append(row)
        elif status == "DRAFT":
            drafts.append(row)
        elif status == "PRE_PUBLISHED":
            pre_published.append(row)
        else:
            unknown.append(row)

    valid_final = published + formal_archived
    blockers = []
    if pre_published:
        blockers.append(f"仍有预发布批次 {len(pre_published)} 个")
    if active_changes:
        blockers.append(f"仍有在途调停课 {int(active_changes)} 条")
    if unknown:
        blockers.append(f"存在未知状态批次 {len(unknown)} 个")
    if not valid_final:
        if voided and not drafts and not pre_published and not unknown:
            blockers.append(f"仅有已作废批次 {len(voided)} 个，必须先发布替代课表")
        elif drafts and not voided and not pre_published and not unknown:
            blockers.append(f"仅有草稿批次 {len(drafts)} 个，尚未形成正式课表")
        else:
            blockers.append("没有 PUBLISHED 或正式 ARCHIVED 课表")

    passed = not blockers
    if passed:
        remark = (
            f"正式发布 {len(published)} 个、正式归档 {len(formal_archived)} 个"
            f"；历史草稿 {len(drafts)} 个、作废批次 {len(voided)} 个不覆盖正式版本"
        )
    else:
        remark = "；".join(blockers)
        if drafts and valid_final:
            remark += f"；另有历史草稿 {len(drafts)} 个，因已有正式版本不单独阻断"
        if voided and valid_final:
            remark += f"；另有作废批次 {len(voided)} 个，已有替代正式版本"
    return _legacy._result(len(rows), passed, remark)


def _evaluate_schedule(db, term_id, college_ids=None):
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

    voided_ids = set()
    if batch_ids:
        voided_ids = {
            int(row.batch_id)
            for row in db.query(AaSchedulePublish).filter(
                AaSchedulePublish.tenant_id == _tid(),
                AaSchedulePublish.batch_id.in_(batch_ids),
                AaSchedulePublish.action == "VOID_REISSUE",
                AaSchedulePublish.is_deleted.is_(False),
            ).all()
        }

    active_change_query = db.query(AaScheduleChange).filter(
        AaScheduleChange.tenant_id == _tid(),
        AaScheduleChange.status.in_([
            "SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW", "APPROVED",
        ]),
        AaScheduleChange.is_deleted.is_(False),
    )
    if term_id:
        active_change_query = active_change_query.filter(AaScheduleChange.term_id == int(term_id))
    active_changes = active_change_query.count()
    return _schedule_gate_result(rows, voided_ids, active_changes)


def _exam_gate_result(
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
        return _legacy._result(0, False, "本学期没有考务批次")

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

    passed = not blockers
    return _legacy._result(
        len(batches),
        passed,
        "考务批次、到考状态、缓考与异常均已收口" if passed else "；".join(blockers),
    )


def _evaluate_exam(db, term_id):
    from app.models import (
        AaDeferredExam,
        AaExamBatch,
        AaExamCourse,
        AaExamIncident,
        AaExamRoomStudent,
    )

    batch_query = db.query(AaExamBatch).filter(
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.is_deleted.is_(False),
    )
    if term_id:
        batch_query = batch_query.filter(AaExamBatch.term_id == int(term_id))
    batches = batch_query.all()
    batch_ids = [int(row.id) for row in batches]
    if not batch_ids:
        return _exam_gate_result([])

    courses = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _tid(),
        AaExamCourse.batch_id.in_(batch_ids),
        AaExamCourse.status != "REMOVED",
        AaExamCourse.is_deleted.is_(False),
    ).all()
    course_ids = [int(row.id) for row in courses]
    pending_courses = sum(1 for row in courses if _status(row.status) == "PENDING_CONFIRM")

    not_started_seats = 0
    active_defers = 0
    unresolved_incidents = 0
    if course_ids:
        not_started_seats = db.query(AaExamRoomStudent).filter(
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
            incident_type = _status(getattr(incident, "incident_type", None))
            if incident_type == "ABSENT" and bool(getattr(incident, "risk_alert_sent", False)):
                continue
            if str(getattr(incident, "discipline_case_ref", None) or "").strip():
                continue
            unresolved_incidents += 1

    return _exam_gate_result(
        batches,
        active_defers=active_defers,
        pending_courses=pending_courses,
        not_started_seats=not_started_seats,
        unresolved_incidents=unresolved_incidents,
        active_course_count=len(courses),
    )


def _grade_gate_result(tasks, *, active_rechecks: int = 0, active_changes: int = 0):
    tasks = list(tasks or [])
    if not tasks:
        return _legacy._result(0, False, "本学期没有成绩任务")
    unfinished = [
        row for row in tasks
        if _status(getattr(row, "status", None)) not in {"PUBLISHED", "ARCHIVED"}
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未发布/未归档成绩任务 {len(unfinished)} 个")
    if active_rechecks:
        blockers.append(f"本学期在途复查 {int(active_rechecks)} 条")
    if active_changes:
        blockers.append(f"本学期在途成绩更正 {int(active_changes)} 条")
    passed = not blockers
    return _legacy._result(
        len(tasks),
        passed,
        "成绩任务均已发布且无在途复查/更正" if passed else "，".join(blockers),
    )


def _evaluate_grade(db, term_code):
    from app.models import AaGradeRecheck, AaGradeRecord, AaGradeTask, AcademicGrade, WorkflowInstance

    task_query = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.is_deleted.is_(False),
    )
    if term_code:
        task_query = task_query.filter(AaGradeTask.term_code == term_code)
    tasks = task_query.all()

    recheck_query = db.query(AaGradeRecheck).join(
        AcademicGrade,
        AcademicGrade.id == AaGradeRecheck.acad_grade_id,
    ).filter(
        AaGradeRecheck.tenant_id == _tid(),
        AaGradeRecheck.is_deleted.is_(False),
        AaGradeRecheck.status == "SUBMITTED",
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.is_deleted.is_(False),
    )
    if term_code:
        recheck_query = recheck_query.filter(AcademicGrade.term == term_code)
    active_rechecks = recheck_query.count()

    change_query = db.query(WorkflowInstance).join(
        AaGradeRecord,
        AaGradeRecord.id == WorkflowInstance.source_biz_id,
    ).join(
        AaGradeTask,
        AaGradeTask.id == AaGradeRecord.task_id,
    ).filter(
        WorkflowInstance.tenant_id == _tid(),
        WorkflowInstance.source_module == "academic-affairs",
        WorkflowInstance.source_biz_type == "AA_GRADE_CHANGE",
        WorkflowInstance.status == "RUNNING",
        WorkflowInstance.is_deleted.is_(False),
        AaGradeRecord.tenant_id == _tid(),
        AaGradeRecord.is_deleted.is_(False),
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.is_deleted.is_(False),
    )
    if term_code:
        change_query = change_query.filter(AaGradeTask.term_code == term_code)
    active_changes = change_query.count()
    return _grade_gate_result(
        tasks,
        active_rechecks=active_rechecks,
        active_changes=active_changes,
    )


# 既有 facade 的 run_check/precheck 会在运行时从自身 globals / legacy 模块取函数。
# 显式替换后，无需复制归档批次、导出和封存代码，也不会形成两套事实。
_legacy._evaluate_schedule = _evaluate_schedule
_legacy._evaluate_exam = _evaluate_exam
_base._evaluate_grade = _evaluate_grade
