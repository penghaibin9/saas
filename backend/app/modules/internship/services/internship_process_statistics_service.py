"""Yiyang C08 AP19-AP24 process statistics.

One canonical aggregation engine serves student process statistics, advisor performance,
homeroom performance, and college/major/class summaries. Screen and Excel use the exact
same row builder and column allow-list so custom columns cannot silently change the metric
population.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import or_, select

from app.core.exceptions import AppException
from app.models import (
    College,
    InternshipApplication,
    InternshipChangeRequest,
    InternshipCheckin,
    InternshipCheckinExemption,
    InternshipFinalScore,
    InternshipLeave,
    InternshipMakeup,
    InternshipProcessReport,
    InternshipRecord,
    InternshipReportReview,
    Major,
    SchoolClass,
    StudentAccountLink,
    StudentProfile,
    StaffAssignment,
    User,
    WeeklyReport,
)
from app.modules.internship.services import internship_stats_service as base_stats
from app.modules.internship.services.internship_report_quality_service import (
    SUBMITTED_REPORT_STATUSES, required_report_counts,
    latest_snapshot_map,
)
from app.modules.internship.services.internship_batch_context import resolve_batch
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.services import xlsx_util
from app.services.db_service import _tid, session
from app.core.timeutil import local_now
from app.modules.internship.services.internship_leave_service import effective_period

GROUPS = {"STUDENT", "ADVISOR", "HOMEROOM", "COLLEGE", "MAJOR", "CLASS"}
PERIODS = {"WEEK", "MONTH", "ALL"}

COLUMN_SETS = {
    "STUDENT": [
        ("studentName", "姓名"), ("studentNo", "学号"), ("grade", "年级"),
        ("batchName", "所属计划"), ("college", "院系"), ("major", "专业"),
        ("className", "班级"), ("advisorName", "指导老师"),
        ("headTeacherName", "班主任"), ("enterpriseCount", "实习企业数量"),
        ("expectedCheckins", "应签到数"), ("actualCheckins", "实际签到数"),
        ("leaveDays", "请假天数"), ("exemptDays", "免签天数"),
        ("makeupDays", "补签天数"), ("dailySubmitted", "日报提交数"),
        ("weeklyExpected", "周报应交数"), ("weeklySubmitted", "周报实交数"),
        ("weeklyLate", "周报迟交数"), ("weeklyCompletionRate", "周报完成率"),
        ("monthlyExpected", "应交月报数"), ("monthlySubmitted", "实交月报数"),
        ("summarySubmitted", "实交总结数"), ("totalScore", "成绩分数"),
    ],
    "ADVISOR": [
        ("name", "指导老师姓名"), ("employeeNo", "教工号"), ("college", "所属院系"),
        ("internshipType", "实习类型"), ("studentCount", "所带学生数"),
        ("boundCount", "学生绑定数"), ("checkinCount", "学生签到数"),
        ("averageCheckins", "平均签到数"), ("averageCheckinRate", "平均签到率"),
        ("dailyCount", "学生日志数"), ("weeklyExpected", "学生应交周报数"),
        ("weeklySubmitted", "实交周报数"), ("weeklyMissing", "未交周报数"),
        ("weeklyReviewed", "周报批阅数"), ("weeklyReviewRate", "周报批阅率"),
        ("weeklyTimelyReviewRate", "周报准时批阅率"), ("monthlySubmitted", "月报实交数"),
        ("monthlyCompletionRate", "月报完成率"), ("monthlyReviewRate", "月报批阅率"),
        ("monthlyTimelyReviewRate", "月报准时批阅率"), ("summarySubmitted", "实习总结数"),
        ("summaryReviewRate", "总结批阅率"),
    ],
    "HOMEROOM": [
        ("name", "姓名"), ("employeeNo", "教工号"), ("college", "所属院系"),
        ("className", "班级"), ("internshipType", "实习类型"),
        ("studentCount", "学生数"), ("boundCount", "绑定数"),
        ("checkinCount", "签到数"), ("averageCheckinRate", "平均签到率"),
        ("dailyCount", "日志数"), ("weeklySubmitted", "周报数"),
        ("weeklyCompletionRate", "周报完成率"), ("weeklyReviewed", "周报批阅数"),
        ("weeklyReviewRate", "周报批阅率"), ("weeklyTimelyReviewRate", "准时批阅率"),
        ("monthlySubmitted", "月报数"), ("monthlyCompletionRate", "月报完成率"),
        ("monthlyReviewRate", "月报批阅率"), ("summarySubmitted", "总结数"),
        ("summaryReviewRate", "总结批阅率"),
    ],
    "COLLEGE": [
        ("college", "院系"), ("grades", "年级"), ("studentCount", "学生人数"),
        ("internshipStudentCount", "实习人数"), ("boundCount", "绑定数"),
        ("bindingRate", "绑定率"), ("exemptInternshipCount", "免实习人数"),
        ("onboardCount", "上岗人次"), ("onboardRate", "上岗率"),
        ("majorMatchRate", "对口率"), ("stabilityRate", "稳定率"),
        ("averageCheckins", "人均签到数"), ("checkinRate", "签到率"),
        ("dailyCount", "日报数"), ("weeklyExpected", "应交周报数"),
        ("weeklySubmitted", "实交周报数"), ("weeklyCompletionRate", "周报完成率"),
        ("weeklyReviewed", "周报批阅数"), ("weeklyReviewRate", "周报批阅率"),
        ("monthlySubmitted", "月报数"), ("monthlyCompletionRate", "月报完成率"),
        ("monthlyReviewed", "月报批阅数"), ("monthlyReviewRate", "月报批阅率"),
        ("summarySubmitted", "总结数"),
    ],
    "MAJOR": [
        ("college", "院系"), ("grades", "年级"), ("major", "专业"),
        ("studentCount", "学生人数"), ("internshipStudentCount", "实习人数"),
        ("boundCount", "绑定数"), ("bindingRate", "绑定率"),
        ("exemptInternshipCount", "免实习人数"), ("onboardCount", "上岗人次"),
        ("onboardRate", "上岗率"), ("majorMatchRate", "对口率"),
        ("stabilityRate", "稳定率"), ("averageCheckins", "人均签到数"),
        ("checkinRate", "签到率"), ("dailyCount", "日报数"),
        ("weeklyExpected", "应交周报数"), ("weeklySubmitted", "实交周报数"),
        ("weeklyCompletionRate", "周报完成率"), ("weeklyReviewed", "周报批阅数"),
        ("weeklyReviewRate", "周报批阅率"), ("monthlySubmitted", "月报数"),
        ("monthlyCompletionRate", "月报完成率"), ("monthlyReviewed", "月报批阅数"),
        ("monthlyReviewRate", "月报批阅率"), ("summarySubmitted", "总结数"),
    ],
    "CLASS": [
        ("college", "院系"), ("grades", "年级"), ("major", "专业"),
        ("className", "班级"), ("headTeacherName", "班主任"),
        ("studentCount", "学生人数"), ("internshipStudentCount", "实习人数"),
        ("boundCount", "绑定数"), ("bindingRate", "绑定率"),
        ("exemptInternshipCount", "免实习人数"), ("onboardCount", "上岗人数"),
        ("onboardRate", "上岗率"), ("majorMatchRate", "对口率"),
        ("stabilityRate", "稳定率"), ("averageCheckins", "人均签到数"),
        ("checkinRate", "签到率"), ("dailyCount", "日报数"),
        ("weeklyExpected", "应交周报数"), ("weeklySubmitted", "实交周报数"),
        ("weeklyCompletionRate", "周报完成率"), ("weeklyReviewed", "周报批阅数"),
        ("weeklyReviewRate", "周报批阅率"), ("monthlySubmitted", "月报数"),
        ("monthlyCompletionRate", "月报完成率"), ("monthlyReviewed", "月报批阅数"),
        ("monthlyReviewRate", "月报批阅率"), ("summarySubmitted", "总结数"),
    ],
}


def _ratio(num: int | float, den: int | float):
    return round(float(num) * 100.0 / float(den), 1) if den else None


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        from app.core.timeutil import UTC,tenant_tz
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).astimezone(tenant_tz()).date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_anchor(value) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise AppException("VALIDATION_ERROR", "anchor 必须为 YYYY-MM-DD") from None


def _window(period: str, anchor=None):
    mode = str(period or "ALL").upper()
    if mode not in PERIODS:
        raise AppException("VALIDATION_ERROR", "period 仅支持 WEEK/MONTH/ALL")
    day = _parse_anchor(anchor)
    if mode == "WEEK":
        start = day - timedelta(days=day.weekday())
        return mode, start, start + timedelta(days=6)
    if mode == "MONTH":
        start = date(day.year, day.month, 1)
        end = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
        return mode, start, end
    return mode, None, None


def _overlap(start: date | None, end: date | None, win_start: date | None, win_end: date | None):
    if not start or not end:
        return None
    a = max(start, win_start) if win_start else start
    b = min(end, win_end) if win_end else end
    return (a, b) if a <= b else None


def _date_set(start: date | None, end: date | None):
    if not start or not end or end < start:
        return set()
    return {start + timedelta(days=offset) for offset in range((end - start).days + 1)}


def _month_due_date(year: int, month: int, end: date | None):
    last = date(year, month, calendar.monthrange(year, month)[1])
    return min(last, end) if end and (year, month) == (end.year, end.month) else last


def _month_due_dates(start: date, end: date, required_count: int):
    if not start or not end or end < start or required_count <= 0:
        return []
    values = []
    current = date(start.year, start.month, 1)
    while current <= end:
        due = _month_due_date(current.year, current.month, end)
        if due >= start:
            values.append(due)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return values[:required_count]


def _weekly_due_dates(start: date, end: date, cfg: dict):
    required = max(0, int(cfg.get("requiredCount") or 0))
    if not start or not end or end < start or required <= 0:
        return []
    step = 14 if str(cfg.get("frequency") or "WEEKLY").upper() == "BIWEEKLY" else 7
    weekday = min(7, max(1, int(cfg.get("deadlineWeekday") or 7)))
    monday = start - timedelta(days=start.weekday())
    due = monday + timedelta(days=weekday - 1)
    if due < start:
        due += timedelta(days=step)
    values = []
    while due <= end:
        values.append(due)
        due += timedelta(days=step)
    return values[:required]


def _selected_due(due: date | None, win_start: date | None, win_end: date | None):
    if due is None:
        return win_start is None and win_end is None
    return (win_start is None or due >= win_start) and (win_end is None or due <= win_end)


def _user_view(user: User | None):
    return {
        "name": user.real_name if user else "",
        "employeeNo": user.login_name if user else "",
    }


def _selected_columns(group_by: str, columns: str | list[str] | None):
    allowed = COLUMN_SETS[group_by]
    keys = [item[0] for item in allowed]
    if isinstance(columns, str):
        requested = [item.strip() for item in columns.split(",") if item.strip()]
    elif isinstance(columns, list):
        requested = [str(item).strip() for item in columns if str(item).strip()]
    else:
        requested = []
    if not requested:
        return allowed
    unknown = [key for key in requested if key not in keys]
    if unknown:
        raise AppException("VALIDATION_ERROR", f"存在不支持的统计列：{','.join(unknown[:5])}")
    selected = [item for item in allowed if item[0] in requested]
    if not selected:
        raise AppException("VALIDATION_ERROR", "至少选择一个统计列")
    return selected


def _record_dates(record, batch):
    start = _as_date(record.intern_start_date) or _as_date(batch.start_date)
    end = _as_date(record.intern_end_date) or _as_date(batch.end_date)
    return start, end


def _latest_review_map(reviews):
    out = {}
    for row in reviews:
        key = (str(row.report_kind or "").upper(), int(row.report_id))
        old = out.get(key)
        if old is None or ((row.reviewed_at or datetime.min), int(row.id)) > (
            (old.reviewed_at or datetime.min), int(old.id)
        ):
            out[key] = row
    return out


def _review_matches(review, user_id, user_name):
    if review is None:
        return False
    rid = str(review.reviewer_user_id or "")
    return bool(user_id and rid and rid.removeprefix('db-') == str(user_id).removeprefix('db-'))


def _timely(review, submitted_at, sla_hours: int):
    if not review or not submitted_at or not review.reviewed_at or sla_hours <= 0:
        return None
    return submitted_at <= review.reviewed_at <= submitted_at + timedelta(hours=sla_hours)


def _load_record_facts(db, user, batch, period, anchor, college=None, major=None, class_name=None):
    mode, win_start, win_end = _window(period, anchor)
    pair_query = select(InternshipRecord, StudentProfile).join(
        StudentProfile,
        (StudentProfile.id == InternshipRecord.student_id)
        & (StudentProfile.tenant_id == InternshipRecord.tenant_id),
    ).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == batch.id,
        InternshipRecord.is_deleted.is_(False),
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    )
    pair_query = apply_internship_record_scope(pair_query, user)
    pairs = db.execute(pair_query.order_by(InternshipRecord.id)).all()
    cache = base_stats._preload_org_cache(db,[student for _,student in pairs])
    pairs = [(rec,stu) for rec,stu in pairs if all(not value or value == actual for value,actual in
        zip((college,major,class_name),base_stats._org_of(db,stu,cache)))]
    records = [rec for rec, _stu in pairs]
    students = [stu for _rec, stu in pairs]
    record_ids = [int(rec.id) for rec in records]
    student_ids = [int(stu.id) for stu in students]
    if not record_ids:
        return mode, win_start, win_end, []

    class_ids = {int(stu.class_id) for stu in students if stu.class_id}
    classes = {int(row.id): row for row in db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(class_ids or {0}),
        SchoolClass.is_deleted.is_(False),
    )).all()}
    major_ids = {int(row.major_id) for row in classes.values() if row.major_id}
    major_ids.update(int(stu.major_id) for stu in students if stu.major_id)
    majors = {int(row.id): row for row in db.scalars(select(Major).where(
        Major.tenant_id == _tid(), Major.id.in_(major_ids or {0}), Major.is_deleted.is_(False),
    )).all()}
    college_ids = {int(row.college_id) for row in majors.values() if row.college_id}
    college_ids.update(int(stu.college_id) for stu in students if stu.college_id)
    colleges = {int(row.id): row for row in db.scalars(select(College).where(
        College.tenant_id == _tid(), College.id.in_(college_ids or {0}), College.is_deleted.is_(False),
    )).all()}

    user_ids = {int(rec.advisor_user_id) for rec in records if rec.advisor_user_id}
    user_ids.update(int(cls.head_teacher_id) for cls in classes.values() if cls.head_teacher_id)
    users = {int(row.id): row for row in db.scalars(select(User).where(
        User.tenant_id == _tid(), User.id.in_(user_ids or {0}), User.is_deleted.is_(False),
    )).all()}
    now = datetime.utcnow()
    staff = {}
    assignments = db.scalars(select(StaffAssignment).where(
        StaffAssignment.tenant_id == _tid(), StaffAssignment.user_id.in_(user_ids or {0}),
        StaffAssignment.org_type == 'COLLEGE', StaffAssignment.is_deleted.is_(False),
        StaffAssignment.status == 'ACTIVE', StaffAssignment.effective_at <= now,
        or_(StaffAssignment.expires_at.is_(None), StaffAssignment.expires_at > now))
        .order_by(StaffAssignment.is_primary.desc(), StaffAssignment.effective_at.desc(), StaffAssignment.id.desc())).all()
    for assignment in assignments:
        staff.setdefault(assignment.user_id, assignment.org_node_id)
    staff_orgs = {row.id: row.college_name for row in db.scalars(select(College).where(
        College.tenant_id == _tid(), College.is_deleted.is_(False), College.id.in_(set(staff.values()) or {0}))).all()}

    bound_students = set()
    if student_ids:
        bound_students = {int(value) for value in db.scalars(select(StudentAccountLink.student_id).where(
            StudentAccountLink.tenant_id == _tid(),
            StudentAccountLink.student_id.in_(student_ids),
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
        )).all()}

    checkins = db.scalars(select(InternshipCheckin).where(
        InternshipCheckin.tenant_id == _tid(),
        InternshipCheckin.internship_id.in_(record_ids),
        InternshipCheckin.result.in_(("NORMAL", "RECORDED")),
        InternshipCheckin.is_deleted.is_(False),
    )).all()
    leaves = db.scalars(select(InternshipLeave).where(
        InternshipLeave.tenant_id == _tid(),
        InternshipLeave.internship_id.in_(record_ids),
        InternshipLeave.status.in_(('APPROVED', 'OVERDUE', 'RETURNED')),
        InternshipLeave.is_deleted.is_(False),
    )).all()
    exemptions = db.scalars(select(InternshipCheckinExemption).where(
        InternshipCheckinExemption.tenant_id == _tid(),
        InternshipCheckinExemption.internship_id.in_(record_ids),
        InternshipCheckinExemption.status == "APPROVED",
        InternshipCheckinExemption.is_deleted.is_(False),
    )).all()
    makeups = db.scalars(select(InternshipMakeup).where(
        InternshipMakeup.tenant_id == _tid(),
        InternshipMakeup.internship_id.in_(record_ids),
        InternshipMakeup.status == "APPROVED",
        InternshipMakeup.is_deleted.is_(False),
    )).all()
    weekly = db.scalars(select(WeeklyReport).where(
        WeeklyReport.tenant_id == _tid(), WeeklyReport.internship_id.in_(record_ids),
        WeeklyReport.is_deleted.is_(False),
        WeeklyReport.status.in_(SUBMITTED_REPORT_STATUSES),
    )).all()
    process = db.scalars(select(InternshipProcessReport).where(
        InternshipProcessReport.tenant_id == _tid(),
        InternshipProcessReport.internship_id.in_(record_ids),
        InternshipProcessReport.is_deleted.is_(False),
        InternshipProcessReport.status.in_(SUBMITTED_REPORT_STATUSES),
    )).all()
    scores = db.scalars(select(InternshipFinalScore).where(
        InternshipFinalScore.tenant_id == _tid(),
        InternshipFinalScore.internship_id.in_(record_ids),
        InternshipFinalScore.status == "PUBLISHED",
        InternshipFinalScore.is_deleted.is_(False),
    )).all()
    changes = db.scalars(select(InternshipChangeRequest).where(
        InternshipChangeRequest.tenant_id == _tid(),
        InternshipChangeRequest.internship_id.in_(record_ids),
        InternshipChangeRequest.status == "APPROVED",
        InternshipChangeRequest.change_type.in_(("CHANGE_POSITION","CHANGE_ENTERPRISE","SELF_ARRANGED")),
        InternshipChangeRequest.is_deleted.is_(False),
    )).all()

    snapshots = {
        **{("WEEKLY", key): value for key, value in latest_snapshot_map(db,"WEEKLY",[row.id for row in weekly]).items()},
        **{("PROCESS", key): value for key, value in latest_snapshot_map(db,"PROCESS",[row.id for row in process]).items()},
    }
    snapshot_ids = [row.id for row in snapshots.values()]
    reviews = []
    if snapshot_ids:
        reviews = db.scalars(select(InternshipReportReview).where(
            InternshipReportReview.tenant_id == _tid(),
            InternshipReportReview.report_version_id.in_(snapshot_ids),
        )).all()
    reviews = [row for row in reviews if (row.report_kind, row.report_id) in snapshots
        and snapshots[(row.report_kind,row.report_id)].id == row.report_version_id]
    review_map = _latest_review_map(reviews)

    application_facts = base_stats._latest_approved_application_facts(db, record_ids)

    by_rec = lambda rows: defaultdict(list)
    checkin_map, leave_map, exemption_map, makeup_map = map(lambda _x: defaultdict(list), range(4))
    weekly_map, process_map, score_map, change_map = map(lambda _x: defaultdict(list), range(4))
    for row in checkins: checkin_map[int(row.internship_id)].append(row)
    for row in leaves: leave_map[int(row.internship_id)].append(row)
    for row in exemptions: exemption_map[int(row.internship_id)].append(row)
    for row in makeups: makeup_map[int(row.internship_id)].append(row)
    for row in weekly: weekly_map[int(row.internship_id)].append(row)
    for row in process: process_map[int(row.internship_id)].append(row)
    for row in scores: score_map[int(row.internship_id)].append(row)
    for row in changes: change_map[int(row.internship_id)].append(row)

    weekly_cfg = dict((batch.rules_config or {}).get("weeklyReport") or {})
    process_cfg = dict((batch.rules_config or {}).get("processReport") or {})
    report_counts = required_report_counts(batch)
    weekly_cfg["requiredCount"] = report_counts["weeklyRequiredCount"]
    checkin_cfg = dict((batch.rules_config or {}).get("checkin") or {})
    weekly_sla = max(0, int(weekly_cfg.get("reviewSlaHours") if weekly_cfg.get("reviewSlaHours") is not None else 48))
    process_sla = max(0, int(process_cfg.get("reviewSlaHours") if process_cfg.get("reviewSlaHours") is not None else 48))
    today = local_now().date()
    facts = []

    for rec, stu in pairs:
        rid = int(rec.id)
        cls = classes.get(int(stu.class_id)) if stu.class_id else None
        major = majors.get(int(stu.major_id)) if stu.major_id else None
        if not major and cls and cls.major_id:
            major = majors.get(int(cls.major_id))
        college = colleges.get(int(stu.college_id)) if stu.college_id else None
        if not college and major and major.college_id:
            college = colleges.get(int(major.college_id))
        advisor_user = users.get(int(rec.advisor_user_id)) if rec.advisor_user_id else None
        head_user = users.get(int(cls.head_teacher_id)) if cls and cls.head_teacher_id else None
        start, end = _record_dates(rec, batch)
        visible_end = min(end, today) if end else None
        active = _overlap(start, visible_end, win_start, win_end)

        leave_days = set()
        for row in leave_map[rid]:
            value = _overlap(*effective_period(row), win_start, win_end)
            if value:
                leave_days |= _date_set(*value)
        exempt_days = set()
        for row in exemption_map[rid]:
            value = _overlap(_as_date(row.start_date), _as_date(row.end_date), win_start, win_end)
            if value:
                exempt_days |= _date_set(*value)
        makeup_days = {
            d for row in makeup_map[rid] for d in [_as_date(row.checkin_date)]
            if d and (win_start is None or d >= win_start) and (win_end is None or d <= win_end)
        }
        checkin_days = {
            d for row in checkin_map[rid] for d in [_as_date(row.checkin_date)]
            if d and (win_start is None or d >= win_start) and (win_end is None or d <= win_end)
        }
        expected_days = _date_set(*active) if active and checkin_cfg.get("requireDaily", True) else set()
        expected_days -= leave_days
        expected_days -= exempt_days
        valid_days = _date_set(*active) if active else set()
        actual_days = (checkin_days | makeup_days) & valid_days

        weekly_dues = _weekly_due_dates(start, end, weekly_cfg)
        selected_weekly_dues = [due for due in weekly_dues if _selected_due(due, win_start, win_end)]
        weekly_expected = (
            report_counts["weeklyRequiredCount"] if mode == "ALL"
            else len(selected_weekly_dues)
        )
        selected_weekly = []
        weekly_late = 0
        weekly_reviewed = 0
        weekly_timely = 0
        advisor_weekly_reviewed = 0
        advisor_weekly_timely = 0
        weekly_timing_known = advisor_weekly_timing_known = True
        for row in weekly_map[rid]:
            current_snapshot=snapshots.get(('WEEKLY',row.id))
            submitted_at=current_snapshot.submitted_at if current_snapshot else row.submitted_at
            index = max(0, int(row.week_number or 1) - 1)
            due = weekly_dues[index] if index < len(weekly_dues) else _as_date(submitted_at)
            if not _selected_due(due, win_start, win_end):
                continue
            selected_weekly.append(row)
            if due and _as_date(submitted_at) and _as_date(submitted_at) > due:
                weekly_late += 1
            review = review_map.get(("WEEKLY", int(row.id)))
            legacy_reviewed = not current_snapshot and row.status in {"APPROVED","RETURNED"}
            if review or legacy_reviewed:
                weekly_reviewed += 1
                timely = _timely(review, submitted_at, weekly_sla) if review else (
                    submitted_at <= row.reviewed_at <= submitted_at + timedelta(hours=weekly_sla)
                    if weekly_sla > 0 and row.reviewed_at and submitted_at else None
                )
                if timely is None:weekly_timing_known=False
                if timely is True:
                    weekly_timely += 1
                if _review_matches(review, rec.advisor_user_id, rec.advisor_name):
                    if timely is None:advisor_weekly_timing_known=False
                    advisor_weekly_reviewed += 1
                    if timely is True:
                        advisor_weekly_timely += 1

        monthly_required = report_counts["monthlyRequiredCount"]
        month_dues = _month_due_dates(start, end, monthly_required)
        selected_month_dues = [due for due in month_dues if _selected_due(due, win_start, win_end)]
        monthly_expected = monthly_required if mode == "ALL" else len(selected_month_dues)
        summary_required = report_counts["summaryRequiredCount"]
        summary_due = end if summary_required else None
        summary_expected = summary_required if mode == "ALL" else (
            1 if summary_due and _selected_due(summary_due, win_start, win_end) else 0
        )

        daily_rows, monthly_rows, summary_rows = [], [], []
        monthly_reviewed = monthly_timely = summary_reviewed = 0
        advisor_monthly_reviewed = advisor_monthly_timely = advisor_summary_reviewed = 0
        monthly_timing_known = advisor_monthly_timing_known = True
        for row in process_map[rid]:
            current_snapshot=snapshots.get(('PROCESS',row.id))
            submitted_at=current_snapshot.submitted_at if current_snapshot else row.submitted_at
            rt = str(row.report_type or "").upper()
            if rt == "DAILY":
                due = _as_date(row.period_key) or _as_date(submitted_at)
            elif rt == "MONTHLY":
                try:
                    y, m = [int(x) for x in str(row.period_key).split("-", 1)]
                    due = _month_due_date(y, m, end)
                except Exception:
                    due = _as_date(submitted_at)
            else:
                due = summary_due or _as_date(submitted_at)
            if not _selected_due(due, win_start, win_end):
                continue
            if rt == "DAILY":
                daily_rows.append(row)
                continue
            review = review_map.get(("PROCESS", int(row.id)))
            legacy_reviewed = not current_snapshot and row.status in {"APPROVED","RETURNED"}
            timely = _timely(review, submitted_at, process_sla) if review else (
                submitted_at <= row.reviewed_at <= submitted_at + timedelta(hours=process_sla)
                if process_sla > 0 and row.reviewed_at and submitted_at else None
            )
            advisor_match = _review_matches(review, rec.advisor_user_id, rec.advisor_name)
            if rt == "MONTHLY":
                monthly_rows.append(row)
                if review or legacy_reviewed:
                    monthly_reviewed += 1
                    if timely is None:monthly_timing_known=False
                    if timely is True: monthly_timely += 1
                    if advisor_match:
                        if timely is None:advisor_monthly_timing_known=False
                        advisor_monthly_reviewed += 1
                        if timely is True: advisor_monthly_timely += 1
            elif rt == "SUMMARY":
                summary_rows.append(row)
                if review or legacy_reviewed:
                    summary_reviewed += 1
                    if advisor_match: advisor_summary_reviewed += 1

        score_rows = sorted(
            score_map[rid],
            key=lambda row: ((row.updated_at or row.created_at or datetime.min), int(row.id)),
            reverse=True,
        )
        total_score = float(score_rows[0].total_score) if score_rows and score_rows[0].total_score is not None else None

        enterprises = set()
        if rec.enterprise_id or rec.enterprise_name:
            enterprises.add(str(rec.enterprise_id or rec.enterprise_name))
        for row in change_map[rid]:
            if row.target_enterprise_id or row.target_enterprise_name:
                enterprises.add(str(row.target_enterprise_id or row.target_enterprise_name))

        app = application_facts.get(rid)
        facts.append({
            "rowKey": f"STUDENT:{rid}",
            "recordId": rid,
            "studentId": int(stu.id),
            "studentName": stu.real_name or "",
            "studentNo": stu.student_no or "",
            "grade": stu.grade or (cls.grade if cls else "") or "",
            "batchName": batch.batch_name or "",
            "collegeId": int(college.id) if college else None,
            "college": college.college_name if college else "",
            "majorId": int(major.id) if major else None,
            "major": major.major_name if major else "",
            "classId": int(cls.id) if cls else None,
            "className": cls.class_name if cls else "",
            "advisorUserId": int(rec.advisor_user_id) if rec.advisor_user_id else None,
            "advisorName": (advisor_user.real_name if advisor_user else rec.advisor_name) or "",
            "advisorEmployeeNo": users[rec.advisor_user_id].login_name if rec.advisor_user_id in users else "",
            "advisorCollege": staff_orgs.get(staff.get(rec.advisor_user_id),''),
            "headTeacherId": int(cls.head_teacher_id) if cls and cls.head_teacher_id else None,
            "headTeacherName": head_user.real_name if head_user else "",
            "headTeacherEmployeeNo": head_user.login_name if head_user else "",
            "headTeacherCollege": staff_orgs.get(staff.get(head_user.id),'') if head_user else '',
            "enterpriseCount": len(enterprises),
            "bound": 1 if int(stu.id) in bound_students else 0,
            "expectedCheckins": len(expected_days),
            "actualCheckins": len(actual_days & expected_days) if expected_days else len(actual_days),
            "leaveDays": len(leave_days),
            "exemptDays": len(exempt_days),
            "makeupDays": len(makeup_days),
            "dailySubmitted": len(daily_rows),
            "weeklyExpected": weekly_expected,
            "weeklySubmitted": len(selected_weekly),
            "weeklyLate": weekly_late,
            "weeklyReviewed": weekly_reviewed,
            "weeklyTimelyReviewed": weekly_timely,
            "advisorWeeklyReviewed": advisor_weekly_reviewed,
            "advisorWeeklyTimelyReviewed": advisor_weekly_timely,
            "weeklySlaConfigured": weekly_sla > 0,
            "processSlaConfigured": process_sla > 0,
            "weeklyTimingKnown":weekly_timing_known,"advisorWeeklyTimingKnown":advisor_weekly_timing_known,
            "monthlyTimingKnown":monthly_timing_known,"advisorMonthlyTimingKnown":advisor_monthly_timing_known,
            "monthlyExpected": monthly_expected,
            "monthlySubmitted": len(monthly_rows),
            "monthlyReviewed": monthly_reviewed,
            "monthlyTimelyReviewed": monthly_timely,
            "advisorMonthlyReviewed": advisor_monthly_reviewed,
            "advisorMonthlyTimelyReviewed": advisor_monthly_timely,
            "summaryExpected": summary_expected,
            "summarySubmitted": len(summary_rows),
            "summaryReviewed": summary_reviewed,
            "advisorSummaryReviewed": advisor_summary_reviewed,
            "totalScore": total_score,
            "internshipStudent": 1 if rec.destination_type != "NONE" else 0,
            "exemptInternship": 1 if rec.destination_type == "EXEMPTED" else 0,
            "onboard": 1 if rec.status in {"ONBOARD", "ASSESSING", "ARCHIVED"} else 0,
            "majorMatchKnown": 1 if app is not None and app.major_match is not None else 0,
            "majorMatched": 1 if app is not None and app.major_match is True else 0,
            "changed": 1 if change_map[rid] else 0,
        })
    return mode, win_start, win_end, facts


def _student_rows(facts):
    rows = []
    for fact in facts:
        row = dict(fact)
        row["weeklyCompletionRate"] = _ratio(
            min(fact["weeklySubmitted"], fact["weeklyExpected"]), fact["weeklyExpected"]
        )
        rows.append(row)
    return rows


def _aggregate(facts, group_by, batch_name):
    groups = defaultdict(list)
    for fact in facts:
        if group_by == "ADVISOR":
            key = ("A", fact["advisorUserId"] or 0, fact["advisorName"] or "未分配指导老师")
        elif group_by == "HOMEROOM":
            key = ("H", fact["headTeacherId"] or 0, fact["classId"] or 0)
        elif group_by == "COLLEGE":
            key = ("C", fact["collegeId"] or 0)
        elif group_by == "MAJOR":
            key = ("M", fact["majorId"] or 0)
        else:
            key = ("L", fact["classId"] or 0)
        groups[key].append(fact)

    rows = []
    for key, items in groups.items():
        first = items[0]
        n = len(items)
        expected_checkins = sum(x["expectedCheckins"] for x in items)
        actual_checkins = sum(x["actualCheckins"] for x in items)
        weekly_expected = sum(x["weeklyExpected"] for x in items)
        weekly_submitted = sum(x["weeklySubmitted"] for x in items)
        weekly_completed = sum(min(x["weeklySubmitted"], x["weeklyExpected"]) for x in items)
        monthly_expected = sum(x["monthlyExpected"] for x in items)
        monthly_submitted = sum(x["monthlySubmitted"] for x in items)
        monthly_completed = sum(min(x["monthlySubmitted"], x["monthlyExpected"]) for x in items)

        if group_by in {"ADVISOR", "HOMEROOM"}:
            if group_by == "ADVISOR":
                reviewed = sum(x["advisorWeeklyReviewed"] for x in items)
                timely = sum(x["advisorWeeklyTimelyReviewed"] for x in items)
                month_reviewed = sum(x["advisorMonthlyReviewed"] for x in items)
                month_timely = sum(x["advisorMonthlyTimelyReviewed"] for x in items)
                summary_reviewed = sum(x["advisorSummaryReviewed"] for x in items)
                name = first["advisorName"] or "未分配指导老师"
                employee_no = first["advisorEmployeeNo"]
                class_name = ""
            else:
                reviewed = sum(x["weeklyReviewed"] for x in items)
                timely = sum(x["weeklyTimelyReviewed"] for x in items)
                month_reviewed = sum(x["monthlyReviewed"] for x in items)
                month_timely = sum(x["monthlyTimelyReviewed"] for x in items)
                summary_reviewed = sum(x["summaryReviewed"] for x in items)
                name = first["headTeacherName"] or "未配置班主任"
                employee_no = first["headTeacherEmployeeNo"]
                class_name = first["className"]
            rows.append({
                "rowKey": ":".join(str(v) for v in key),
                "name": name,
                "employeeNo": employee_no,
                "college": first['advisorCollege'] if group_by=='ADVISOR' else first['headTeacherCollege'],
                "className": class_name,
                "internshipType": batch_name,
                "studentCount": n,
                "boundCount": sum(x["bound"] for x in items),
                "checkinCount": actual_checkins,
                "averageCheckins": round(actual_checkins / n, 2) if n else 0,
                "averageCheckinRate": _ratio(actual_checkins, expected_checkins),
                "dailyCount": sum(x["dailySubmitted"] for x in items),
                "weeklyExpected": weekly_expected,
                "weeklySubmitted": weekly_submitted,
                "weeklyMissing": weekly_expected - weekly_completed,
                "weeklyCompletionRate": _ratio(weekly_completed, weekly_expected),
                "weeklyReviewed": reviewed,
                "weeklyReviewRate": _ratio(reviewed, weekly_submitted),
                "weeklyTimelyReviewRate": _ratio(timely, reviewed) if all(x["weeklySlaConfigured"] and x['advisorWeeklyTimingKnown' if group_by=='ADVISOR' else 'weeklyTimingKnown'] for x in items) else None,
                "monthlySubmitted": monthly_submitted,
                "monthlyCompletionRate": _ratio(monthly_completed, monthly_expected),
                "monthlyReviewRate": _ratio(month_reviewed, monthly_submitted),
                "monthlyTimelyReviewRate": _ratio(month_timely, month_reviewed) if all(x["processSlaConfigured"] and x['advisorMonthlyTimingKnown' if group_by=='ADVISOR' else 'monthlyTimingKnown'] for x in items) else None,
                "summarySubmitted": sum(x["summarySubmitted"] for x in items),
                "summaryReviewRate": _ratio(
                    summary_reviewed, sum(x["summarySubmitted"] for x in items)
                ),
            })
            continue

        major_known = sum(x["majorMatchKnown"] for x in items)
        major_yes = sum(x["majorMatched"] for x in items)
        weekly_reviewed = sum(x["weeklyReviewed"] for x in items)
        monthly_reviewed = sum(x["monthlyReviewed"] for x in items)
        rows.append({
            "rowKey": ":".join(str(v) for v in key),
            "college": first["college"],
            "grades": "、".join(sorted({x["grade"] for x in items if x["grade"]})),
            "major": first["major"] if group_by in {"MAJOR", "CLASS"} else "",
            "className": first["className"] if group_by == "CLASS" else "",
            "headTeacherName": first["headTeacherName"] if group_by == "CLASS" else "",
            "studentCount": n,
            "internshipStudentCount": sum(x["internshipStudent"] for x in items),
            "boundCount": sum(x["bound"] for x in items),
            "bindingRate": _ratio(sum(x["bound"] for x in items), n),
            "exemptInternshipCount": sum(x["exemptInternship"] for x in items),
            "onboardCount": sum(x["onboard"] for x in items),
            "onboardRate": _ratio(sum(x["onboard"] for x in items), n),
            "majorMatchRate": _ratio(major_yes, major_known),
            "stabilityRate": _ratio(n - sum(x["changed"] for x in items), n),
            "averageCheckins": round(actual_checkins / n, 2) if n else 0,
            "checkinRate": _ratio(actual_checkins, expected_checkins),
            "dailyCount": sum(x["dailySubmitted"] for x in items),
            "weeklyExpected": weekly_expected,
            "weeklySubmitted": weekly_submitted,
            "weeklyCompletionRate": _ratio(weekly_completed, weekly_expected),
            "weeklyReviewed": weekly_reviewed,
            "weeklyReviewRate": _ratio(weekly_reviewed, weekly_submitted),
            "monthlySubmitted": monthly_submitted,
            "monthlyCompletionRate": _ratio(monthly_completed, monthly_expected),
            "monthlyReviewed": monthly_reviewed,
            "monthlyReviewRate": _ratio(monthly_reviewed, monthly_submitted),
            "summarySubmitted": sum(x["summarySubmitted"] for x in items),
        })
    return rows


def query(user, *, batch_id, group_by="STUDENT", period="ALL", anchor=None,
          columns=None, page=1, page_size=50, college=None, major=None, class_name=None, _export=False):
    group = str(group_by or "STUDENT").upper()
    if group not in GROUPS:
        raise AppException("VALIDATION_ERROR", "groupBy 仅支持 STUDENT/ADVISOR/HOMEROOM/COLLEGE/MAJOR/CLASS")
    selected = _selected_columns(group, columns)
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        mode, win_start, win_end, facts = _load_record_facts(
            db, user, batch, period, anchor, college, major, class_name
        )
        rows = _student_rows(facts) if group == "STUDENT" else _aggregate(
            facts, group, batch.batch_name or ""
        )
    rows.sort(key=lambda row: row['rowKey'])
    total = len(rows)
    if _export:
        from app.modules.internship.services.internship_export_util import require_exportable
        require_exportable(total)
    page_value = max(1, int(page or 1))
    page_size_value = min(500, max(1, int(page_size or 50)))
    if _export:page_size_value=max(1,total)
    start = (page_value - 1) * page_size_value
    visible = rows[start:start + page_size_value]
    return {
        "schemaVersion": "YIYANG_AP19_AP24_V1",
        "batchId": str(batch.id),
        "batchName": batch.batch_name or "",
        "groupBy": group,
        "period": mode,
        "anchor": _parse_anchor(anchor).isoformat(),
        "windowStart": win_start.isoformat() if win_start else "",
        "windowEnd": win_end.isoformat() if win_end else "",
        "availableColumns": [{"key": key, "title": title} for key, title in COLUMN_SETS[group]],
        "selectedColumns": [{"key": key, "title": title} for key, title in selected],
        "items": [
            {"rowKey": row["rowKey"], **{key: row.get(key) for key, _title in selected}}
            for row in visible
        ],
        "total": total,
        "page": page_value,
        "pageSize": page_size_value,
        "definitions": {
            "binding": "只统计有效学生账号绑定；缺绑定不按已绑定计算。",
            "checkin": "按实习有效日期扣除已批准请假/免签；补签与正式签到按日期去重。",
            "stability": "本批次无已批准换岗、换单位或转自主实习变更的实习记录，占本批次记录的比例。",
            "majorMatch": "仅已批准申请中明确登记专业是否对口的记录进入分母；未知不默认对口或不对口。",
            "weeklyExpected": "全部期间与报告台账共用批次应交篇数；0或缺失表示未配置。周/月筛选按任务到期日归属，缺实习日期不生成到期任务。",
            "timelyReview": "按批次规定的批阅时限计算，未配置时默认48小时；明确为0不计算准时率。缺少提交或批阅时点的历史资料不冒充逾期，该组准时率暂不计算。仅当前提交版本的批阅计入，指导教师本人工作量按稳定账号归属，不凭同名计算。",
            "homeroomPerformance": "班主任统计反映所辖班级的学生报告批阅进度，包含指导教师等有权人的批阅；不当作班主任本人批阅次数。本人工作量以批阅留痕的稳定账号为准。",
            "reportCompletion": "按每人实交与应交的较小值计算完成率，多交不抵他人缺交；批阅率针对当前提交版，历史批阅工作量见教师工作台账。零分母不计算完成率。",
            "customColumns": "屏幕与 Excel 共用同一列白名单和同一统计条件。",
        },
    }


def export(user, *, batch_id, group_by="STUDENT", period="ALL", anchor=None, columns=None, college=None, major=None, class_name=None):
    data = query(
        user, batch_id=batch_id, group_by=group_by, period=period, anchor=anchor,
        columns=columns, page=1, page_size=500, college=college, major=major, class_name=class_name, _export=True,
    )
    selected = data["selectedColumns"]
    headers = [item["title"] for item in selected]
    rows = [[row.get(item["key"]) for item in selected] for row in data["items"]]
    group_label = {
        "STUDENT": "实习生过程统计", "ADVISOR": "指导老师绩效统计",
        "HOMEROOM": "班主任绩效统计", "COLLEGE": "院系实习情况汇总",
        "MAJOR": "专业实习情况汇总", "CLASS": "班级实习情况汇总",
    }[data["groupBy"]]
    period_label={'ALL':'全部时间','WEEK':'按周','MONTH':'按月'}[data['period']]
    content = xlsx_util.build_ledger_xlsx(
        group_label, headers, rows,
        watermark=f"跃科岗位实习管理平台 · {group_label} · {period_label} · {datetime.now():%Y-%m-%d %H:%M}",
    )
    base_stats._record_export(user,group_label,len(rows),dict(batchId=str(batch_id),groupBy=group_by,
        period=period,anchor=anchor,columns=columns,college=college,major=major,className=class_name),
        ['studentName','studentNo'] if group_by=='STUDENT' else ['name','employeeNo'] if group_by in {'ADVISOR','HOMEROOM'} else None)
    return xlsx_util.pack_xlsx_result(
        content, f"{group_label}_{period_label}.xlsx", len(rows)
    )
