"""实习域 UnifiedTodo 写入（工作台 P5 / T10 INTERN_MENTOR）。

幂等键对齐 uk_todo_dedup。受理人优先 InternshipRecord.advisor_user_id；停用后仍保留待交接责任。
仅未登记账号编号时允许姓名唯一匹配，不替换已有稳定责任。
"""
from __future__ import annotations

from sqlalchemy import select

from app.services.db_service import _tid

SRC_MODULE = "internship"

TODO_WEEKLY = "INTERN_WEEKLY_REVIEW"
TODO_LEAVE = "INTERN_LEAVE_APPROVAL"
TODO_LEAVE_RETURN = "INTERN_LEAVE_RETURN"
TODO_EXCEPTION = "INTERN_EXCEPTION_HANDLE"
TODO_VISIT_RECTIFY = "INTERN_VISIT_RECTIFY"
TODO_MAKEUP = "INTERN_MAKEUP_APPROVAL"
TODO_CHANGE = "INTERN_CHANGE_APPROVAL"
TODO_ENTERPRISE_CHANGE = "INTERN_ENTERPRISE_CHANGE"
TODO_CHECKIN_EXEMPTION = "INTERN_EXEMPTION_APPROVAL"
TODO_APPLICATION = "INTERN_APPLICATION_REVIEW"
TODO_EXEMPTION_APPLICATION = "INTERN_EXEMPTION_APPLICATION"
TODO_DAILY_REVIEW = "INTERN_DAILY_REVIEW"
TODO_MONTHLY_REVIEW = "INTERN_MONTHLY_REVIEW"
TODO_SUMMARY_REVIEW = "INTERN_SUMMARY_REVIEW"
TODO_EMPLOYMENT = "INTERN_EMPLOYMENT_REPORT"

ADVISOR_TODO_PERMISSIONS = {
    'internship.report.review': [TODO_WEEKLY,TODO_DAILY_REVIEW,TODO_MONTHLY_REVIEW,TODO_SUMMARY_REVIEW],
    'internship.attendance.review': [TODO_EXCEPTION,TODO_CHECKIN_EXEMPTION],
    'internship.makeup.review': [TODO_MAKEUP],
    'internship.change.review': [TODO_CHANGE,TODO_ENTERPRISE_CHANGE],
    'internship.application.review': [TODO_APPLICATION,TODO_EXEMPTION_APPLICATION],
    'internship.visit.manage': [TODO_VISIT_RECTIFY],
    'internship.leave.review': [TODO_LEAVE_RETURN],
    'internship.employment.review': [TODO_EMPLOYMENT],
}


def resolve_advisor_assignee_id(db, rec, *, preserve_unavailable=False) -> int:
    """待办可保留停用责任；要求有效承办人的业务仍按默认检查。"""
    from app.models import User
    if rec is None:
        return 0
    uid = getattr(rec, "advisor_user_id", None)
    if uid:
        row = db.get(User, int(uid))
        if row and row.tenant_id == _tid() and (preserve_unavailable or (not row.is_deleted and row.status == "ACTIVE")):
            return int(row.id)
        return 0
    name = (getattr(rec, "advisor_name", None) or "").strip()
    if not name:
        return 0
    rows = db.scalars(select(User).where(
        User.tenant_id == _tid(), User.real_name == name,
        User.user_type.in_(("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN")),
        User.is_deleted.is_(False), User.status == "ACTIVE")).all()
    return int(rows[0].id) if len(rows) == 1 else 0


def todo_upsert(db, *, biz_type: str, biz_id, todo_type: str, assignee_id: int,
                student_id, title: str) -> bool:
    from app.models import UnifiedTodo
    aid = int(assignee_id or 0)
    if aid <= 0 or not biz_id:
        return False
    bid = int(biz_id)
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == SRC_MODULE,
        UnifiedTodo.source_biz_id == bid, UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == aid, UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title = title
        row.status = "PENDING"
        row.student_id = student_id
        row.source_biz_type = biz_type
        row.version = int(row.version or 0) + 1
        return True
    db.add(UnifiedTodo(
        tenant_id=_tid(), source_module=SRC_MODULE, source_biz_type=biz_type,
        source_biz_id=bid, todo_type=todo_type, assignee_id=aid,
        student_id=student_id, title=title, status="PENDING"))
    return True


def todo_done(db, *, biz_id, todo_type: str) -> int:
    from app.models import UnifiedTodo
    if not biz_id:
        return 0
    n = 0
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == SRC_MODULE,
            UnifiedTodo.source_biz_id == int(biz_id), UnifiedTodo.todo_type == todo_type,
            UnifiedTodo.is_deleted.is_(False), UnifiedTodo.status == "PENDING")).all():
        r.status = "DONE"
        r.version = int(r.version or 0) + 1
        n += 1
    return n


