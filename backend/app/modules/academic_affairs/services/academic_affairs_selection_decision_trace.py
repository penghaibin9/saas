"""Stage D adapter from existing selection decisions to deterministic DecisionTrace.

This module does not re-run selection rules. The canonical selection service remains the
only decision authority; this adapter translates the AppException produced at that exact
business branch into a stable RuleCode and attaches safe, student-facing evidence.
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException

from .academic_affairs_decision_trace import build_decision_trace


_RESOLUTIONS = {
    "STUDENT_STATUS_NOT_ELIGIBLE": [
        {"code": "CHECK_STUDENT_STATUS", "label": "核对当前学籍状态，如有误请联系教务老师"},
    ],
    "BATCH_NOT_OPEN": [
        {"code": "RETRY_DURING_OPEN_WINDOW", "label": "在选课批次开放时间内重新办理"},
    ],
    "OUT_OF_COLLEGE_SCOPE": [
        {"code": "CHECK_ACADEMIC_SCOPE", "label": "如学院信息有误，请联系教务老师核对学籍范围"},
    ],
    "OUT_OF_MAJOR_SCOPE": [
        {"code": "CHECK_ACADEMIC_SCOPE", "label": "如专业信息有误，请联系教务老师核对学籍范围"},
    ],
    "OUT_OF_GRADE_SCOPE": [
        {"code": "CHECK_ACADEMIC_SCOPE", "label": "如年级信息有误，请联系教务老师核对学籍范围"},
    ],
    "ALREADY_SELECTED": [
        {"code": "VIEW_MY_SELECTIONS", "label": "查看“我的选课”确认当前有效记录"},
    ],
    "COURSE_ALREADY_PASSED": [
        {"code": "VIEW_PASSED_GRADE", "label": "查看该课程已通过的正式成绩；如需再次修读，请按学校重修流程办理"},
    ],
    "PREREQUISITE_NOT_MET": [
        {"code": "COMPLETE_PREREQUISITES", "label": "先完成并通过缺失的先修课程"},
    ],
    "MAX_CREDITS_EXCEEDED": [
        {"code": "REVIEW_SELECTED_CREDITS", "label": "核对已选课程与本轮学分上限"},
    ],
    "TIME_CONFLICT": [
        {"code": "REVIEW_SCHEDULE", "label": "调整与本课程冲突的已选课程"},
    ],
    "COURSE_FULL": [
        {"code": "CHOOSE_AVAILABLE_COURSE", "label": "选择仍有余量的其他可选课程"},
    ],
    "COURSE_MASTER_MISSING": [
        {"code": "CONTACT_ACADEMIC_ADMIN", "label": "联系教务管理员修复课程主档关联"},
    ],
    "COURSE_RULE_BROKEN": [
        {"code": "CONTACT_ACADEMIC_ADMIN", "label": "联系教务管理员修复选课规则配置"},
    ],
    "TERM_ARCHIVED": [
        {"code": "CONTACT_POST_ARCHIVE_CORRECTION", "label": "该学期已归档；如确需更正，请联系教务老师按归档后纠错流程处理"},
    ],
    "SELECTION_LOCKED": [
        {"code": "CHECK_SELECTION_WINDOW", "label": "查看当前选课轮次或批次状态"},
    ],
    "LOTTERY_PENDING": [
        {"code": "WAIT_LOTTERY_RESULT", "label": "等待本轮抽签结果"},
    ],
}


def _masked_student_ref(student) -> str:
    value = str(getattr(student, "student_no", "") or "").strip()
    if len(value) <= 4:
        return "masked:student"
    return f"masked:{value[:4]}{'*' * max(2, len(value) - 6)}{value[-2:]}"


def _target(db, course) -> dict:
    target = {"courseName": str(getattr(course, "course_name", "") or "")}
    course_id = getattr(course, "course_id", None)
    if not course_id:
        return target
    try:
        from app.models import AaCourse
        from app.services.db_service import _tid
        catalog = db.query(AaCourse).filter(
            AaCourse.tenant_id == _tid(),
            AaCourse.id == int(course_id),
            AaCourse.is_deleted.is_(False),
        ).first()
    except Exception:  # explanation lookup must never change the business decision
        catalog = None
    if catalog:
        target["courseCode"] = str(catalog.course_code or "")
        target["courseName"] = str(catalog.course_name or target["courseName"])
    return target


def classify_selection_exception(exc: AppException) -> str | None:
    """Translate the already-raised canonical decision; never re-evaluate business data."""
    msg = str(getattr(exc, "message", "") or "")
    code = str(getattr(exc, "code", "") or "")
    if code == "TERM_ARCHIVED" or "学期已归档" in msg or "归档后" in msg:
        return "TERM_ARCHIVED"
    ordered = (
        ("当前学籍状态不可选课", "STUDENT_STATUS_NOT_ELIGIBLE"),
        ("不在选课时间内", "BATCH_NOT_OPEN"),
        ("学院范围", "OUT_OF_COLLEGE_SCOPE"),
        ("专业范围", "OUT_OF_MAJOR_SCOPE"),
        ("年级范围", "OUT_OF_GRADE_SCOPE"),
        ("已修读通过", "COURSE_ALREADY_PASSED"),
        ("未满足先修课程", "PREREQUISITE_NOT_MET"),
        ("超过本轮选课最大学分限制", "MAX_CREDITS_EXCEEDED"),
        ("上课时间冲突", "TIME_CONFLICT"),
        ("课程容量已满", "COURSE_FULL"),
        ("选课供给项未关联有效课程主档", "COURSE_MASTER_MISSING"),
        ("课程主档不存在或已删除", "COURSE_MASTER_MISSING"),
        ("先修规则JSON损坏", "COURSE_RULE_BROKEN"),
        ("先修规则格式错误", "COURSE_RULE_BROKEN"),
        ("maxCredits 配置无效", "COURSE_RULE_BROKEN"),
        ("maxCredits 不可小于", "COURSE_RULE_BROKEN"),
        ("同一课程代码已存在在途选课记录", "ALREADY_SELECTED"),
        ("该课程已选", "ALREADY_SELECTED"),
        ("已存在有效选课记录", "ALREADY_SELECTED"),
        ("课程已取消或不可选", "SELECTION_LOCKED"),
        ("当前轮次不允许选课", "SELECTION_LOCKED"),
    )
    for needle, rule in ordered:
        if needle in msg:
            return rule
    return None


def attach_selection_trace(
    exc: AppException,
    *,
    db,
    student,
    course,
    evaluated_at: datetime,
    rule_code: str | None = None,
    failed_nodes: list[dict] | None = None,
    passed_nodes: list[dict] | None = None,
    available_resolutions: list[dict] | None = None,
) -> AppException:
    """Attach trace to the original exception so code/message/http semantics stay intact."""
    resolved_rule = rule_code or classify_selection_exception(exc)
    if not resolved_rule:
        return exc
    resolutions = available_resolutions
    if resolutions is None:
        resolutions = list(_RESOLUTIONS.get(resolved_rule, []))
    exc.decision_trace = build_decision_trace(
        domain="SELECTION",
        action="ENROLL",
        decision="DENIED",
        rule_code=resolved_rule,
        rule_version="selection-d1",
        subject={"studentId": _masked_student_ref(student)},
        target=_target(db, course),
        failed_nodes=failed_nodes or [{"code": resolved_rule}],
        passed_nodes=passed_nodes or [],
        available_resolutions=resolutions,
        evaluated_at=evaluated_at,
    )
    return exc
