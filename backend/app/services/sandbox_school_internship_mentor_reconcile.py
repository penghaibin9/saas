"""20K 售前学校 · 岗位实习导师工作量与过程责任人对账。"""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select

from app.services.sandbox_school_mentor_pool import (
    EXPECTED_INTERNSHIP_MENTORS,
    MAX_INTERNSHIP_STUDENTS_PER_MENTOR,
    partition_users_by_major,
)
from app.services.sandbox_school_professional_reconcile import _major_specs


def reconcile_internship_mentor_workload(db, tenant_id: int, users: list) -> dict:
    from app.models import (
        AttendanceException,
        InternshipRecord,
        Major,
        RiskRecord,
        StudentProfile,
        WeeklyReport,
    )

    users_by_major = partition_users_by_major(users, graduation=False)
    major_name_by_id = {
        int(mid): major_name
        for mid, major_name in db.execute(select(Major.id, Major.major_name).where(
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )).all()
    }
    student_major = {
        int(sid): major_name_by_id[int(mid)]
        for sid, mid in db.execute(select(StudentProfile.id, StudentProfile.major_id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.grade == "2024",
            StudentProfile.is_deleted.is_(False),
        )).all()
    }

    records = list(db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.is_deleted.is_(False),
    ).order_by(InternshipRecord.student_id)).all())
    grouped: dict[str, list] = defaultdict(list)
    for record in records:
        grouped[student_major[int(record.student_id)]].append(record)

    loads: Counter[int] = Counter()
    advisor_by_internship: dict[int, str] = {}
    for _major_code, _college_name, major_name in _major_specs():
        mentor_pool = users_by_major[major_name]
        for index, record in enumerate(grouped[major_name]):
            user = mentor_pool[index % len(mentor_pool)]
            record.advisor_user_id = int(user.id)
            record.advisor_name = user.real_name
            loads[int(user.id)] += 1
            advisor_by_internship[int(record.id)] = user.real_name

    # 页面会从过程表直接展示“批阅人/处置人/风险责任人”，这些快照必须跟主实习导师一致。
    for report in db.scalars(select(WeeklyReport).where(
        WeeklyReport.tenant_id == tenant_id,
        WeeklyReport.is_deleted.is_(False),
    )):
        if report.reviewed_by_name is not None:
            report.reviewed_by_name = advisor_by_internship[int(report.internship_id)]

    for row in db.scalars(select(AttendanceException).where(
        AttendanceException.tenant_id == tenant_id,
        AttendanceException.is_deleted.is_(False),
    )):
        if row.handled_by_name is not None:
            row.handled_by_name = advisor_by_internship[int(row.internship_id)]

    for row in db.scalars(select(RiskRecord).where(
        RiskRecord.tenant_id == tenant_id,
        RiskRecord.is_deleted.is_(False),
    )):
        row.owner_name = advisor_by_internship[int(row.internship_id)]

    db.commit()
    max_load = max(loads.values(), default=0)
    if len(loads) != EXPECTED_INTERNSHIP_MENTORS or max_load > MAX_INTERNSHIP_STUDENTS_PER_MENTOR:
        raise RuntimeError(
            f"实习导师工作量异常 used={len(loads)} maxLoad={max_load}"
        )
    return {
        "mentors": len(loads),
        "students": len(records),
        "maxStudentsPerMentor": max_load,
        "avgStudentsPerMentor": round(len(records) / len(loads), 2),
    }
