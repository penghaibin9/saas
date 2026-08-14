"""教务统计总览的大校规模 SQL 聚合安全层。

不改变任何统计 DTO、口径字段或路由，只把原 legacy 总览中“为求 count/rate 先把整列明细
materialize 到 Python”的纯聚合函数替换成数据库聚合。public stats、canonical drilldown、XLSX
入口均保持原 owner；本模块不写业务事实。
"""
from __future__ import annotations

from sqlalchemy import case, func, or_, select

from . import academic_affairs_stats_service as stats


def _i_registration(db, scope, sids, term_id) -> dict:
    from app.models import AaRegistration, AaRegistrationBatch

    conditions = [
        AaRegistration.tenant_id == stats._tid(),
        AaRegistration.is_deleted.is_(False),
    ]
    if sids is not None:
        if not sids:
            return stats._ind(
                "registration", "注册完成率", numerator=0, denominator=0,
                rate=None, unit="%", drill="registration",
            )
        conditions.append(AaRegistration.student_id.in_(sids))
    if term_id:
        batch_ids = select(AaRegistrationBatch.id).where(
            AaRegistrationBatch.tenant_id == stats._tid(),
            AaRegistrationBatch.term_id == int(term_id),
        )
        conditions.append(AaRegistration.batch_id.in_(batch_ids))

    den, num = db.execute(
        select(
            func.count(AaRegistration.id),
            func.coalesce(func.sum(case((AaRegistration.status == "REGISTERED", 1), else_=0)), 0),
        ).where(*conditions)
    ).one()
    den, num = int(den or 0), int(num or 0)
    return stats._ind(
        "registration", "注册完成率", numerator=num, denominator=den,
        rate=stats._rate(num, den), unit="%", drill="registration",
    )


def _i_teaching_task(db, scope, college_id, term_id) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    class_ids = stats._class_ids_scope(db, scope, college_id)
    conditions = [
        AaTeachingTask.tenant_id == stats._tid(),
        AaTeachingTask.is_deleted.is_(False),
    ]
    if term_id:
        batch_ids = select(AaTeachingTaskBatch.id).where(
            AaTeachingTaskBatch.tenant_id == stats._tid(),
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )
        conditions.append(AaTeachingTask.batch_id.in_(batch_ids))
    if class_ids is not None:
        if not class_ids:
            return stats._ind(
                "teachingTask", "教学任务完成率", numerator=0, denominator=0,
                rate=None, unit="%", drill="teaching-task",
            )
        conditions.append(AaTeachingTask.class_id.in_(class_ids))

    den, num = db.execute(
        select(
            func.count(AaTeachingTask.id),
            func.coalesce(func.sum(case((AaTeachingTask.confirm_at.isnot(None), 1), else_=0)), 0),
        ).where(*conditions)
    ).one()
    den, num = int(den or 0), int(num or 0)
    return stats._ind(
        "teachingTask", "教学任务完成率", numerator=num, denominator=den,
        rate=stats._rate(num, den), unit="%", drill="teaching-task",
    )


def _i_grade_publish(db, scope, college_id, term_id) -> dict:
    from app.models import AaGradeTask

    class_ids = stats._class_ids_scope(db, scope, college_id)
    conditions = [
        AaGradeTask.tenant_id == stats._tid(),
        AaGradeTask.is_deleted.is_(False),
    ]
    if term_id:
        conditions.append(AaGradeTask.term_id == int(term_id))
    if class_ids is not None:
        if not class_ids:
            return stats._ind(
                "gradePublish", "成绩录入发布率", numerator=0, denominator=0,
                rate=None, unit="%", drill="grade",
            )
        conditions.append(AaGradeTask.class_id.in_(class_ids))

    den, num = db.execute(
        select(
            func.count(AaGradeTask.id),
            func.coalesce(func.sum(case((AaGradeTask.status == "PUBLISHED", 1), else_=0)), 0),
        ).where(*conditions)
    ).one()
    den, num = int(den or 0), int(num or 0)
    return stats._ind(
        "gradePublish", "成绩录入发布率", numerator=num, denominator=den,
        rate=stats._rate(num, den), unit="%", drill="grade",
    )


