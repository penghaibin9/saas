"""sandbox-school · 20K 真实学校 13B 教务运营数据。

与旧 seed_academic_affairs_demo.py 不同，本文件绝不依赖 20/22/34 等历史固定主键；
所有学院、专业、班级、学生、教师均从本次 20K 主数据查询真实 ID 后构造。

2026-08-13 时点：
- 2025-2026-2 已结束：保留教学任务、考务、成绩作为历史学期事实；
- 2026-2027-1 尚未开学：学期已发布，教学任务已确认，课表提前发布，9 月 1 日生效；
- 2026 级 7,000 人处于入学注册资格预核验，最终状态仍 PENDING_REGISTER；
- 2024 级以岗位实习为主，不强行安排大量普通课堂任务。

目标不是把所有 t_aa_* 表“各塞一行”，而是让高频教务工作区有学校量级、关系自洽的数据。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.services.sandbox_school_master_seed import _bulk_insert

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)

EXPECTED_TERMS = 4
EXPECTED_TIME_SLOTS = 10
EXPECTED_CLASSROOMS = 320
EXPECTED_COURSES = 196             # 4 公共 + 32 专业 × 6
EXPECTED_PROGRAMS = 96             # 32 专业 × 2024/2025/2026
EXPECTED_PROGRAM_COURSES = 960     # 每方案 4 公共 + 6 专业
EXPECTED_REGISTRATIONS = 20_000
EXPECTED_HISTORICAL_TASKS = 256    # 2025 级 128 班 × 2 门
EXPECTED_NEXT_TASKS = 768           # 2025 级 128×4 + 2026 级 128×2
EXPECTED_TASKS = EXPECTED_HISTORICAL_TASKS + EXPECTED_NEXT_TASKS
EXPECTED_SCHEDULE_ITEMS = EXPECTED_TASKS
EXPECTED_GRADE_TASKS = EXPECTED_HISTORICAL_TASKS
EXPECTED_GRADE_RECORDS = 13_200     # 2025 级 6,600 人 × 2 门
EXPECTED_EXAM_COURSES = EXPECTED_HISTORICAL_TASKS
EXPECTED_EXAM_SEATS = EXPECTED_GRADE_RECORDS

PUBLIC_COURSES = (
    ("PUB001", "思想道德与法治", "PUBLIC_BASIC", "REQUIRED", Decimal("2.0"), 32, "CHECK"),
    ("PUB002", "大学英语", "PUBLIC_BASIC", "REQUIRED", Decimal("3.0"), 48, "EXAM"),
    ("PUB003", "体育与健康", "PUBLIC_BASIC", "REQUIRED", Decimal("1.0"), 32, "CHECK"),
    ("PUB004", "信息技术", "PUBLIC_BASIC", "REQUIRED", Decimal("2.0"), 32, "EXAM"),
)

MAJOR_COURSE_TEMPLATES = (
    ("01", "专业导论", "DISCIPLINE_BASIC", "REQUIRED", Decimal("2.0"), 32, "CHECK"),
    ("02", "基础实训", "MAJOR_CORE", "REQUIRED", Decimal("3.0"), 48, "CHECK"),
    ("03", "核心技能", "MAJOR_CORE", "REQUIRED", Decimal("4.0"), 64, "EXAM"),
    ("04", "项目实践", "PRACTICE", "REQUIRED", Decimal("3.0"), 48, "CHECK"),
    ("05", "综合实训", "PRACTICE", "REQUIRED", Decimal("4.0"), 64, "CHECK"),
    ("06", "岗位技能", "MAJOR_CORE", "REQUIRED", Decimal("4.0"), 64, "EXAM"),
)


def _org(db, tenant_id: int) -> dict:
    from app.models import College, Major, SchoolClass, StudentProfile, User

    colleges = list(db.execute(select(
        College.id, College.code, College.college_name,
    ).where(
        College.tenant_id == tenant_id,
        College.is_deleted.is_(False),
    ).order_by(College.code)).all())
    majors = list(db.execute(select(
        Major.id, Major.code, Major.major_name, Major.college_id,
    ).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.code)).all())
    classes = list(db.execute(select(
        SchoolClass.id, SchoolClass.class_code, SchoolClass.class_name, SchoolClass.grade,
        SchoolClass.major_id, SchoolClass.counselor_id,
    ).where(
        SchoolClass.tenant_id == tenant_id,
        SchoolClass.is_deleted.is_(False),
    ).order_by(SchoolClass.class_code)).all())
    students = list(db.execute(select(
        StudentProfile.id, StudentProfile.student_no, StudentProfile.real_name,
        StudentProfile.grade, StudentProfile.class_id, StudentProfile.major_id,
        StudentProfile.college_id,
    ).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    ).order_by(StudentProfile.student_no)).all())
    teachers = list(db.execute(select(
        User.id, User.login_name, User.real_name,
    ).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_t%"),
        User.is_deleted.is_(False),
        User.status == "ACTIVE",
    ).order_by(User.login_name)).all())
    academic_admins = list(db.execute(select(
        User.id, User.login_name, User.real_name,
    ).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_aa%"),
        User.is_deleted.is_(False),
        User.status == "ACTIVE",
    ).order_by(User.login_name)).all())
    if not (len(colleges) == 8 and len(majors) == 32 and len(classes) == 384 and len(students) == 20_000):
        raise RuntimeError(
            f"13B 主数据基数异常 colleges={len(colleges)} majors={len(majors)} "
            f"classes={len(classes)} students={len(students)}"
        )
    if len(teachers) < 900 or len(academic_admins) < 1:
        raise RuntimeError("13B 教师/教务管理员账号未准备完整")
    return {
        "colleges": colleges,
        "majors": majors,
        "classes": classes,
        "students": students,
        "teachers": teachers,
        "academicAdmins": academic_admins,
    }


def _seed_terms_slots_resources(db, tenant_id: int) -> dict:
    from app.models import AaCalendarEvent, AaClassroom, AaTerm, AaTimeSlot

    term_rows = [
        {
            "tenant_id": tenant_id, "year_code": "2024-2025", "term_no": 2,
            "term_name": "2024-2025学年第二学期", "start_date": datetime(2025, 2, 24),
            "end_date": datetime(2025, 7, 4), "teaching_weeks": 18, "exam_week_start": 17,
            "is_current": False, "status": "ARCHIVED",
        },
        {
            "tenant_id": tenant_id, "year_code": "2025-2026", "term_no": 1,
            "term_name": "2025-2026学年第一学期", "start_date": datetime(2025, 9, 1),
            "end_date": datetime(2026, 1, 16), "teaching_weeks": 18, "exam_week_start": 17,
            "is_current": False, "status": "ARCHIVED",
        },
        {
            "tenant_id": tenant_id, "year_code": "2025-2026", "term_no": 2,
            "term_name": "2025-2026学年第二学期", "start_date": datetime(2026, 2, 23),
            "end_date": datetime(2026, 7, 10), "teaching_weeks": 18, "exam_week_start": 17,
            "is_current": False, "status": "ARCHIVED",
        },
        {
            "tenant_id": tenant_id, "year_code": "2026-2027", "term_no": 1,
            "term_name": "2026-2027学年第一学期", "start_date": datetime(2026, 9, 1),
            "end_date": datetime(2027, 1, 15), "teaching_weeks": 18, "exam_week_start": 17,
            "is_current": True, "status": "PUBLISHED",
        },
    ]
    _bulk_insert(db, AaTerm, term_rows)
    db.flush()
    term_by_code = {
        f"{year}-{term_no}": int(tid)
        for tid, year, term_no in db.execute(select(AaTerm.id, AaTerm.year_code, AaTerm.term_no).where(
            AaTerm.tenant_id == tenant_id,
            AaTerm.is_deleted.is_(False),
        )).all()
    }

    calendar_rows = [
        {
            "tenant_id": tenant_id, "term_id": term_by_code["2025-2026-2"],
            "event_type": "TEACHING", "start_date": datetime(2026, 2, 23),
            "end_date": datetime(2026, 6, 19), "remark": "第二学期正常教学周",
        },
        {
            "tenant_id": tenant_id, "term_id": term_by_code["2025-2026-2"],
            "event_type": "EXAM", "start_date": datetime(2026, 6, 22),
            "end_date": datetime(2026, 7, 3), "remark": "期末考试周",
        },
        {
            "tenant_id": tenant_id, "term_id": term_by_code["2026-2027-1"],
            "event_type": "TEACHING", "start_date": datetime(2026, 9, 1),
            "end_date": datetime(2026, 12, 25), "remark": "第一学期正常教学周",
        },
        {
            "tenant_id": tenant_id, "term_id": term_by_code["2026-2027-1"],
            "event_type": "EXAM", "start_date": datetime(2027, 1, 4),
            "end_date": datetime(2027, 1, 15), "remark": "期末考试周",
        },
    ]
    _bulk_insert(db, AaCalendarEvent, calendar_rows)

    times = (
        (1, "第1节", "08:20", "09:05"), (2, "第2节", "09:15", "10:00"),
        (3, "第3节", "10:20", "11:05"), (4, "第4节", "11:15", "12:00"),
        (5, "第5节", "14:00", "14:45"), (6, "第6节", "14:55", "15:40"),
        (7, "第7节", "16:00", "16:45"), (8, "第8节", "16:55", "17:40"),
        (9, "第9节", "19:00", "19:45"), (10, "第10节", "19:55", "20:40"),
    )
    _bulk_insert(db, AaTimeSlot, [{
        "tenant_id": tenant_id, "slot_no": no, "slot_name": name,
        "start_time": start, "end_time": end, "campus_code": "MAIN",
        "enabled": True, "status": "ENABLED",
    } for no, name, start, end in times])

    classroom_rows = []
    for building_no in range(1, 9):
        building_code = f"J{building_no}"
        building_name = f"教学楼{building_no}号楼"
        for room_seq in range(1, 41):
            floor_no = ((room_seq - 1) // 10) + 1
            room_no = f"{floor_no}{((room_seq - 1) % 10) + 1:02d}"
            classroom_rows.append({
                "tenant_id": tenant_id,
                "building_code": building_code,
                "building_name": building_name,
                "room_code": room_no,
                "room_name": f"{building_name}{room_no}",
                "capacity": 60 if room_seq % 5 else 80,
                "exam_seats": 30 if room_seq % 5 else 40,
                "is_exclusive": False,
                "room_type": "COMPUTER" if room_seq % 10 == 0 else ("MULTIMEDIA" if room_seq % 4 == 0 else "LECTURE"),
                "campus_code": "MAIN",
                "status": "AVAILABLE",
            })
    _bulk_insert(db, AaClassroom, classroom_rows, chunk_size=500)
    db.commit()
    return {"termByCode": term_by_code, "calendarEvents": len(calendar_rows), "classrooms": len(classroom_rows)}


def _seed_courses_programs(db, tenant_id: int, org: dict) -> dict:
    from app.models import AaCourse, AaProgram, AaProgramCourse

    teachers = org["teachers"]
    college_by_id = {int(c.id): c for c in org["colleges"]}
    majors = org["majors"]

    course_rows = []
    for idx, (code, name, category, nature, credit, hours, exam_mode) in enumerate(PUBLIC_COURSES):
        teacher = teachers[idx % len(teachers)]
        course_rows.append({
            "tenant_id": tenant_id,
            "course_code": code,
            "course_name": name,
            "category": category,
            "nature": nature,
            "credit": credit,
            "hours_total": hours,
            "hours_theory": hours // 2,
            "hours_practice": hours - hours // 2,
            "exam_mode": exam_mode,
            "owner_teacher_id": int(teacher.id),
            "is_core": False,
            "is_all_major": True,
            "applicable_majors_json": json.dumps([int(m.id) for m in majors]),
            "version": 1,
            "status": "ENABLED",
        })
    for major_index, major in enumerate(majors):
        owner = teachers[(major_index * 5) % len(teachers)]
        for suffix, label, category, nature, credit, hours, exam_mode in MAJOR_COURSE_TEMPLATES:
            course_rows.append({
                "tenant_id": tenant_id,
                "course_code": f"{major.code}-{suffix}",
                "course_name": f"{major.major_name}{label}",
                "category": category,
                "nature": nature,
                "credit": credit,
                "hours_total": hours,
                "hours_theory": 16 if category == "PRACTICE" else hours // 2,
                "hours_practice": hours - (16 if category == "PRACTICE" else hours // 2),
                "exam_mode": exam_mode,
                "owner_college_id": int(major.college_id),
                "owner_teacher_id": int(owner.id),
                "is_core": label in {"核心技能", "岗位技能"},
                "is_all_major": False,
                "applicable_majors_json": json.dumps([int(major.id)]),
                "description": f"面向{major.major_name}专业岗位能力培养的校级标准课程。",
                "version": 1,
                "status": "ENABLED",
            })
    if len(course_rows) != EXPECTED_COURSES:
        raise RuntimeError(f"课程目录数量异常: {len(course_rows)}")
    _bulk_insert(db, AaCourse, course_rows, chunk_size=500)
    db.flush()

    courses = list(db.execute(select(
        AaCourse.id, AaCourse.course_code, AaCourse.course_name, AaCourse.credit,
    ).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.is_deleted.is_(False),
    )).all())
    course_by_code = {c.course_code: c for c in courses}

    program_rows = []
    for major in majors:
        for grade in ("2024", "2025", "2026"):
            program_rows.append({
                "tenant_id": tenant_id,
                "program_name": f"{major.major_name}专业{grade}级人才培养方案",
                "major_id": int(major.id),
                "grade_year": grade,
                "total_credits": Decimal("140.0"),
                "requirement_json": json.dumps({
                    "公共基础": 30, "专业基础与核心": 70, "实践教学": 32, "素质拓展": 8,
                }, ensure_ascii=False),
                "version": 1,
                "status": "ENABLED",
            })
    _bulk_insert(db, AaProgram, program_rows, chunk_size=500)
    db.flush()

    programs = list(db.execute(select(
        AaProgram.id, AaProgram.major_id, AaProgram.grade_year,
    ).where(
        AaProgram.tenant_id == tenant_id,
        AaProgram.is_deleted.is_(False),
    )).all())
    major_by_id = {int(m.id): m for m in majors}
    pc_rows = []
    for program in programs:
        major = major_by_id[int(program.major_id)]
        for term_no, (code, name, *_rest) in enumerate(PUBLIC_COURSES, 1):
            course = course_by_code[code]
            pc_rows.append({
                "tenant_id": tenant_id,
                "program_id": int(program.id),
                "course_id": int(course.id),
                "course_name": name,
                "open_term_no": min(term_no, 4),
                "module": "公共基础",
                "credit_snapshot": course.credit,
            })
        for term_offset, (suffix, label, *_rest) in enumerate(MAJOR_COURSE_TEMPLATES, 1):
            code = f"{major.code}-{suffix}"
            course = course_by_code[code]
            pc_rows.append({
                "tenant_id": tenant_id,
                "program_id": int(program.id),
                "course_id": int(course.id),
                "course_name": course.course_name,
                "open_term_no": term_offset,
                "module": "专业课程" if term_offset <= 4 else "实践课程",
                "credit_snapshot": course.credit,
            })
    _bulk_insert(db, AaProgramCourse, pc_rows, chunk_size=1000)
    db.commit()
    return {
        "courses": len(course_rows),
        "programs": len(program_rows),
        "programCourses": len(pc_rows),
        "courseByCode": course_by_code,
    }


def _seed_registration(db, tenant_id: int, org: dict, term_by_code: dict[str, int]) -> dict:
    from app.models import AaRegistration, AaRegistrationBatch, AaRegistrationException

    batches = [
        AaRegistrationBatch(
            tenant_id=tenant_id,
            batch_name="2024级2025-2026学年学年注册",
            register_type="ANNUAL",
            term_id=term_by_code["2025-2026-1"],
            window_start=datetime(2025, 8, 25), window_end=datetime(2025, 9, 10),
            scope_json=json.dumps({"grades": ["2024"]}), status="CLOSED",
        ),
        AaRegistrationBatch(
            tenant_id=tenant_id,
            batch_name="2025级入学注册",
            register_type="ENROLL",
            term_id=term_by_code["2025-2026-1"],
            window_start=datetime(2025, 9, 1), window_end=datetime(2025, 9, 12),
            scope_json=json.dumps({"grades": ["2025"]}), status="CLOSED",
        ),
        AaRegistrationBatch(
            tenant_id=tenant_id,
            batch_name="2026级入学注册资格核验",
            register_type="ENROLL",
            term_id=term_by_code["2026-2027-1"],
            window_start=datetime(2026, 8, 10), window_end=datetime(2026, 9, 10),
            scope_json=json.dumps({"grades": ["2026"], "mode": "PRECHECK"}), status="OPEN",
        ),
    ]
    db.add_all(batches)
    db.flush()
    batch_by_grade = {"2024": int(batches[0].id), "2025": int(batches[1].id), "2026": int(batches[2].id)}

    rows = []
    exceptions = []
    grade_seq = defaultdict(int)
    for stu in org["students"]:
        grade = str(stu.grade)
        grade_seq[grade] += 1
        seq = grade_seq[grade]
        if grade in {"2024", "2025"}:
            rows.append({
                "tenant_id": tenant_id,
                "batch_id": batch_by_grade[grade],
                "student_id": int(stu.id),
                "precheck_json": json.dumps({"identity": "PASS", "fee": "PASS", "material": "PASS"}),
                "register_at": datetime(int(grade), 9, 1, 9, 0) if grade == "2025" else datetime(2025, 9, 1, 9, 0),
                "status": "REGISTERED",
                "eligibility_status": "ELIGIBLE",
                "eligibility_note": "学籍与缴费材料核验通过",
                "eligibility_checked_at": datetime(2025, 8, 28, 10, 0),
            })
        else:
            if seq % 50 == 0:
                eligibility = "INELIGIBLE"
                note = "报到材料存在缺项，待补充后重新核验"
            elif seq % 10 == 0:
                eligibility = "PENDING"
                note = "待完成线上材料核验"
            else:
                eligibility = "ELIGIBLE"
                note = "身份、专业、预报到材料预核验通过"
            rows.append({
                "tenant_id": tenant_id,
                "batch_id": batch_by_grade[grade],
                "student_id": int(stu.id),
                "precheck_json": json.dumps({
                    "identity": "PASS",
                    "fee": "PENDING" if seq % 8 == 0 else "PASS",
                    "material": "MISSING" if eligibility == "INELIGIBLE" else "PASS",
                }),
                "status": "PENDING_REGISTER",
                "eligibility_status": eligibility,
                "eligibility_note": note,
                "eligibility_checked_at": REFERENCE_NOW if eligibility != "PENDING" else None,
            })
            if eligibility == "INELIGIBLE":
                exceptions.append({
                    "tenant_id": tenant_id,
                    "batch_id": batch_by_grade[grade],
                    "student_id": int(stu.id),
                    "exception_type": "MATERIAL_MISSING",
                    "description": "新生注册材料缺项，已进入迎新异常与注册核验协同处理",
                    "status": "OPEN",
                })
    _bulk_insert(db, AaRegistration, rows, chunk_size=1000)
    db.flush()
    registration_by_key = {
        (int(batch_id), int(student_id)): int(reg_id)
        for reg_id, batch_id, student_id in db.execute(select(
            AaRegistration.id, AaRegistration.batch_id, AaRegistration.student_id,
        ).where(
            AaRegistration.tenant_id == tenant_id,
            AaRegistration.is_deleted.is_(False),
        )).all()
    }
    for row in exceptions:
        row["registration_id"] = registration_by_key[(row["batch_id"], row["student_id"])]
    _bulk_insert(db, AaRegistrationException, exceptions, chunk_size=500)
    db.commit()
    return {"batches": 3, "registrations": len(rows), "exceptions": len(exceptions)}


def _class_rosters(org: dict) -> dict[int, list]:
    out: dict[int, list] = defaultdict(list)
    for stu in org["students"]:
        out[int(stu.class_id)].append(stu)
    return out


def _seed_tasks_schedules_grades_exams(db, tenant_id: int, org: dict,
                                       term_by_code: dict[str, int], course_by_code: dict) -> dict:
    from app.models import (
        AaClassroom, AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom,
        AaExamRoomStudent, AaGradeRecord, AaGradeTask, AaScheduleBatch,
        AaScheduleItem, AaScheduleScopeHead, AaTeachingTask, AaTeachingTaskBatch,
        AcademicGrade,
    )

    classes_by_grade = defaultdict(list)
    for cls in org["classes"]:
        classes_by_grade[str(cls.grade)].append(cls)
    major_by_id = {int(m.id): m for m in org["majors"]}
    rosters = _class_rosters(org)
    teachers = org["teachers"]
    classrooms = list(db.execute(select(
        AaClassroom.id, AaClassroom.room_name,
    ).where(
        AaClassroom.tenant_id == tenant_id,
        AaClassroom.status == "AVAILABLE",
        AaClassroom.is_deleted.is_(False),
    ).order_by(AaClassroom.id)).all())

    hist_batch = AaTeachingTaskBatch(
        tenant_id=tenant_id,
        term_id=term_by_code["2025-2026-2"],
        batch_name="2025-2026学年第二学期教学任务",
        generate_at=datetime(2026, 2, 8, 9, 0),
        status="APPROVED",
    )
    next_batch = AaTeachingTaskBatch(
        tenant_id=tenant_id,
        term_id=term_by_code["2026-2027-1"],
        batch_name="2026-2027学年第一学期教学任务",
        generate_at=datetime(2026, 7, 20, 9, 0),
        status="APPROVED",
    )
    db.add_all([hist_batch, next_batch])
    db.flush()

    hist_task_rows = []
    next_task_rows = []
    teacher_cursor = 0
    for cls in classes_by_grade["2025"]:
        major = major_by_id[int(cls.major_id)]
        for suffix in ("02", "03"):
            course = course_by_code[f"{major.code}-{suffix}"]
            teacher = teachers[teacher_cursor % len(teachers)]
            teacher_cursor += 1
            hist_task_rows.append({
                "tenant_id": tenant_id, "batch_id": int(hist_batch.id),
                "course_id": int(course.id), "course_code": course.course_code,
                "course_name": course.course_name, "class_id": int(cls.id),
                "teaching_class_code": f"H-{cls.class_code}-{suffix}",
                "teaching_class_name": f"{cls.class_name}-{course.course_name}",
                "teacher_id": int(teacher.id), "teacher_key": teacher.login_name,
                "teacher_name": teacher.real_name, "expected_students": len(rosters[int(cls.id)]),
                "weekly_hours": 2, "total_hours": 36, "start_week": 1, "end_week": 18,
                "required_room_type": "MULTIMEDIA", "no_auto_schedule": False,
                "confirm_at": datetime(2026, 2, 12, 10, 0), "status": "READY",
            })
    for grade in ("2025", "2026"):
        suffixes = ("05", "06", "PUB002", "PUB003") if grade == "2025" else ("01", "PUB004")
        for cls in classes_by_grade[grade]:
            major = major_by_id[int(cls.major_id)]
            for suffix in suffixes:
                course = course_by_code[suffix] if suffix.startswith("PUB") else course_by_code[f"{major.code}-{suffix}"]
                teacher = teachers[teacher_cursor % len(teachers)]
                teacher_cursor += 1
                next_task_rows.append({
                    "tenant_id": tenant_id, "batch_id": int(next_batch.id),
                    "course_id": int(course.id), "course_code": course.course_code,
                    "course_name": course.course_name, "class_id": int(cls.id),
                    "teaching_class_code": f"N-{cls.class_code}-{suffix}",
                    "teaching_class_name": f"{cls.class_name}-{course.course_name}",
                    "teacher_id": int(teacher.id), "teacher_key": teacher.login_name,
                    "teacher_name": teacher.real_name, "expected_students": len(rosters[int(cls.id)]),
                    "weekly_hours": 2, "total_hours": 36, "start_week": 1, "end_week": 18,
                    "required_room_type": "MULTIMEDIA" if suffix != "05" else "COMPUTER",
                    "no_auto_schedule": False,
                    "confirm_at": datetime(2026, 8, 5, 10, 0), "status": "READY",
                })
    if len(hist_task_rows) != EXPECTED_HISTORICAL_TASKS or len(next_task_rows) != EXPECTED_NEXT_TASKS:
        raise RuntimeError(f"教学任务数量异常 hist={len(hist_task_rows)} next={len(next_task_rows)}")
    _bulk_insert(db, AaTeachingTask, hist_task_rows, chunk_size=500)
    _bulk_insert(db, AaTeachingTask, next_task_rows, chunk_size=500)
    db.flush()

    hist_tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id == hist_batch.id,
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).all())
    next_tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id == next_batch.id,
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).all())

    hist_sched = AaScheduleBatch(
        tenant_id=tenant_id, term_id=term_by_code["2025-2026-2"],
        batch_name="2025-2026学年第二学期正式课表", status="ARCHIVED",
        publish_at=datetime(2026, 2, 18, 9, 0),
    )
    next_sched = AaScheduleBatch(
        tenant_id=tenant_id, term_id=term_by_code["2026-2027-1"],
        batch_name="2026-2027学年第一学期正式课表", status="PUBLISHED",
        publish_at=datetime(2026, 8, 10, 9, 0),
    )
    db.add_all([hist_sched, next_sched])
    db.flush()

    class_room = {}
    scheduled_class_ids = [int(c.id) for c in classes_by_grade["2025"] + classes_by_grade["2026"]]
    for idx, class_id in enumerate(scheduled_class_ids):
        class_room[class_id] = classrooms[idx % len(classrooms)]

    hist_per_class = defaultdict(int)
    next_per_class = defaultdict(int)
    schedule_rows = []
    for task in hist_tasks:
        idx = hist_per_class[int(task.class_id)]
        hist_per_class[int(task.class_id)] += 1
        room = class_room[int(task.class_id)]
        schedule_rows.append({
            "tenant_id": tenant_id, "batch_id": int(hist_sched.id), "task_id": int(task.id),
            "course_id": int(task.course_id), "course_name": task.course_name,
            "class_id": int(task.class_id), "class_name": task.teaching_class_name,
            "teacher_key": task.teacher_key, "teacher_name": task.teacher_name,
            "weekday": 2 + idx, "slot_no": 1 + idx * 2,
            "start_week": 1, "end_week": 18, "week_parity": "ALL",
            "classroom_id": int(room.id), "classroom_text": room.room_name,
            "status": "EFFECTIVE", "source": "AUTO",
        })
    for task in next_tasks:
        idx = next_per_class[int(task.class_id)]
        next_per_class[int(task.class_id)] += 1
        room = class_room[int(task.class_id)]
        schedule_rows.append({
            "tenant_id": tenant_id, "batch_id": int(next_sched.id), "task_id": int(task.id),
            "course_id": int(task.course_id), "course_name": task.course_name,
            "class_id": int(task.class_id), "class_name": task.teaching_class_name,
            "teacher_key": task.teacher_key, "teacher_name": task.teacher_name,
            "weekday": 1 + idx, "slot_no": 1 + idx * 2,
            "start_week": 1, "end_week": 18, "week_parity": "ALL",
            "classroom_id": int(room.id), "classroom_text": room.room_name,
            "status": "EFFECTIVE", "source": "AUTO",
        })
    _bulk_insert(db, AaScheduleItem, schedule_rows, chunk_size=1000)
    db.add(AaScheduleScopeHead(
        tenant_id=tenant_id,
        term_id=term_by_code["2026-2027-1"],
        scope_type="SCHOOL", scope_id=0,
        active_batch_id=int(next_sched.id), version=1,
        published_at=datetime(2026, 8, 10, 9, 0),
    ))

    # 2025 级历史成绩任务：直接回链已有 t_acad_grade 真值，避免出现两套成绩互相打架。
    academic_grades = list(db.execute(select(
        AcademicGrade.id, AcademicGrade.acad_student_id, AcademicGrade.course_name,
        AcademicGrade.term, AcademicGrade.score, AcademicGrade.pass_status,
    ).where(
        AcademicGrade.tenant_id == tenant_id,
        AcademicGrade.term == "2025-2026-2",
        AcademicGrade.is_deleted.is_(False),
    )).all())
    from app.models import AcademicStudent
    sid_by_acad = {
        int(aid): int(sid)
        for aid, sid in db.execute(select(AcademicStudent.id, AcademicStudent.student_id).where(
            AcademicStudent.tenant_id == tenant_id,
            AcademicStudent.grade == "2025",
            AcademicStudent.is_deleted.is_(False),
        )).all()
    }
    grade_lookup = {
        (sid_by_acad.get(int(g.acad_student_id)), g.course_name): g
        for g in academic_grades
        if sid_by_acad.get(int(g.acad_student_id)) is not None
    }

    grade_task_rows = []
    for task in hist_tasks:
        grade_task_rows.append({
            "tenant_id": tenant_id,
            "teaching_task_id": int(task.id),
            "term_id": term_by_code["2025-2026-2"],
            "term_code": "2025-2026-2",
            "course_id": int(task.course_id), "course_name": task.course_name,
            "class_id": int(task.class_id), "teacher_key": task.teacher_key,
            "credit": course_by_code[task.course_code].credit,
            "usual_ratio": 30, "midterm_ratio": 0, "final_ratio": 70,
            "pass_line": 60, "status": "PUBLISHED",
            "submitted_at": datetime(2026, 7, 1, 10, 0),
            "college_reviewed_at": datetime(2026, 7, 2, 9, 0),
            "academic_reviewed_at": datetime(2026, 7, 3, 9, 0),
            "publish_at": datetime(2026, 7, 4, 9, 0),
        })
    _bulk_insert(db, AaGradeTask, grade_task_rows, chunk_size=500)
    db.flush()
    grade_task_by_tt = {
        int(ttid): int(gtid)
        for gtid, ttid in db.execute(select(AaGradeTask.id, AaGradeTask.teaching_task_id).where(
            AaGradeTask.tenant_id == tenant_id,
            AaGradeTask.is_deleted.is_(False),
        )).all()
    }
    grade_record_rows = []
    for task in hist_tasks:
        gt_id = grade_task_by_tt[int(task.id)]
        for stu in rosters[int(task.class_id)]:
            grade = grade_lookup.get((int(stu.id), task.course_name))
            if grade is None:
                raise RuntimeError(f"13B 成绩回链缺失 student={stu.id} course={task.course_name}")
            total = int(grade.score) if grade.score is not None else 0
            usual = min(100, total + 9)
            final = max(0, total - 4)
            grade_record_rows.append({
                "tenant_id": tenant_id, "task_id": gt_id, "student_id": int(stu.id),
                "usual_score": usual, "final_score": final, "total_score": total,
                "pass_status": grade.pass_status,
                "acad_grade_id": int(grade.id), "source": "PUBLISH",
                "version_no": 1, "exception_flag": "NORMAL",
            })
    if len(grade_record_rows) != EXPECTED_GRADE_RECORDS:
        raise RuntimeError(f"13B 成绩明细数量异常: {len(grade_record_rows)}")
    _bulk_insert(db, AaGradeRecord, grade_record_rows, chunk_size=2000)

    # 历史期末考务：每个教学任务一个考场，每名学生有座位；不伪造大量违纪事故。
    exam_batch = AaExamBatch(
        tenant_id=tenant_id,
        term_id=term_by_code["2025-2026-2"],
        batch_name="2025-2026学年第二学期期末考试",
        exam_type="FINAL", exam_week_start=17, exam_week_end=18,
        published_at=datetime(2026, 6, 10, 9, 0), status="FINISHED",
    )
    db.add(exam_batch)
    db.flush()
    exam_course_rows = []
    college_by_major = {int(m.id): int(m.college_id) for m in org["majors"]}
    class_by_id = {int(c.id): c for c in org["classes"]}
    for idx, task in enumerate(hist_tasks):
        cls = class_by_id[int(task.class_id)]
        exam_day = datetime(2026, 6, 22) + timedelta(days=idx % 10)
        exam_course_rows.append({
            "tenant_id": tenant_id, "batch_id": int(exam_batch.id),
            "teaching_task_id": int(task.id), "course_id": int(task.course_id),
            "course_name": task.course_name, "class_id": int(task.class_id),
            "class_name": cls.class_name, "college_id": college_by_major[int(cls.major_id)],
            "teacher_key": task.teacher_key, "teacher_name": task.teacher_name,
            "expected_students": len(rosters[int(task.class_id)]),
            "exam_date": exam_day.strftime("%Y-%m-%d"),
            "start_time": "09:00" if idx % 2 == 0 else "14:30",
            "end_time": "10:40" if idx % 2 == 0 else "16:10",
            "duration_minutes": 100, "status": "CONFIRMED",
        })
    _bulk_insert(db, AaExamCourse, exam_course_rows, chunk_size=500)
    db.flush()
    exam_courses = list(db.scalars(select(AaExamCourse).where(
        AaExamCourse.tenant_id == tenant_id,
        AaExamCourse.batch_id == exam_batch.id,
        AaExamCourse.is_deleted.is_(False),
    ).order_by(AaExamCourse.id)).all())
    task_by_id = {int(t.id): t for t in hist_tasks}
    room_rows = []
    for idx, ec in enumerate(exam_courses):
        classroom = classrooms[idx % len(classrooms)]
        room_rows.append({
            "tenant_id": tenant_id, "exam_course_id": int(ec.id), "room_seq": 1,
            "classroom_text": classroom.room_name, "capacity": 80,
            "planned_count": int(ec.expected_students or 0), "seat_mode": "SEQUENTIAL",
            "source": "MANUAL", "status": "ACTIVE",
        })
    _bulk_insert(db, AaExamRoom, room_rows, chunk_size=500)
    db.flush()
    rooms = list(db.scalars(select(AaExamRoom).where(
        AaExamRoom.tenant_id == tenant_id,
        AaExamRoom.is_deleted.is_(False),
    ).order_by(AaExamRoom.id)).all())
    room_by_course = {int(r.exam_course_id): r for r in rooms}

    seat_rows = []
    invigilator_rows = []
    for idx, ec in enumerate(exam_courses):
        task = task_by_id[int(ec.teaching_task_id)]
        room = room_by_course[int(ec.id)]
        for seat, stu in enumerate(rosters[int(task.class_id)], 1):
            seat_rows.append({
                "tenant_id": tenant_id, "exam_room_id": int(room.id), "exam_course_id": int(ec.id),
                "student_id": int(stu.id), "student_no": stu.student_no,
                "student_name": stu.real_name, "seat_no": seat,
                "admission_no": f"{ec.id}{seat:03d}", "attendance_status": "PRESENT",
            })
        invigilator = teachers[(idx + 400) % len(teachers)]
        invigilator_rows.append({
            "tenant_id": tenant_id, "exam_room_id": int(room.id),
            "teacher_key": invigilator.login_name, "teacher_name": invigilator.real_name,
            "role": "CHIEF", "confirm_status": "CONFIRMED",
        })
    _bulk_insert(db, AaExamRoomStudent, seat_rows, chunk_size=2000)
    _bulk_insert(db, AaExamInvigilator, invigilator_rows, chunk_size=500)
    db.commit()
    return {
        "teachingTaskBatches": 2,
        "historicalTasks": len(hist_task_rows),
        "nextTermTasks": len(next_task_rows),
        "scheduleBatches": 2,
        "scheduleItems": len(schedule_rows),
        "gradeTasks": len(grade_task_rows),
        "gradeRecords": len(grade_record_rows),
        "examBatches": 1,
        "examCourses": len(exam_course_rows),
        "examSeats": len(seat_rows),
        "invigilators": len(invigilator_rows),
    }


def validate_academic_affairs_facts(db, tenant_id: int) -> dict:
    from app.models import (
        AaClassroom, AaCourse, AaExamCourse, AaExamRoomStudent, AaGradeRecord,
        AaGradeTask, AaProgram, AaProgramCourse, AaRegistration, AaScheduleItem,
        AaTeachingTask, AaTerm, AaTimeSlot,
    )

    def count(model, *conditions) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            *conditions,
        )) or 0)

    report = {
        "terms": count(AaTerm, AaTerm.is_deleted.is_(False)),
        "timeSlots": count(AaTimeSlot, AaTimeSlot.is_deleted.is_(False)),
        "classrooms": count(AaClassroom, AaClassroom.is_deleted.is_(False)),
        "courses": count(AaCourse, AaCourse.is_deleted.is_(False)),
        "programs": count(AaProgram, AaProgram.is_deleted.is_(False)),
        "programCourses": count(AaProgramCourse, AaProgramCourse.is_deleted.is_(False)),
        "registrations": count(AaRegistration, AaRegistration.is_deleted.is_(False)),
        "teachingTasks": count(AaTeachingTask, AaTeachingTask.is_deleted.is_(False)),
        "scheduleItems": count(AaScheduleItem, AaScheduleItem.is_deleted.is_(False)),
        "gradeTasks": count(AaGradeTask, AaGradeTask.is_deleted.is_(False)),
        "gradeRecords": count(AaGradeRecord, AaGradeRecord.is_deleted.is_(False)),
        "examCourses": count(AaExamCourse, AaExamCourse.is_deleted.is_(False)),
        "examSeats": count(AaExamRoomStudent, AaExamRoomStudent.is_deleted.is_(False)),
    }
    expected = {
        "terms": EXPECTED_TERMS,
        "timeSlots": EXPECTED_TIME_SLOTS,
        "classrooms": EXPECTED_CLASSROOMS,
        "courses": EXPECTED_COURSES,
        "programs": EXPECTED_PROGRAMS,
        "programCourses": EXPECTED_PROGRAM_COURSES,
        "registrations": EXPECTED_REGISTRATIONS,
        "teachingTasks": EXPECTED_TASKS,
        "scheduleItems": EXPECTED_SCHEDULE_ITEMS,
        "gradeTasks": EXPECTED_GRADE_TASKS,
        "gradeRecords": EXPECTED_GRADE_RECORDS,
        "examCourses": EXPECTED_EXAM_COURSES,
        "examSeats": EXPECTED_EXAM_SEATS,
    }
    mismatch = {k: {"expected": expected[k], "actual": report[k]} for k in expected if report[k] != expected[k]}
    if mismatch:
        raise RuntimeError(f"20K 13B 教务数据验收失败: {mismatch}")

    # 强约束：当前学期必须只有 2026-2027-1 一条，且 2026 级不能被伪造成已注册。
    from app.models import AaRegistrationBatch
    current_terms = count(AaTerm, AaTerm.is_current.is_(True), AaTerm.is_deleted.is_(False))
    if current_terms != 1:
        raise RuntimeError(f"教务当前学期口径错误: {current_terms}")
    incoming_batch = db.scalars(select(AaRegistrationBatch).where(
        AaRegistrationBatch.tenant_id == tenant_id,
        AaRegistrationBatch.batch_name == "2026级入学注册资格核验",
        AaRegistrationBatch.is_deleted.is_(False),
    )).one()
    incoming_registered = count(
        AaRegistration,
        AaRegistration.batch_id == incoming_batch.id,
        AaRegistration.status == "REGISTERED",
        AaRegistration.is_deleted.is_(False),
    )
    if incoming_registered != 0:
        raise RuntimeError(f"2026级在 2026-08-13 被错误标记已注册: {incoming_registered}")
    report["incomingRegisteredBeforeSchool"] = incoming_registered
    report["passed"] = True
    return report


def seed_school_academic_affairs_20k(db, tenant_id: int) -> dict:
    org = _org(db, tenant_id)
    base = _seed_terms_slots_resources(db, tenant_id)
    curriculum = _seed_courses_programs(db, tenant_id, org)
    registration = _seed_registration(db, tenant_id, org, base["termByCode"])
    operations = _seed_tasks_schedules_grades_exams(
        db, tenant_id, org, base["termByCode"], curriculum["courseByCode"],
    )
    result = {
        "base": {k: v for k, v in base.items() if k != "termByCode"},
        "curriculum": {k: v for k, v in curriculum.items() if k != "courseByCode"},
        "registration": registration,
        "operations": operations,
    }
    result["validation"] = validate_academic_affairs_facts(db, tenant_id)
    return result