def advisor_todo_sources(tenant_id):
    """The same business links drive mentor handoff and its problem-list entry."""
    from app.models import (WeeklyReport,InternshipProcessReport,InternshipMakeup,
        InternshipChangeRequest,InternshipCheckinExemption,AttendanceException,InternshipVisit,InternshipLeave,InternshipApplication)
    from app.models.internship_employment_registration import InternshipEmploymentRegistration
    specs=[(WeeklyReport,[TODO_WEEKLY]),(InternshipProcessReport,[TODO_DAILY_REVIEW,TODO_MONTHLY_REVIEW,TODO_SUMMARY_REVIEW]),
        (InternshipMakeup,[TODO_MAKEUP]),(InternshipChangeRequest,[TODO_CHANGE,TODO_ENTERPRISE_CHANGE]),
        (InternshipCheckinExemption,[TODO_CHECKIN_EXEMPTION]),(AttendanceException,[TODO_EXCEPTION]),
        (InternshipVisit,[TODO_VISIT_RECTIFY]),(InternshipLeave,[TODO_LEAVE_RETURN]),(InternshipEmploymentRegistration,[TODO_EMPLOYMENT])]
    sources=[(types,select(model.id.label('biz_id'),model.internship_id.label('record_id')).where(
        model.tenant_id==tenant_id,model.is_deleted.is_(False))) for model,types in specs]
    sources.append(([TODO_APPLICATION,TODO_EXEMPTION_APPLICATION],select(InternshipApplication.id.label('biz_id'),
        InternshipApplication.record_id.label('record_id')).where(InternshipApplication.tenant_id==tenant_id,
        InternshipApplication.campaign_id.is_(None),InternshipApplication.is_deleted.is_(False))))
    return sources


def handoff_advisor_todos(db,record,previous_id,recipient_id):
    """Existing mentor-assignment command owns non-workflow todo transfer.

    Leave workflow snapshots require the explicit system-management handoff command.
    Completed actions and original actor facts are never rewritten.
    """
    from sqlalchemy import or_,and_
    from app.models import UnifiedTodo
    if not previous_id or previous_id==recipient_id:return 0
    targets=[]
    for types,query in advisor_todo_sources(record.tenant_id):
        source=query.subquery()
        business=select(source.c.biz_id).where(source.c.record_id==record.id)
        targets.append(and_(UnifiedTodo.todo_type.in_(types),UnifiedTodo.source_biz_id.in_(business)))
    items=db.scalars(select(UnifiedTodo).where(UnifiedTodo.tenant_id==record.tenant_id,
        UnifiedTodo.source_module==SRC_MODULE,UnifiedTodo.assignee_id==previous_id,UnifiedTodo.status=='PENDING',
        UnifiedTodo.is_deleted.is_(False),or_(*targets)).with_for_update()).all()
    if items and not recipient_id:
        from app.core.exceptions import AppException
        raise AppException('VALIDATION_ERROR','原指导教师还有待办，请指定接收教师后再交接')
    for old in items:
        old.status='CANCELLED';old.remark='指导教师交接，原承办人未办理';old.version+=1
        todo_upsert(db,biz_type=old.source_biz_type,biz_id=old.source_biz_id,todo_type=old.todo_type,
            assignee_id=recipient_id,student_id=old.student_id,title=old.title)
    # 历史提交可能没有生成报告待办；只补完全缺失的待批原报告，不复活已办待办。
    recovered=0
    if recipient_id:
        from app.models import WeeklyReport,InternshipProcessReport
        for model,types,push in [(WeeklyReport,[TODO_WEEKLY],push_weekly_todo),
                (InternshipProcessReport,[TODO_DAILY_REVIEW,TODO_MONTHLY_REVIEW,TODO_SUMMARY_REVIEW],push_process_report_todo)]:
            exists=select(UnifiedTodo.id).where(UnifiedTodo.tenant_id==record.tenant_id,
                UnifiedTodo.source_module==SRC_MODULE,UnifiedTodo.source_biz_id==model.id,
                UnifiedTodo.todo_type.in_(types),UnifiedTodo.is_deleted.is_(False)).correlate(model).exists()
            for report in db.scalars(select(model).where(model.tenant_id==record.tenant_id,model.internship_id==record.id,
                    model.is_deleted.is_(False),model.status=='PENDING_REVIEW',~exists).with_for_update()):
                recovered+=int(push(db,report,record))
    return len(items)+recovered


def _stu_name(db, rec) -> str:
    from app.models import StudentProfile
    if not rec or not rec.student_id:
        return "学生"
    stu = db.get(StudentProfile, rec.student_id)
    return (stu.real_name if stu else None) or "学生"


def push_weekly_todo(db, report, rec) -> bool:
    aid = resolve_advisor_assignee_id(db, rec, preserve_unavailable=True)
    week = getattr(report, "week_number", "") or ""
    return todo_upsert(
        db, biz_type="INTERN_WEEKLY", biz_id=report.id, todo_type=TODO_WEEKLY,
        assignee_id=aid, student_id=getattr(rec, "student_id", None),
        title=f"第{week}周周报待批：{_stu_name(db, rec)}")