def _i_fail_rate(db, scope, acad_ids, term_id) -> dict:
    from app.models import AcademicGrade

    conditions = [
        AcademicGrade.tenant_id == stats._tid(),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.pass_status.in_(["PASSED", "FAILED"]),
    ]
    if acad_ids is not None:
        if not acad_ids:
            return stats._ind(
                "failRate", "挂科率", numerator=0, denominator=0,
                rate=None, unit="%", drill="grade",
            )
        conditions.append(AcademicGrade.acad_student_id.in_(acad_ids))
    codes = stats._term_codes(db, term_id)
    if codes is not None:
        conditions.append(AcademicGrade.term.in_(codes or ["-"]))

    den, num = db.execute(
        select(
            func.count(AcademicGrade.id),
            func.coalesce(func.sum(case((AcademicGrade.pass_status == "FAILED", 1), else_=0)), 0),
        ).where(*conditions)
    ).one()
    den, num = int(den or 0), int(num or 0)
    return stats._ind(
        "failRate", "挂科率", numerator=num, denominator=den,
        rate=stats._rate(num, den), unit="%", drill="grade",
    )


def _i_graduation(db, scope, sids) -> dict:
    from app.models import AaGraduationAuditResult

    conditions = [
        AaGraduationAuditResult.tenant_id == stats._tid(),
        AaGraduationAuditResult.is_deleted.is_(False),
    ]
    if sids is not None:
        if not sids:
            return stats._ind(
                "graduation", "毕业资格通过率", numerator=0, denominator=0,
                rate=None, unit="%", drill="graduation",
            )
        conditions.append(AaGraduationAuditResult.student_id.in_(sids))

    passed = or_(
        AaGraduationAuditResult.overall == "SYSTEM_PASSED",
        AaGraduationAuditResult.conclusion == "GRADUATED",
    )
    den, num = db.execute(
        select(
            func.count(AaGraduationAuditResult.id),
            func.coalesce(func.sum(case((passed, 1), else_=0)), 0),
        ).where(*conditions)
    ).one()
    den, num = int(den or 0), int(num or 0)
    return stats._ind(
        "graduation", "毕业资格通过率", numerator=num, denominator=den,
        rate=stats._rate(num, den), unit="%", drill="graduation",
    )


def _i_exam(db, scope, college_id, term_id) -> dict:
    from app.models import AaExamBatch, AaExamCourse

    colleges = stats._college_ids_scope(db, scope, college_id)
    conditions = [
        AaExamCourse.tenant_id == stats._tid(),
        AaExamCourse.is_deleted.is_(False),
    ]
    if term_id:
        batch_ids = select(AaExamBatch.id).where(
            AaExamBatch.tenant_id == stats._tid(),
            AaExamBatch.term_id == int(term_id),
            AaExamBatch.is_deleted.is_(False),
        )
        conditions.append(AaExamCourse.batch_id.in_(batch_ids))
    if colleges is not None:
        conditions.append(AaExamCourse.college_id.in_(list(colleges) or [-1]))

    den, num = db.execute(
        select(
            func.count(AaExamCourse.id),
            func.coalesce(func.sum(case((AaExamCourse.status == "CONFIRMED", 1), else_=0)), 0),
        ).where(*conditions)
    ).one()
    den, num = int(den or 0), int(num or 0)
    return stats._ind(
        "exam", "考务统计", value=den, numerator=num, denominator=den,
        rate=(round(num / den * 100, 2) if den else None), unit="%", drill="exam",
    )


def _i_resource(db, scope) -> dict:
    from app.models import AaClassroom, AaClassroomBooking

    grouped = db.execute(
        select(AaClassroom.room_type, func.count(AaClassroom.id))
        .where(AaClassroom.tenant_id == stats._tid(), AaClassroom.is_deleted.is_(False))
        .group_by(AaClassroom.room_type)
    ).all()
    groups = [
        {"key": room_type or "OTHER", "count": int(count or 0)}
        for room_type, count in grouped
    ]
    pending = int(db.scalar(
        select(func.count(AaClassroomBooking.id)).where(
            AaClassroomBooking.tenant_id == stats._tid(),
            AaClassroomBooking.status == "PENDING",
            AaClassroomBooking.is_deleted.is_(False),
        )
    ) or 0)
    return stats._ind(
        "resource", "教学资源统计", value=sum(row["count"] for row in groups),
        numerator=pending, denominator=None, unit="间", drill="classrooms",
        groups=sorted(groups, key=lambda row: row["key"]),
        message="教室为全校共享资源（含待审预约数）",
    )


