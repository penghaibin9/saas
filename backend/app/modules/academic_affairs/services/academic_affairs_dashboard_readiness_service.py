"""AA-DASHBOARD-01 教务看板统一 readiness 读模型。

只读聚合现有学期、培养方案、教学任务、课表、考务、成绩和在途事项；
不新建异常表、不复制业务状态。所有阻断都回链现有责任页面。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import func, select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session


_STAGE_LABELS = {
    "NO_TERM": "未建立学期",
    "TERM_SETUP": "学期基础配置",
    "PRE_TERM": "开学准备",
    "TEACHING": "教学运行",
    "EXAM": "考试组织",
    "TERM_CLOSE": "成绩与归档收口",
    "ARCHIVED": "学期已归档",
}

_SEVERITY_ORDER = {"BLOCKER": 0, "RISK": 1, "INFO": 2}


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _local_today(db) -> date:
    from .student_exam_read_service import _tenant_timezone

    zone, _name = _tenant_timezone(db)
    return datetime.now(zone).date()


def _term_code(term) -> str:
    return f"{term.year_code}-{term.term_no}" if term else ""


def _term_label(term) -> str:
    if not term:
        return "未设置当前学期"
    return term.term_name or f"{term.year_code} 第{term.term_no}学期"


def _current_week(term, today: date) -> int | None:
    if not term or not term.start_date:
        return None
    start = term.start_date.date() if isinstance(term.start_date, datetime) else term.start_date
    if today < start:
        return 0
    return ((today - start).days // 7) + 1


def _stage(term, today: date) -> tuple[str, int | None]:
    if not term:
        return "NO_TERM", None
    status = str(term.status or "").upper()
    if status == "ARCHIVED":
        return "ARCHIVED", _current_week(term, today)
    if status == "DRAFT":
        return "TERM_SETUP", _current_week(term, today)
    week = _current_week(term, today)
    start = term.start_date.date() if isinstance(term.start_date, datetime) else term.start_date
    end = term.end_date.date() if isinstance(term.end_date, datetime) else term.end_date
    if start and today < start:
        return "PRE_TERM", week
    if end and today > end:
        return "TERM_CLOSE", week
    if term.exam_week_start and week and week >= int(term.exam_week_start):
        return "EXAM", week
    return "TEACHING", week


def _deadline_from_start(term, days_before=0):
    if not term or not term.start_date:
        return None
    start = term.start_date.date() if isinstance(term.start_date, datetime) else term.start_date
    return (start - timedelta(days=days_before)).isoformat()


def _deadline_from_end(term, days_after=0):
    if not term or not term.end_date:
        return None
    end = term.end_date.date() if isinstance(term.end_date, datetime) else term.end_date
    return (end + timedelta(days=days_after)).isoformat()


def _item(
    *,
    key,
    severity,
    title,
    summary,
    rule_code,
    count=1,
    route,
    owner_role,
    deadline=None,
    evidence=None,
):
    assign_route = (
        "/admin/approval?source=academic-readiness"
        f"&ruleCode={quote(str(rule_code))}"
        f"&target={quote(str(route))}"
    )
    return {
        "key": key,
        "severity": severity,
        "title": title,
        "summary": summary,
        "ruleCode": rule_code,
        "count": int(count or 0),
        "route": route,
        "ownerRole": owner_role,
        "deadline": deadline,
        "deadlineLabel": deadline or "未配置明确截止时间",
        "assignRoute": assign_route,
        "evidence": list(evidence or []),
    }


def _scope_college_ids(ctx):
    values = getattr(ctx, "college_ids", None)
    if values is None:
        return None
    return {int(value) for value in values if str(value).isdigit()}


def _load_term(db, term_id=None):
    from app.models import AaTerm

    conditions = [AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)]
    if term_id:
        conditions.append(AaTerm.id == int(term_id))
    else:
        conditions.append(AaTerm.is_current.is_(True))
    term = db.scalars(select(AaTerm).where(*conditions).order_by(AaTerm.id.desc())).first()
    if term_id and not term:
        raise not_found("学期不存在")
    return term


def _term_setup_items(db, term):
    from app.models import AaTimeSlot

    items = []
    if not term:
        return [
            _item(
                key="CURRENT_TERM_MISSING",
                severity="BLOCKER",
                title="尚未设置当前学期",
                summary="教务运行没有时间轴，培养方案、任务、排课、考务和成绩均无法形成统一学期口径。",
                rule_code="DASHBOARD_CURRENT_TERM_REQUIRED",
                route="/admin/academic-affairs/terms",
                owner_role="教务处",
            )
        ]

    missing = []
    if not term.start_date:
        missing.append("开学日期")
    if not term.end_date:
        missing.append("结束日期")
    if not term.teaching_weeks:
        missing.append("教学周数")
    if not term.exam_week_start:
        missing.append("考试周开始周次")
    if missing:
        items.append(_item(
            key="TERM_FIELDS_INCOMPLETE",
            severity="BLOCKER",
            title="学期关键字段不完整",
            summary=f"缺少：{'、'.join(missing)}。无法可靠计算当前周、考试阶段和各业务截止时间。",
            rule_code="DASHBOARD_TERM_FIELDS_REQUIRED",
            count=len(missing),
            route=f"/admin/academic-affairs/terms/{term.id}",
            owner_role="教务处",
            deadline=_deadline_from_start(term),
            evidence=[{"missingFields": missing}],
        ))

    slot_count = db.scalar(select(func.count()).select_from(AaTimeSlot).where(
        AaTimeSlot.tenant_id == _tid(),
        AaTimeSlot.enabled.is_(True),
        AaTimeSlot.is_deleted.is_(False),
    )) or 0
    if slot_count == 0:
        items.append(_item(
            key="TIME_SLOT_MISSING",
            severity="BLOCKER",
            title="尚未配置有效作息节次",
            summary="排课、教师课表、学生课表和考试时间缺少统一节次坐标。",
            rule_code="DASHBOARD_TIME_SLOT_REQUIRED",
            route="/admin/academic-affairs/time-slots",
            owner_role="教务处",
            deadline=_deadline_from_start(term, 30),
        ))
    return items


def _program_items(db, term, college_ids):
    from app.models import StudentProfile
    from .academic_affairs_status_service import is_enrolled
    from .student_program_resolution_service import resolve_student_program

    query = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    )
    if college_ids:
        query = query.filter(StudentProfile.college_id.in_(list(college_ids)))
    students = [row for row in query.all() if is_enrolled(getattr(row, "student_status", None))]
    if not students:
        return []
    unresolved = []
    for student in students:
        result = resolve_student_program(db, student, tenant_id=_tid())
        if result.status != "RESOLVED":
            unresolved.append({
                "studentId": str(student.id),
                "studentNo": getattr(student, "student_no", None),
                "rule": result.rule,
                "message": result.message,
            })
    if not unresolved:
        return []
    return [_item(
        key="PROGRAM_BINDING_UNRESOLVED",
        severity="BLOCKER",
        title="在读学生培养方案未完整绑定",
        summary=f"当前范围有 {len(unresolved)} 名在读学生无法唯一解析培养方案。",
        rule_code="DASHBOARD_PROGRAM_BINDING_REQUIRED",
        count=len(unresolved),
        route="/admin/academic-affairs/programs",
        owner_role="专业负责人 / 学院教务员",
        deadline=_deadline_from_start(term, 30),
        evidence=unresolved[:20],
    )]


def _task_items(db, term, college_ids):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    batch_query = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(term.id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )
    if college_ids:
        batch_query = batch_query.filter(AaTeachingTaskBatch.college_id.in_(list(college_ids)))
    batches = batch_query.all()
    batch_ids = [int(row.id) for row in batches]
    tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(batch_ids or [0]),
        AaTeachingTask.status != "MERGED",
        AaTeachingTask.is_deleted.is_(False),
    ).all()
    if not tasks:
        return [_item(
            key="TEACHING_TASK_MISSING",
            severity="BLOCKER",
            title="本学期尚未生成教学任务",
            summary="培养方案应开课程尚未形成任课教师、班级和学时责任单。",
            rule_code="DASHBOARD_TEACHING_TASK_REQUIRED",
            route="/admin/academic-affairs/teaching-tasks",
            owner_role="学院教务员",
            deadline=_deadline_from_start(term, 21),
        )]

    invalid = [row for row in tasks if str(row.status or "").upper() != "READY" or not str(row.teacher_key or "").strip()]
    unfinished_batches = [row for row in batches if str(row.status or "").upper() not in {"APPROVED", "ARCHIVED"}]
    count = len(invalid) + len(unfinished_batches)
    if not count:
        return []
    return [_item(
        key="TEACHING_TASK_NOT_READY",
        severity="BLOCKER",
        title="教学任务尚未全部确认",
        summary=f"未就绪任务 {len(invalid)} 条，未批准任务批次 {len(unfinished_batches)} 个。",
        rule_code="DASHBOARD_TEACHING_TASK_READY",
        count=count,
        route="/admin/academic-affairs/teaching-tasks",
        owner_role="学院教务员 / 任课教师",
        deadline=_deadline_from_start(term, 14),
        evidence=[
            {"taskId": str(row.id), "status": row.status, "teacherKey": row.teacher_key}
            for row in invalid[:20]
        ],
    )]


def _schedule_items(db, term, college_ids):
    from app.models import AaScheduleBatch, AaScheduleItem
    from .academic_affairs_archive_rule_evaluator import hard_schedule_conflicts

    query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.term_id == int(term.id),
        AaScheduleBatch.status == "PUBLISHED",
        AaScheduleBatch.is_deleted.is_(False),
    )
    if college_ids:
        query = query.filter(AaScheduleBatch.college_id.in_(list(college_ids)))
    batches = query.all()
    if not batches:
        return [_item(
            key="SCHEDULE_NOT_PUBLISHED",
            severity="BLOCKER",
            title="本学期课表尚未正式发布",
            summary="学生和教师无法取得统一正式课表，教学运行不可继续。",
            rule_code="DASHBOARD_SCHEDULE_PUBLISHED",
            route="/admin/academic-affairs/scheduling",
            owner_role="排课管理员",
            deadline=_deadline_from_start(term, 7),
        )]
    batch_ids = [int(row.id) for row in batches]
    rows = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(batch_ids),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all()
    conflicts = hard_schedule_conflicts(rows)
    if not conflicts:
        return []
    return [_item(
        key="SCHEDULE_HARD_CONFLICT",
        severity="BLOCKER",
        title="正式课表存在硬冲突",
        summary=f"发现 {len(conflicts)} 组教师、班级或教室同时间冲突。",
        rule_code="DASHBOARD_SCHEDULE_HARD_CONFLICT",
        count=len(conflicts),
        route="/admin/academic-affairs/scheduling",
        owner_role="排课管理员",
        deadline=_deadline_from_start(term, 7),
        evidence=conflicts[:20],
    )]


def _exam_items(db, term, stage):
    if stage not in {"EXAM", "TERM_CLOSE"}:
        return []
    from app.models import AaExamBatch, AaExamCourse

    batches = db.query(AaExamBatch).filter(
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.term_id == int(term.id),
        AaExamBatch.is_deleted.is_(False),
    ).all()
    formal = [row for row in batches if str(row.status or "").upper() in {"PUBLISHED", "FINISHED", "ARCHIVED", "CLOSED"}]
    if not formal:
        return [_item(
            key="EXAM_NOT_PUBLISHED",
            severity="BLOCKER",
            title="本学期考试安排尚未正式发布",
            summary="当前已进入考试或收口阶段，但没有可供师生查询的正式考试批次。",
            rule_code="DASHBOARD_EXAM_PUBLISHED",
            route="/admin/academic-affairs/exam",
            owner_role="考务管理员",
            deadline=_deadline_from_start(term, max(int(term.exam_week_start or 1) * 7 - 7, 0)),
        )]
    batch_ids = [int(row.id) for row in formal]
    courses = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _tid(),
        AaExamCourse.batch_id.in_(batch_ids),
        AaExamCourse.is_deleted.is_(False),
    ).all()
    incomplete = [row for row in courses if str(row.status or "").upper() not in {"CONFIRMED", "FINISHED", "ARCHIVED"}]
    if not incomplete:
        return []
    return [_item(
        key="EXAM_COURSE_INCOMPLETE",
        severity="BLOCKER" if stage == "EXAM" else "RISK",
        title="考试课程仍有未确认安排",
        summary=f"{len(incomplete)} 门考试课程尚未完成时间、考场或名单确认。",
        rule_code="DASHBOARD_EXAM_COURSE_CONFIRMED",
        count=len(incomplete),
        route="/admin/academic-affairs/exam",
        owner_role="考务管理员",
        deadline=_deadline_from_end(term),
        evidence=[{"examCourseId": str(row.id), "status": row.status} for row in incomplete[:20]],
    )]


def _grade_items(db, term, stage):
    if stage not in {"EXAM", "TERM_CLOSE"}:
        return []
    from app.models import AaGradeTask

    tasks = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.term_code == _term_code(term),
        AaGradeTask.is_deleted.is_(False),
    ).all()
    if not tasks:
        return [_item(
            key="GRADE_TASK_MISSING",
            severity="RISK" if stage == "EXAM" else "BLOCKER",
            title="本学期尚未建立成绩录入任务",
            summary="考试已进入收口阶段，但任课教师尚无正式成绩录入责任单。",
            rule_code="DASHBOARD_GRADE_TASK_REQUIRED",
            route="/admin/academic-affairs/grade-tasks",
            owner_role="教务处 / 学院教务员",
            deadline=_deadline_from_end(term, 7),
        )]
    unfinished = [row for row in tasks if str(row.status or "").upper() not in {"PUBLISHED", "ARCHIVED"}]
    if not unfinished:
        return []
    return [_item(
        key="GRADE_TASK_UNFINISHED",
        severity="RISK" if stage == "EXAM" else "BLOCKER",
        title="成绩任务尚未全部发布",
        summary=f"{len(unfinished)} 个成绩任务仍处于录入、退回或审核状态。",
        rule_code="DASHBOARD_GRADE_TASK_PUBLISHED",
        count=len(unfinished),
        route="/admin/academic-affairs/grade-tasks",
        owner_role="任课教师 / 学院教务员 / 教务处",
        deadline=_deadline_from_end(term, 7),
        evidence=[{"gradeTaskId": str(row.id), "status": row.status} for row in unfinished[:20]],
    )]


def _operation_risks(db, term):
    from app.models import AaScheduleChange, AaStatusChange, AcademicWarning

    risks = []
    pending_changes = db.query(AaScheduleChange).filter(
        AaScheduleChange.tenant_id == _tid(),
        AaScheduleChange.term_id == int(term.id),
        AaScheduleChange.status.in_(["SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"]),
        AaScheduleChange.is_deleted.is_(False),
    ).count()
    if pending_changes:
        risks.append(_item(
            key="SCHEDULE_CHANGE_PENDING",
            severity="RISK",
            title="存在在途调停课申请",
            summary=f"{pending_changes} 条调课、停课或补课申请尚未生效。",
            rule_code="DASHBOARD_SCHEDULE_CHANGE_PENDING",
            count=pending_changes,
            route="/admin/academic-affairs/schedule-changes",
            owner_role="学院教务员 / 教务处",
        ))

    pending_status = db.query(AaStatusChange).filter(
        AaStatusChange.tenant_id == _tid(),
        AaStatusChange.status.in_(["SUBMITTED", "IN_REVIEW"]),
        AaStatusChange.is_deleted.is_(False),
    ).count()
    if pending_status:
        risks.append(_item(
            key="STATUS_CHANGE_PENDING",
            severity="RISK",
            title="存在在途学籍异动",
            summary=f"{pending_status} 条学籍异动尚未完成审批或生效。",
            rule_code="DASHBOARD_STATUS_CHANGE_PENDING",
            count=pending_status,
            route="/admin/academic-affairs/status-changes",
            owner_role="学院教务员 / 教务处",
        ))

    high_warnings = db.query(AcademicWarning).filter(
        AcademicWarning.tenant_id == _tid(),
        AcademicWarning.level == "HIGH",
        AcademicWarning.status == "PENDING_HANDLE",
        AcademicWarning.record_status == "ACTIVE",
        AcademicWarning.is_deleted.is_(False),
    ).count()
    if high_warnings:
        risks.append(_item(
            key="HIGH_WARNING_PENDING",
            severity="RISK",
            title="高等级学业预警待处置",
            summary=f"{high_warnings} 条高等级学业预警尚未形成闭环。",
            rule_code="DASHBOARD_HIGH_WARNING_PENDING",
            count=high_warnings,
            route="/admin/academic-affairs/warnings",
            owner_role="辅导员 / 学院教务员",
        ))
    return risks


def readiness(user, term_id=None) -> dict:
    with session() as db:
        ctx = build_affairs_context(user, db)
        term = _load_term(db, term_id)
        today = _local_today(db)
        stage, week = _stage(term, today)
        college_ids = _scope_college_ids(ctx)

        items = _term_setup_items(db, term)
        if term and stage not in {"TERM_SETUP", "ARCHIVED"}:
            items.extend(_program_items(db, term, college_ids))
            items.extend(_task_items(db, term, college_ids))
            items.extend(_schedule_items(db, term, college_ids))
            items.extend(_exam_items(db, term, stage))
            items.extend(_grade_items(db, term, stage))
            items.extend(_operation_risks(db, term))

        items.sort(key=lambda row: (
            _SEVERITY_ORDER.get(row["severity"], 9),
            row["deadline"] or "9999-12-31",
            row["key"],
        ))
        blocker_count = sum(row["count"] for row in items if row["severity"] == "BLOCKER")
        risk_count = sum(row["count"] for row in items if row["severity"] == "RISK")
        status = "BLOCKED" if blocker_count else ("RISK" if risk_count else "NORMAL")
        conclusion = {
            "BLOCKED": "本学期当前阶段不可继续，请先处理阻断项",
            "RISK": "本学期可以继续，但存在需要尽快处理的风险",
            "NORMAL": "本学期当前阶段运行正常，可以继续",
        }[status]
        if stage == "ARCHIVED":
            status = "NORMAL"
            conclusion = "本学期已经完成正式归档，业务数据保持只读"

        return {
            "term": {
                "termId": str(term.id) if term else None,
                "termCode": _term_code(term),
                "termLabel": _term_label(term),
                "status": term.status if term else None,
                "startDate": _iso(term.start_date) if term else None,
                "endDate": _iso(term.end_date) if term else None,
                "teachingWeeks": term.teaching_weeks if term else None,
                "examWeekStart": term.exam_week_start if term else None,
            },
            "stage": stage,
            "stageLabel": _STAGE_LABELS[stage],
            "currentWeek": week,
            "today": today.isoformat(),
            "status": status,
            "conclusion": conclusion,
            "blockerCount": blocker_count,
            "riskCount": risk_count,
            "itemCount": len(items),
            "topItems": items[:3],
            "items": items,
            "scopeType": getattr(ctx, "scope_type", None),
            "generatedAt": datetime.utcnow().isoformat(),
        }


def export_readiness_xlsx(user, term_id=None, purpose="") -> tuple[bytes, str]:
    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于5个字")
    data = readiness(user, term_id)
    from app.services.xlsx_util import build_ledger_xlsx

    headers = ["级别", "阻断/风险项", "规则编号", "数量", "责任角色", "截止时间", "处理入口", "说明"]
    rows = [
        [
            "阻断" if row["severity"] == "BLOCKER" else "风险",
            row["title"],
            row["ruleCode"],
            row["count"],
            row["ownerRole"],
            row["deadlineLabel"],
            row["route"],
            row["summary"],
        ]
        for row in data["items"]
    ]
    if not rows:
        rows = [["正常", "当前阶段无阻断或风险", "DASHBOARD_READY", 0, "—", "—", "—", data["conclusion"]]]
    watermark = (
        f"学期：{data['term']['termLabel']}  导出时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  "
        f"用途：{purpose}"
    )
    content = build_ledger_xlsx("开学与学期运行准备清单", headers, rows, watermark=watermark)
    term_code = data["term"]["termCode"] or "未设置学期"
    return content, f"{term_code}-教务运行准备清单.xlsx"