def push_leave_todo(db, leave, rec) -> bool:
    from app.modules.internship.services.internship_leave_policy_service import start
    return start(db, leave, rec)


def push_leave_return_todo(db, leave, rec) -> bool:
    return todo_upsert(db, biz_type='INTERN_LEAVE', biz_id=leave.id, todo_type=TODO_LEAVE_RETURN,
        assignee_id=resolve_advisor_assignee_id(db, rec, preserve_unavailable=True), student_id=rec.student_id,
        title=f"实习返岗待确认：{_stu_name(db, rec)}")


def push_exception_todo(db, exc, rec) -> bool:
    aid = resolve_advisor_assignee_id(db, rec, preserve_unavailable=True)
    et = getattr(exc, "exception_type", "") or "异常"
    return todo_upsert(
        db, biz_type="INTERN_EXCEPTION", biz_id=exc.id, todo_type=TODO_EXCEPTION,
        assignee_id=aid, student_id=getattr(rec, "student_id", None),
        title=f"打卡异常待处置（{et}）：{_stu_name(db, rec)}")


def push_visit_rectify_todo(db, visit, rec) -> bool:
    aid = resolve_advisor_assignee_id(db, rec, preserve_unavailable=True)
    return todo_upsert(
        db, biz_type="INTERN_VISIT", biz_id=visit.id, todo_type=TODO_VISIT_RECTIFY,
        assignee_id=aid, student_id=getattr(rec, "student_id", None) or getattr(visit, "student_id", None),
        title=f"巡访整改待跟进：{_stu_name(db, rec)}")



def push_makeup_todo(db, makeup, rec) -> bool:
    return todo_upsert(
        db, biz_type="INTERN_MAKEUP", biz_id=makeup.id, todo_type=TODO_MAKEUP,
        assignee_id=resolve_advisor_assignee_id(db, rec, preserve_unavailable=True),
        student_id=getattr(rec, "student_id", None),
        title=f"补签申请待审：{_stu_name(db, rec)}")


def change_todo_type(change) -> str:
    return TODO_ENTERPRISE_CHANGE if str(getattr(change, "change_type", "") or "").upper() == "CHANGE_ENTERPRISE" else TODO_CHANGE


def push_change_todo(db, change, rec) -> bool:
    label = "企业变更" if change_todo_type(change) == TODO_ENTERPRISE_CHANGE else "岗位/实习变更"
    return todo_upsert(
        db, biz_type="INTERN_CHANGE", biz_id=change.id, todo_type=change_todo_type(change),
        assignee_id=resolve_advisor_assignee_id(db, rec, preserve_unavailable=True),
        student_id=getattr(rec, "student_id", None),
        title=f"{label}待审：{_stu_name(db, rec)}")


def push_checkin_exemption_todo(db, item, rec) -> bool:
    return todo_upsert(
        db, biz_type="INTERN_CHECKIN_EXEMPTION", biz_id=item.id,
        todo_type=TODO_CHECKIN_EXEMPTION,
        assignee_id=resolve_advisor_assignee_id(db, rec, preserve_unavailable=True),
        student_id=getattr(rec, "student_id", None),
        title=f"免签申请待审：{_stu_name(db, rec)}")


def application_todo_type(app) -> str:
    return TODO_EXEMPTION_APPLICATION if str(getattr(app, "application_type", "") or "").upper() == "EXEMPTION" else TODO_APPLICATION


def push_application_todo(db, app, rec) -> bool:
    app_type = str(getattr(app, "application_type", "") or "").upper()
    label = {
        "EXEMPTION": "免实习申请",
        "SELF_ARRANGED": "自主实习申请",
        "POSITION": "实习岗位申请",
    }.get(app_type, "实习申请")
    return todo_upsert(
        db, biz_type="INTERN_APPLICATION", biz_id=app.id,
        todo_type=application_todo_type(app),
        assignee_id=resolve_advisor_assignee_id(db, rec, preserve_unavailable=True),
        student_id=getattr(rec, "student_id", None),
        title=f"{label}待审：{_stu_name(db, rec)}")


def process_report_todo_type(report) -> str:
    return {
        "DAILY": TODO_DAILY_REVIEW,
        "MONTHLY": TODO_MONTHLY_REVIEW,
        "SUMMARY": TODO_SUMMARY_REVIEW,
    }.get(str(getattr(report, "report_type", "") or "").upper(), TODO_DAILY_REVIEW)


def push_process_report_todo(db, report, rec) -> bool:
    label = {"DAILY": "日报", "MONTHLY": "月报", "SUMMARY": "实习总结"}.get(
        str(getattr(report, "report_type", "") or "").upper(), "过程报告")
    return todo_upsert(
        db, biz_type="INTERN_PROCESS_REPORT", biz_id=report.id,
        todo_type=process_report_todo_type(report),
        assignee_id=resolve_advisor_assignee_id(db, rec, preserve_unavailable=True),
        student_id=getattr(rec, "student_id", None),
        title=f"{label}待批：{_stu_name(db, rec)}")
