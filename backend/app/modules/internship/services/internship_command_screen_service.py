"""Additive, read-only aggregates for the internship wall; no tables, writes, or alternate authority.

All queries start from the same tenant + explicit batch + active student + existing SQL role scope.
Return bounded aggregates only. Existing business rates remain supplied by stats/overview.
"""
from __future__ import annotations

from datetime import timedelta
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import aliased

from app.core.exceptions import no_permission
from app.core.timeutil import UTC, local_day_bounds_utc, local_now
from app.models import (AttendanceException, EmpCompany, EmpStudent, InternshipRecord,
                        InternshipCheckin, InternshipVisit, Major, RiskRecord,
                        SchoolClass, StudentProfile)
from app.modules.internship.services.internship_batch_context import batch_public_fields, resolve_batch
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.modules.internship.services.internship_command_screen_rules import REGIONS, month_keys
from app.services.db_service import _tid, session

CONTRACT_VERSION = "ix-command-screen-1"


def _visible_records(user, batch_id):
    """Return a SQL selectable, never a Python list of every student."""
    from app.modules.internship.services.internship_student_service import _current_scope
    scope = _current_scope(user)
    if scope.get("mode") not in {"ADMIN_TENANT", "SCOPED"}:
        raise no_permission("无法确认实习数据范围")
    query = select(
        InternshipRecord.id, InternshipRecord.student_id, InternshipRecord.status,
        InternshipRecord.enterprise_id, InternshipRecord.position_id,
        InternshipRecord.advisor_user_id, InternshipRecord.mentor_contact_id,
    ).join(StudentProfile, and_(
        StudentProfile.id == InternshipRecord.student_id,
        StudentProfile.tenant_id == InternshipRecord.tenant_id,
        StudentProfile.is_deleted.is_(False),
    )).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == batch_id,
        InternshipRecord.is_deleted.is_(False),
    )
    return apply_internship_record_scope(query, user).subquery("ix_wall_scope"), scope


def _live(model):
    return (model.tenant_id == _tid(), model.is_deleted.is_(False))


def _region_expr():
    # region is the explicit company province/region; city only handles four municipalities.
    raw = func.trim(func.coalesce(EmpCompany.region, ""))
    municipality = case(*[(func.trim(EmpCompany.city).like(short + "%"), short)
                          for _, short, _ in REGIONS if short in {"北京", "上海", "天津", "重庆"}], else_="")
    source = case((raw != "", raw), else_=municipality)
    return case(*[(source.like(prefix + "%"), code)
                  for code, short, full in REGIONS for prefix in (code, full, short)], else_="UNKNOWN")


def _risk_daily_query(ids, days, now_utc):
    predicates = []
    for day in days:
        begin, end = local_day_bounds_utc(day)
        predicates.append(func.sum(case((and_(RiskRecord.created_at >= begin,
                                               RiskRecord.created_at < min(end, now_utc)), 1), else_=0)))
    return select(*predicates).where(*_live(RiskRecord), RiskRecord.internship_id.in_(ids),
                                    RiskRecord.created_at >= local_day_bounds_utc(days[0])[0],
                                    RiskRecord.created_at < now_utc)