def _i_schedule_change(db, scope, term_id) -> dict:
    from app.models import AaScheduleChange

    conditions = [
        AaScheduleChange.tenant_id == stats._tid(),
        AaScheduleChange.is_deleted.is_(False),
    ]
    if term_id:
        conditions.append(AaScheduleChange.term_id == int(term_id))
    if not scope.all:
        conditions.append(AaScheduleChange.class_id.in_(list(scope.class_ids) or [-1]))

    grouped = db.execute(
        select(
            AaScheduleChange.change_type,
            func.count(AaScheduleChange.id),
            func.coalesce(func.sum(case((AaScheduleChange.status.in_(["APPROVED", "APPLIED"]), 1), else_=0)), 0),
        )
        .where(*conditions)
        .group_by(AaScheduleChange.change_type)
    ).all()
    den = sum(int(count or 0) for _change_type, count, _applied in grouped)
    num = sum(int(applied or 0) for _change_type, _count, applied in grouped)
    groups = [
        {"key": change_type or "OTHER", "count": int(count or 0)}
        for change_type, count, _applied in grouped
    ]
    return stats._ind(
        "scheduleChange", "调停课统计", value=den, numerator=num, denominator=den,
        rate=(round(num / den * 100, 2) if den else None), unit="%", drill="schedule-change",
        groups=sorted(groups, key=lambda row: row["key"]),
    )


def _i_selection(db, scope, term_id) -> dict:
    from app.models import AaSelectionBatch, AaSelectionCourse

    if not scope.all:
        return stats._ind(
            "courseSelection", "选课统计", value=0, numerator=0, denominator=0, unit="%",
            drill="selection", message="选课为全校口径，受数据范围限制不展示（仅教务处可见）",
        )

    batch_conditions = [
        AaSelectionBatch.tenant_id == stats._tid(),
        AaSelectionBatch.is_deleted.is_(False),
    ]
    if term_id:
        batch_conditions.append(AaSelectionBatch.term_id == int(term_id))

    grouped = db.execute(
        select(AaSelectionBatch.status, func.count(AaSelectionBatch.id))
        .where(*batch_conditions)
        .group_by(AaSelectionBatch.status)
    ).all()
    batch_total = sum(int(count or 0) for _status, count in grouped)
    batch_ids = select(AaSelectionBatch.id).where(*batch_conditions)
    cap, selected = db.execute(
        select(
            func.coalesce(func.sum(AaSelectionCourse.capacity), 0),
            func.coalesce(func.sum(AaSelectionCourse.selected_count), 0),
        ).where(
            AaSelectionCourse.tenant_id == stats._tid(),
            AaSelectionCourse.batch_id.in_(batch_ids),
            AaSelectionCourse.is_deleted.is_(False),
        )
    ).one()
    cap, selected = int(cap or 0), int(selected or 0)
    return stats._ind(
        "courseSelection", "选课统计", value=batch_total, numerator=selected,
        denominator=cap, rate=(round(selected / cap * 100, 2) if cap else None),
        unit="%", drill="selection",
        groups=[{"key": status, "count": int(count or 0)} for status, count in sorted(grouped, key=lambda row: str(row[0] or ""))],
    )


_PATCHES = {
    "_i_registration": _i_registration,
    "_i_teaching_task": _i_teaching_task,
    "_i_grade_publish": _i_grade_publish,
    "_i_fail_rate": _i_fail_rate,
    "_i_graduation": _i_graduation,
    "_i_exam": _i_exam,
    "_i_resource": _i_resource,
    "_i_schedule_change": _i_schedule_change,
    "_i_selection": _i_selection,
}


def install() -> None:
    """幂等替换 legacy module 的纯读聚合函数；overview 动态读取这些 module globals。"""
    for name, replacement in _PATCHES.items():
        original_name = f"_stats_scale_guard_original{name}"
        if not hasattr(stats, original_name):
            setattr(stats, original_name, getattr(stats, name))
        setattr(stats, name, replacement)
