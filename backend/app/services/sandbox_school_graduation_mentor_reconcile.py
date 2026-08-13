"""20K 售前学校 · 毕业设计导师库、题目与学生导师工作量对账。"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select

from app.services.sandbox_school_master_seed import _bulk_insert
from app.services.sandbox_school_mentor_pool import (
    EXPECTED_GRADUATION_MENTORS,
    MAX_GRADUATION_STUDENTS_PER_MENTOR,
    partition_users_by_major,
)
from app.services.sandbox_school_professional_reconcile import _major_specs


def _ensure_graduation_mentor_rows(db, tenant_id: int, users: list) -> list:
    from app.models import GraduationMentor

    selected_logins = [row.login_name for row in users]
    existing = {
        row.teacher_no: row
        for row in db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == tenant_id,
            GraduationMentor.teacher_no.in_(selected_logins),
            GraduationMentor.is_deleted.is_(False),
        )).all()
    }
    new_rows = []
    for index, user in enumerate(users, 1):
        if user.login_name in existing:
            continue
        new_rows.append({
            "tenant_id": tenant_id,
            "teacher_no": user.login_name,
            "teacher_name": user.real_name,
            "mentor_type": "INTERNAL",
            "title": "副教授" if index % 4 == 0 else "讲师",
            "research_direction": "专业实践与产教融合项目",
            "max_capacity": MAX_GRADUATION_STUDENTS_PER_MENTOR,
            "current_count": 0,
            "qualification_status": "QUALIFIED",
        })
    _bulk_insert(db, GraduationMentor, new_rows, chunk_size=500)
    db.flush()

    rows = list(db.scalars(select(GraduationMentor).where(
        GraduationMentor.tenant_id == tenant_id,
        GraduationMentor.teacher_no.in_(selected_logins),
        GraduationMentor.is_deleted.is_(False),
    ).order_by(GraduationMentor.teacher_no)).all())
    if len(rows) != EXPECTED_GRADUATION_MENTORS:
        raise RuntimeError(
            f"毕设导师库扩容失败 expected={EXPECTED_GRADUATION_MENTORS} actual={len(rows)}"
        )
    return rows


def reconcile_graduation_mentor_workload(db, tenant_id: int, users: list) -> dict:
    from app.models import GraduationMentor, GraduationStudent, GraduationTopic, Major
    from app.services.sandbox_school_professional_catalog import professional_profile

    mentor_rows = _ensure_graduation_mentor_rows(db, tenant_id, users)
    mentor_by_teacher_no = {row.teacher_no: row for row in mentor_rows}
    ordered_mentors = [mentor_by_teacher_no[user.login_name] for user in users]
    mentors_by_major = partition_users_by_major(ordered_mentors, graduation=True)

    major_id_by_name = {
        major_name: int(mid)
        for mid, major_name in db.execute(select(Major.id, Major.major_name).where(
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )).all()
    }
    college_id_by_major = {
        major_name: int(college_id)
        for college_id, major_name in db.execute(select(Major.college_id, Major.major_name).where(
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )).all()
    }
    major_name_by_id = {mid: name for name, mid in major_id_by_name.items()}

    for _major_code, college_name, major_name in _major_specs():
        profile = professional_profile(major_name)
        for mentor in mentors_by_major[major_name]:
            mentor.college_id = str(college_id_by_major[major_name])
            mentor.college_name = college_name
            mentor.major_name = major_name
            mentor.research_direction = f"{profile.industry}·{major_name}岗位实践"
            mentor.max_capacity = MAX_GRADUATION_STUDENTS_PER_MENTOR
            mentor.current_count = 0
            mentor.qualification_status = "QUALIFIED"

    topics = list(db.scalars(select(GraduationTopic).where(
        GraduationTopic.tenant_id == tenant_id,
        GraduationTopic.is_deleted.is_(False),
    ).order_by(GraduationTopic.id)).all())
    topic_mentor: dict[int, GraduationMentor] = {}
    topic_cursor: Counter[str] = Counter()
    for topic in topics:
        major_name = topic.major_name or major_name_by_id[int(topic.major_id)]
        pool = mentors_by_major[major_name]
        mentor = pool[topic_cursor[major_name] % len(pool)]
        topic_cursor[major_name] += 1
        topic.advisor_mentor_id = int(mentor.id)
        topic.advisor_name = mentor.teacher_name
        topic_mentor[int(topic.id)] = mentor

    students = list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.student_no)).all())
    selecting_cursor: Counter[str] = Counter()
    loads: Counter[int] = Counter()
    for student in students:
        major_name = major_name_by_id[int(student.major_id)]
        pool = mentors_by_major[major_name]
        if student.topic_id is not None:
            mentor = topic_mentor[int(student.topic_id)]
        else:
            mentor = pool[selecting_cursor[major_name] % len(pool)]
            selecting_cursor[major_name] += 1
        student.mentor_id = int(mentor.id)
        student.advisor_name = mentor.teacher_name
        student.student_group = f"{major_name}导师组{(int(mentor.id) % len(pool)) + 1}"
        loads[int(mentor.id)] += 1

    for mentor in mentor_rows:
        mentor.current_count = loads[int(mentor.id)]
        if mentor.current_count > mentor.max_capacity:
            raise RuntimeError(
                f"毕设导师超容量 mentor={mentor.teacher_name} "
                f"current={mentor.current_count} max={mentor.max_capacity}"
            )

    db.commit()
    max_load = max(loads.values(), default=0)
    if len(loads) != EXPECTED_GRADUATION_MENTORS or max_load > MAX_GRADUATION_STUDENTS_PER_MENTOR:
        raise RuntimeError(
            f"毕设导师工作量异常 used={len(loads)} maxLoad={max_load}"
        )
    return {
        "mentors": len(mentor_rows),
        "students": len(students),
        "topics": len(topics),
        "maxStudentsPerMentor": max_load,
        "avgStudentsPerMentor": round(len(students) / len(mentor_rows), 2),
    }