def overview(user, batch_id):
    now = local_now()
    now_utc = now.astimezone(UTC).replace(tzinfo=None)
    days = [now.date() - timedelta(days=i) for i in range(6, -1, -1)]
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        scoped, scope = _visible_records(user, batch.id)
        ids = select(scoped.c.id)
        company_join = and_(EmpCompany.id == scoped.c.enterprise_id,
                            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False))
        totals_row = db.execute(select(
            func.count(scoped.c.id), func.count(func.distinct(EmpCompany.id)),
            func.count(func.distinct(scoped.c.position_id)),
            func.count(func.distinct(scoped.c.advisor_user_id)),
            func.count(func.distinct(scoped.c.mentor_contact_id)),
        ).select_from(scoped).outerjoin(EmpCompany, company_join)).one()
        totals = dict(zip(("students", "enterprises", "positions", "schoolMentors", "enterpriseMentors"),
                          [int(v or 0) for v in totals_row]))
        # Linked mentor IDs are counted separately by identity domain, not by names and not as unioned persons.
        totals["pendingExceptions"] = int(db.scalar(select(func.count()).select_from(AttendanceException).where(
            *_live(AttendanceException), AttendanceException.internship_id.in_(ids),
            AttendanceException.status == "PENDING_HANDLE")) or 0)
        totals["visits7d"] = int(db.scalar(select(func.count()).select_from(InternshipVisit).where(
            *_live(InternshipVisit), InternshipVisit.internship_id.in_(ids),
            InternshipVisit.visit_at >= local_day_bounds_utc(days[0])[0],
            InternshipVisit.visit_at < now_utc)) or 0)

        region = _region_expr()
        grouped = db.execute(select(region.label("region_code"), func.count(scoped.c.id),
                                    func.count(func.distinct(EmpCompany.id))).select_from(scoped)
                             .outerjoin(EmpCompany, company_join).group_by(region).limit(35)).all()
        names = {code: full for code, _, full in REGIONS}
        regions, unlocated_students, unlocated_enterprises = [], 0, 0
        for code, students, enterprises in grouped:
            if code == "UNKNOWN":
                unlocated_students, unlocated_enterprises = int(students), int(enterprises)
            else:
                regions.append({"code": code, "name": names[code], "students": int(students),
                                "enterprises": int(enterprises)})
        regions.sort(key=lambda row: (-row["students"], row["code"]))

        direct_major, class_major = aliased(Major), aliased(Major)
        major_name = func.coalesce(direct_major.major_name, class_major.major_name, "未归属专业")
        major_id = func.coalesce(direct_major.id, class_major.id, 0)
        major_count = func.count(scoped.c.id)
        major_rows = db.execute(select(major_name, major_count,
                                      func.count(func.distinct(EmpCompany.id)))
            .select_from(scoped)
            .join(StudentProfile, and_(StudentProfile.id == scoped.c.student_id, *_live(StudentProfile)))
            .outerjoin(SchoolClass, and_(SchoolClass.id == StudentProfile.class_id, *_live(SchoolClass)))
            .outerjoin(direct_major, and_(direct_major.id == StudentProfile.major_id,
                                         direct_major.tenant_id == _tid(), direct_major.is_deleted.is_(False)))
            .outerjoin(class_major, and_(class_major.id == SchoolClass.major_id,
                                        class_major.tenant_id == _tid(), class_major.is_deleted.is_(False)))
            .outerjoin(EmpCompany, company_join)
            .group_by(major_id, major_name).order_by(major_count.desc(), major_id.asc()).limit(8)).all()
        majors = [{"name": name, "students": int(students), "enterprises": int(enterprises)}
                  for name, students, enterprises in major_rows]

        level = case((RiskRecord.risk_level.in_(["HIGH", "MEDIUM", "LOW"]), RiskRecord.risk_level), else_="UNKNOWN")
        risk_rows = db.execute(select(level, func.count()).select_from(RiskRecord).where(
            *_live(RiskRecord), RiskRecord.internship_id.in_(ids),
            RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"])).group_by(level).limit(4)).all()
        risk_counts = {key: int(value) for key, value in risk_rows}
        risk_levels = [{"key": key, "value": risk_counts.get(key, 0)} for key in ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]]
        totals["openRisks"] = sum(row["value"] for row in risk_levels)
        risk_daily_counts = db.execute(_risk_daily_query(ids, days, now_utc)).one()
        risk_daily = [{"date": day.isoformat(), "value": int(value or 0)} for day, value in zip(days, risk_daily_counts)]

        attendance = db.execute(select(InternshipCheckin.checkin_date, func.count(), func.sum(case(
            (InternshipCheckin.result.in_(["NORMAL", "RECORDED", "LEAVE"]), 1), else_=0)))
            .where(*_live(InternshipCheckin), InternshipCheckin.internship_id.in_(ids),
                   InternshipCheckin.checkin_date.in_([day.isoformat() for day in days]),
                   InternshipCheckin.checkin_at < now_utc)
            .group_by(InternshipCheckin.checkin_date).limit(7)).all()
        attendance_by_day = {str(day): (int(value), int(compliant)) for day, value, compliant in attendance}
        attendance_daily = [{"date": day.isoformat(), "value": attendance_by_day.get(day.isoformat(), (0, 0))[0],
                             "compliant": attendance_by_day.get(day.isoformat(), (0, 0))[1]} for day in days]

        # Signature-month distribution of latest ACTIVE verified SIGNED rows; never a reconstructed historical rate.
        months = month_keys(now.date())
        cohort_students = select(scoped.c.student_id).where(scoped.c.status.in_(["ASSESSING", "ARCHIVED"]))
        latest = select(func.max(EmpStudent.id)).where(*_live(EmpStudent),
            EmpStudent.student_id.in_(cohort_students), EmpStudent.record_status == "ACTIVE").group_by(EmpStudent.student_id)
        month = func.substr(EmpStudent.sign_date, 1, 7)
        employment = db.execute(select(month, func.count(func.distinct(EmpStudent.student_id)))
            .where(*_live(EmpStudent), EmpStudent.id.in_(latest), EmpStudent.verify_status == "VERIFIED",
                   EmpStudent.destination_type == "SIGNED", func.length(EmpStudent.sign_date) == 10,
                   EmpStudent.sign_date.op("REGEXP")(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"),
                   EmpStudent.sign_date <= now.date().isoformat(), month.in_(months))
            .group_by(month).limit(6)).all()
        employment_values = {key: int(value) for key, value in employment}
        quality = []
        if unlocated_students:
            quality.append(f"{unlocated_students}条实习记录没有可识别的企业省域，单独计入未定位，不猜测坐标")
        return {
            "contractVersion": CONTRACT_VERSION, **batch_public_fields(batch),
            "snapshotAt": now.isoformat(timespec="seconds"), "timezone": str(now.tzinfo),
            "scopeMode": scope["mode"], "totals": totals, "regions": regions, "majors": majors,
            "geography": {"unlocatedStudents": unlocated_students, "unlocatedEnterprises": unlocated_enterprises,
                          "basis": "企业主档省域字段；非学生实时定位"},
            "riskLevels": risk_levels, "riskNewDaily": risk_daily, "attendanceDaily": attendance_daily,
            "employmentMonths": [{"month": key, "value": employment_values.get(key, 0)} for key in months],
            "quality": quality,
        }
