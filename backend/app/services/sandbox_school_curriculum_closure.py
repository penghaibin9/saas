"""sandbox-school · 三年制 140 学分培养方案与历史教学闭环。

这是 standard-20k 专属的数据治理层，不修改生产教务写链：
- 把课程库扩成真实三年制职业院校规模：14 门公共课 + 每专业 23 门专业/实践课；
- 96 套培养方案每套 37 门课程、140 学分，含学分结构、毕业要求和集中实践；
- 2025-2026-2 补齐 2024/2025 两届真实教学闭环：1024 教学任务、1024 课表项、
  1024 成绩任务、52000 成绩明细、1024 考试课程；
- 历史成绩仍回链既有 t_acad_grade，不建立第二套成绩真值。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.services.sandbox_school_master_seed import _bulk_insert
from app.services.sandbox_school_professional_catalog import professional_profile
from app.services.sandbox_school_professional_reconcile import ADVANCED_MAJOR_COURSE_LABELS

EXPECTED_COURSES_FINAL = 750
EXPECTED_PROGRAMS = 96
EXPECTED_PROGRAM_COURSES_FINAL = 3552
EXPECTED_GRADUATION_REQUIREMENTS = 384
EXPECTED_PRACTICE_SEGMENTS = 576
EXPECTED_HISTORICAL_TASKS_FINAL = 1024
EXPECTED_HISTORICAL_GRADE_RECORDS_FINAL = 52_000
EXPECTED_HISTORICAL_EXAM_COURSES_FINAL = 1024
EXPECTED_TOTAL_TASKS_FINAL = 1792
EXPECTED_TOTAL_SCHEDULE_ITEMS_FINAL = 1792

PUBLIC_EXPANSION = (
    ("PUB005", "毛泽东思想和中国特色社会主义理论体系概论", 3.0),
    ("PUB006", "习近平新时代中国特色社会主义思想概论", 3.0),
    ("PUB007", "形势与政策", 1.0),
    ("PUB008", "心理健康教育", 2.0),
    ("PUB009", "职业生涯规划", 2.0),
    ("PUB010", "创新创业基础", 2.0),
    ("PUB011", "劳动教育", 2.0),
    ("PUB012", "军事理论", 2.0),
    ("PUB013", "大学语文", 3.0),
    ("PUB014", "美育与艺术素养", 2.0),
)

MAJOR_EXTENSION_LABELS = (
    "技术标准与规范",
    "质量控制与改进",
    "数字化工具应用",
    "项目管理与协作",
    "安全生产与职业健康",
    "企业案例分析",
    "技术创新实践",
    "岗位综合能力",
)

PRACTICE_LABELS = (
    ("认识实习", 6.0, "COGNITION_INTERNSHIP", 2.0),
    ("课程设计", 6.0, "COURSE_DESIGN", 2.0),
    ("专业综合实训", 8.0, "COURSE_DESIGN", 3.0),
    ("生产实习", 8.0, "PRODUCTION_INTERNSHIP", 4.0),
    ("岗位实习", 10.0, "POST_INTERNSHIP", 18.0),
    ("毕业设计", 8.0, "GRADUATION_PROJECT", 8.0),
)

CREDIT_STRUCTURE = (
    ("PUBLIC_BASIC", 30.0),
    ("MAJOR_CORE", 64.0),
    ("PRACTICE", 46.0),
)


def _major_rows(db, tenant_id: int):
    from app.models import Major

    rows = list(db.execute(select(Major.id, Major.code, Major.major_name, Major.college_id).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.code)).all())
    if len(rows) != 32:
        raise RuntimeError(f"完整培养方案专业基数异常 expected=32 actual={len(rows)}")
    return rows


def _ensure_course_catalog(db, tenant_id: int) -> dict:
    from app.models import AaCourse

    majors = _major_rows(db, tenant_id)
    existing = {
        str(row.course_code): row
        for row in db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == tenant_id,
            AaCourse.is_deleted.is_(False),
        )).all()
    }

    public_rows = []
    for code, name, credit in PUBLIC_EXPANSION:
        if code in existing:
            continue
        hours = int(credit * 16)
        public_rows.append({
            "tenant_id": tenant_id,
            "course_code": code,
            "course_name": name,
            "category": "PUBLIC_BASIC",
            "nature": "REQUIRED",
            "credit": credit,
            "hours_total": hours,
            "hours_theory": hours,
            "hours_practice": 0,
            "hours_experiment": 0,
            "hours_computer": 0,
            "exam_mode": "CHECK" if code in {"PUB007", "PUB008", "PUB011", "PUB014"} else "EXAM",
            "is_core": code in {"PUB005", "PUB006"},
            "is_all_major": True,
            "version": 1,
            "status": "ENABLED",
            "description": "全校统一公共基础课程，纳入三年制高职人才培养方案。",
        })
    _bulk_insert(db, AaCourse, public_rows, chunk_size=200)
    db.flush()

    major_course_rows = []
    for major in majors:
        profile = professional_profile(str(major.major_name))
        # 07-09 承接已经发生的历史二年级课程；10-17 是后续专业拓展；18-23 为实践课程。
        advanced_names = [f"{major.major_name}{label}" for label in ADVANCED_MAJOR_COURSE_LABELS]
        extension_names = [f"{major.major_name}{label}" for label in MAJOR_EXTENSION_LABELS]
        practice_names = [f"{major.major_name}{label}" for label, _credit, _kind, _weeks in PRACTICE_LABELS]
        definitions = []
        for offset, name in enumerate(advanced_names, 7):
            definitions.append((offset, name, 4.0, "MAJOR_CORE", "REQUIRED"))
        for offset, name in enumerate(extension_names, 10):
            definitions.append((offset, name, 4.0, "MAJOR_CORE", "REQUIRED"))
        for offset, ((label, credit, _kind, _weeks), name) in enumerate(zip(PRACTICE_LABELS, practice_names), 18):
            definitions.append((offset, name, credit, "PRACTICE", "REQUIRED"))

        for suffix, name, credit, category, nature in definitions:
            code = f"{major.code}-{suffix:02d}"
            if code in existing:
                continue
            hours = int(credit * 16)
            is_practice = category == "PRACTICE"
            major_course_rows.append({
                "tenant_id": tenant_id,
                "course_code": code,
                "course_name": name,
                "category": category,
                "nature": nature,
                "credit": credit,
                "hours_total": hours,
                "hours_theory": 0 if is_practice else hours // 2,
                "hours_practice": hours if is_practice else hours - hours // 2,
                "hours_experiment": 0,
                "hours_computer": 0,
                "exam_mode": "CHECK" if is_practice else "EXAM",
                "owner_college_id": int(major.college_id),
                "is_core": category == "MAJOR_CORE" and suffix <= 17,
                "applicable_majors_json": json.dumps([int(major.id)]),
                "is_all_major": False,
                "version": 1,
                "status": "ENABLED",
                "description": f"{major.major_name}三年制人才培养方案正式课程。",
            })
    _bulk_insert(db, AaCourse, major_course_rows, chunk_size=1000)
    db.commit()

    total = int(db.scalar(select(func.count()).select_from(AaCourse).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.is_deleted.is_(False),
    )) or 0)
    if total != EXPECTED_COURSES_FINAL:
        raise RuntimeError(f"完整课程库数量异常 expected={EXPECTED_COURSES_FINAL} actual={total}")
    return {"courses": total, "addedPublic": len(public_rows), "addedMajor": len(major_course_rows)}


def _term_assignments(grade: str, public_codes: list[str], major_codes: list[str]) -> dict[str, int]:
    all_codes = list(public_codes) + list(major_codes)
    if len(all_codes) != 37:
        raise RuntimeError(f"培养方案课程数必须为37，actual={len(all_codes)}")

    if grade == "2025":
        reserved = {
            major_codes[0]: 2, major_codes[1]: 2, major_codes[2]: 2, major_codes[3]: 2,
            major_codes[4]: 3, major_codes[5]: 3,
            "PUB002": 3, "PUB003": 3,
        }
        allowed = [1, 4, 5, 6]
    elif grade == "2024":
        reserved = {
            major_codes[5]: 4, major_codes[6]: 4, major_codes[7]: 4, major_codes[8]: 4,
        }
        # 2026秋进入岗位实习期，第5学期不再制造普通课堂教学任务。
        allowed = [1, 2, 3, 6]
    elif grade == "2026":
        reserved = {major_codes[0]: 1, "PUB004": 1}
        allowed = [2, 3, 4, 5, 6]
    else:
        raise RuntimeError(f"未知年级培养方案: {grade}")

    result = dict(reserved)
    cursor = 0
    for code in all_codes:
        if code in result:
            continue
        result[code] = allowed[cursor % len(allowed)]
        cursor += 1
    return result


def _rebuild_programs(db, tenant_id: int) -> dict:
    from app.models import (
        AaCourse,
        AaProgram,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
    )

    majors = _major_rows(db, tenant_id)
    courses = list(db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.status == "ENABLED",
        AaCourse.is_deleted.is_(False),
    )).all())
    course_by_code = {str(row.course_code): row for row in courses}
    public_codes = [f"PUB{i:03d}" for i in range(1, 15)]
    if any(code not in course_by_code for code in public_codes):
        raise RuntimeError("公共课程库不完整，无法重建培养方案")

    program_rows = list(db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == tenant_id,
        AaProgram.is_deleted.is_(False),
    ).order_by(AaProgram.major_id, AaProgram.grade_year)).all())
    if len(program_rows) != EXPECTED_PROGRAMS:
        raise RuntimeError(f"培养方案主档异常 expected={EXPECTED_PROGRAMS} actual={len(program_rows)}")

    old_program_ids = [int(row.id) for row in program_rows]
    db.execute(delete(AaProgramCourse).where(
        AaProgramCourse.tenant_id == tenant_id,
        AaProgramCourse.program_id.in_(old_program_ids),
    ))
    db.execute(delete(AaProgramGraduationRequirement).where(
        AaProgramGraduationRequirement.tenant_id == tenant_id,
        AaProgramGraduationRequirement.program_id.in_(old_program_ids),
    ))
    db.execute(delete(AaProgramPracticeSegment).where(
        AaProgramPracticeSegment.tenant_id == tenant_id,
        AaProgramPracticeSegment.program_id.in_(old_program_ids),
    ))
    db.flush()

    major_by_id = {int(row.id): row for row in majors}
    program_course_rows = []
    requirement_rows = []
    practice_rows = []
    for program in program_rows:
        major = major_by_id[int(program.major_id)]
        grade = str(program.grade_year)
        major_codes = [f"{major.code}-{i:02d}" for i in range(1, 24)]
        if any(code not in course_by_code for code in major_codes):
            missing = [code for code in major_codes if code not in course_by_code]
            raise RuntimeError(f"专业课程库缺失 major={major.major_name} missing={missing}")
        assignment = _term_assignments(grade, public_codes, major_codes)
        program.total_credits = Decimal("140.0")
        program.requirement_json = json.dumps({
            "scheme": "THREE_YEAR_HIGHER_VOCATIONAL_140",
            "creditStructure": [
                {"module": module, "creditTarget": credit}
                for module, credit in CREDIT_STRUCTURE
            ],
            "practiceNote": "集中实践课程学分已计入PRACTICE模块，实践环节表仅记录周数和组织方式，不重复计学分。",
        }, ensure_ascii=False)

        for code in public_codes + major_codes:
            course = course_by_code[code]
            if code.startswith("PUB"):
                module = "PUBLIC_BASIC"
            else:
                suffix = int(code.rsplit("-", 1)[1])
                module = "PRACTICE" if suffix >= 18 else "MAJOR_CORE"
            program_course_rows.append({
                "tenant_id": tenant_id,
                "program_id": int(program.id),
                "course_id": int(course.id),
                "course_name": course.course_name,
                "open_term_no": int(assignment[code]),
                "module": module,
                "credit_snapshot": float(course.credit),
            })

        requirements = (
            ("KNOWLEDGE", f"掌握{major.major_name}专业基础理论、技术标准和岗位知识体系。"),
            ("ABILITY", f"能够完成{major.major_name}典型岗位任务、项目实施与质量改进。"),
            ("QUALITY", "具备职业道德、团队协作、安全意识、数字素养和持续学习能力。"),
            ("CERTIFICATE", f"鼓励取得与{major.major_name}相关的职业技能等级证书或行业认证。"),
        )
        for order, (category, content) in enumerate(requirements, 1):
            requirement_rows.append({
                "tenant_id": tenant_id,
                "program_id": int(program.id),
                "category": category,
                "content": content,
                "sort_order": order,
                "status": "ACTIVE",
            })

        for order, (label, credit, segment_type, weeks) in enumerate(PRACTICE_LABELS, 1):
            suffix = 17 + order
            practice_rows.append({
                "tenant_id": tenant_id,
                "program_id": int(program.id),
                "segment_name": f"{major.major_name}{label}",
                "segment_type": segment_type,
                "open_term_no": int(assignment[f"{major.code}-{suffix:02d}"]),
                "weeks": weeks,
                "credit": credit,
                "org_mode": "DISTRIBUTED" if segment_type == "POST_INTERNSHIP" else "CENTRALIZED",
                "location": "校企合作实践基地" if "INTERNSHIP" in segment_type else "校内实训基地",
                "assessment_mode": "CHECK",
                "sort_order": order,
                "status": "ACTIVE",
            })

    _bulk_insert(db, AaProgramCourse, program_course_rows, chunk_size=1500)
    _bulk_insert(db, AaProgramGraduationRequirement, requirement_rows, chunk_size=1000)
    _bulk_insert(db, AaProgramPracticeSegment, practice_rows, chunk_size=1000)
    db.commit()
    return {
        "programs": len(program_rows),
        "programCourses": len(program_course_rows),
        "graduationRequirements": len(requirement_rows),
        "practiceSegments": len(practice_rows),
    }


def prepare_school_curriculum_20k(db, tenant_id: int) -> dict:
    catalog = _ensure_course_catalog(db, tenant_id)
    programs = _rebuild_programs(db, tenant_id)
    validation = validate_school_curriculum_20k(db, tenant_id)
    return {"catalog": catalog, "programs": programs, "validation": validation}


def validate_school_curriculum_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaCourse,
        AaProgram,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
    )

    def count(model, *where):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            model.is_deleted.is_(False),
            *where,
        )) or 0)

    report = {
        "courses": count(AaCourse),
        "programs": count(AaProgram),
        "programCourses": count(AaProgramCourse),
        "graduationRequirements": count(AaProgramGraduationRequirement, AaProgramGraduationRequirement.status == "ACTIVE"),
        "practiceSegments": count(AaProgramPracticeSegment, AaProgramPracticeSegment.status == "ACTIVE"),
    }
    expected = {
        "courses": EXPECTED_COURSES_FINAL,
        "programs": EXPECTED_PROGRAMS,
        "programCourses": EXPECTED_PROGRAM_COURSES_FINAL,
        "graduationRequirements": EXPECTED_GRADUATION_REQUIREMENTS,
        "practiceSegments": EXPECTED_PRACTICE_SEGMENTS,
    }
    mismatch = {k: {"expected": v, "actual": report[k]} for k, v in expected.items() if report[k] != v}
    if mismatch:
        raise RuntimeError(f"完整培养方案结构验收失败: {mismatch}")

    program_ids = list(db.scalars(select(AaProgram.id).where(
        AaProgram.tenant_id == tenant_id,
        AaProgram.is_deleted.is_(False),
    )))
    bad = []
    for program_id in program_ids:
        credit_sum = float(db.scalar(select(func.coalesce(func.sum(AaProgramCourse.credit_snapshot), 0)).where(
            AaProgramCourse.tenant_id == tenant_id,
            AaProgramCourse.program_id == int(program_id),
            AaProgramCourse.is_deleted.is_(False),
        )) or 0)
        course_count = count(AaProgramCourse, AaProgramCourse.program_id == int(program_id))
        if abs(credit_sum - 140.0) > 0.001 or course_count != 37:
            bad.append({"programId": str(program_id), "credits": credit_sum, "courses": course_count})
    if bad:
        raise RuntimeError(f"培养方案140学分/37课程不一致: {bad[:10]}")
    report["programsAt140Credits"] = len(program_ids)
    report["passed"] = True
    return report


def _historical_context(db, tenant_id: int) -> dict:
    from app.models import (
        AaClassroom,
        AaCourse,
        AaExamBatch,
        AaScheduleBatch,
        AaTeachingTaskBatch,
        AcademicGrade,
        AcademicStudent,
        Major,
        SchoolClass,
        StudentProfile,
        User,
    )

    task_batch = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == tenant_id,
        AaTeachingTaskBatch.batch_name == "2025-2026学年第二学期教学任务",
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).one()
    schedule_batch = db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == tenant_id,
        AaScheduleBatch.batch_name == "2025-2026学年第二学期正式课表",
        AaScheduleBatch.is_deleted.is_(False),
    )).one()
    exam_batch = db.scalars(select(AaExamBatch).where(
        AaExamBatch.tenant_id == tenant_id,
        AaExamBatch.batch_name == "2025-2026学年第二学期期末考试",
        AaExamBatch.is_deleted.is_(False),
    )).one()

    classes = list(db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == tenant_id,
        SchoolClass.grade.in_(("2024", "2025")),
        SchoolClass.class_status == "NORMAL",
        SchoolClass.is_deleted.is_(False),
    ).order_by(SchoolClass.grade, SchoolClass.class_code)).all())
    if len(classes) != 256:
        raise RuntimeError(f"历史教学行政班基数异常 expected=256 actual={len(classes)}")
    major_by_id = {
        int(row.id): row
        for row in db.scalars(select(Major).where(
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        ).all()
    }
    courses = {
        str(row.course_code): row
        for row in db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == tenant_id,
            AaCourse.status == "ENABLED",
            AaCourse.is_deleted.is_(False),
        )).all()
    }
    students = list(db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.grade.in_(("2024", "2025")),
        StudentProfile.is_deleted.is_(False),
    ).order_by(StudentProfile.class_id, StudentProfile.student_no)).all())
    rosters = defaultdict(list)
    for student in students:
        rosters[int(student.class_id)].append(student)
    if sum(len(value) for value in rosters.values()) != 13_000:
        raise RuntimeError("历史教学学生基数必须为13000")

    teachers = list(db.scalars(select(User).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_t%"),
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
    ).order_by(User.login_name)).all())
    if len(teachers) < 912:
        raise RuntimeError(f"历史教学教师池不足: {len(teachers)}")
    classrooms = list(db.execute(select(AaClassroom.id, AaClassroom.room_name).where(
        AaClassroom.tenant_id == tenant_id,
        AaClassroom.status == "AVAILABLE",
        AaClassroom.is_deleted.is_(False),
    ).order_by(AaClassroom.id)).all())
    if len(classrooms) < 256:
        raise RuntimeError(f"历史教学教室池不足: {len(classrooms)}")

    acad_to_student = {
        int(aid): int(sid)
        for aid, sid in db.execute(select(AcademicStudent.id, AcademicStudent.student_id).where(
            AcademicStudent.tenant_id == tenant_id,
            AcademicStudent.grade.in_(("2024", "2025")),
            AcademicStudent.is_deleted.is_(False),
        )).all()
    }
    grade_lookup = {}
    grade_count = 0
    for row in db.execute(select(
        AcademicGrade.id,
        AcademicGrade.acad_student_id,
        AcademicGrade.course_name,
        AcademicGrade.score,
        AcademicGrade.pass_status,
    ).where(
        AcademicGrade.tenant_id == tenant_id,
        AcademicGrade.term == "2025-2026-2",
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )).all():
        student_id = acad_to_student.get(int(row.acad_student_id))
        if student_id is None:
            continue
        grade_lookup[(student_id, str(row.course_name))] = row
        grade_count += 1
    if grade_count != EXPECTED_HISTORICAL_GRADE_RECORDS_FINAL:
        raise RuntimeError(f"历史AcademicGrade基数异常 expected=52000 actual={grade_count}")

    return {
        "taskBatch": task_batch,
        "scheduleBatch": schedule_batch,
        "examBatch": exam_batch,
        "classes": classes,
        "majorById": major_by_id,
        "courses": courses,
        "rosters": rosters,
        "teachers": teachers,
        "classrooms": classrooms,
        "gradeLookup": grade_lookup,
    }


def seed_historical_teaching_closure_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaExamCourse,
        AaExamInvigilator,
        AaExamRoom,
        AaExamRoomStudent,
        AaGradeRecord,
        AaGradeTask,
        AaScheduleItem,
        AaTeachingTask,
    )

    ctx = _historical_context(db, tenant_id)
    task_batch = ctx["taskBatch"]
    schedule_batch = ctx["scheduleBatch"]
    exam_batch = ctx["examBatch"]
    classes = ctx["classes"]
    courses = ctx["courses"]
    major_by_id = ctx["majorById"]
    rosters = ctx["rosters"]
    teachers = ctx["teachers"]
    classrooms = ctx["classrooms"]
    grade_lookup = ctx["gradeLookup"]

    existing_tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id == int(task_batch.id),
        AaTeachingTask.is_deleted.is_(False),
    )).all())
    by_key = {(int(row.course_id), int(row.class_id)): row for row in existing_tasks}

    missing_rows = []
    final_plan = []
    class_index = {int(cls.id): idx for idx, cls in enumerate(classes)}
    for cls in classes:
        major = major_by_id[int(cls.major_id)]
        suffixes = ("06", "07", "08", "09") if str(cls.grade) == "2024" else ("01", "02", "03", "04")
        for position, suffix in enumerate(suffixes):
            code = f"{major.code}-{suffix}"
            course = courses.get(code)
            if course is None:
                raise RuntimeError(f"历史教学缺正式课程: {code}")
            teacher_index = position * 256 + class_index[int(cls.id)]
            teacher = teachers[teacher_index % len(teachers)]
            key = (int(course.id), int(cls.id))
            task = by_key.get(key)
            values = {
                "course_id": int(course.id),
                "course_code": course.course_code,
                "course_name": course.course_name,
                "class_id": int(cls.id),
                "teaching_class_code": f"H-{cls.class_code}-{suffix}",
                "teaching_class_name": f"{cls.class_name}-{course.course_name}",
                "teacher_id": int(teacher.id),
                "teacher_key": teacher.login_name,
                "teacher_name": teacher.real_name,
                "expected_students": len(rosters[int(cls.id)]),
                "weekly_hours": 2,
                "total_hours": 36,
                "start_week": 1,
                "end_week": 18,
                "required_room_type": "MULTIMEDIA",
                "no_auto_schedule": False,
                "confirm_at": datetime(2026, 2, 12, 10, 0),
                "status": "READY",
            }
            if task is None:
                missing_rows.append({"tenant_id": tenant_id, "batch_id": int(task_batch.id), **values})
            else:
                for field, value in values.items():
                    setattr(task, field, value)
            final_plan.append((int(cls.id), int(course.id), position))
    _bulk_insert(db, AaTeachingTask, missing_rows, chunk_size=1000)
    db.commit()

    tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id == int(task_batch.id),
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.class_id, AaTeachingTask.course_id)).all())
    if len(tasks) != EXPECTED_HISTORICAL_TASKS_FINAL:
        raise RuntimeError(f"历史教学任务补齐失败 expected=1024 actual={len(tasks)}")
    task_by_key = {(int(row.class_id), int(row.course_id)): row for row in tasks}

    # 历史正式课表重建：256 个班各占一个稳定教室，四门课分布在周一至周四；
    # 同一时段教师索引不重复，避免班级/教师/教室 HARD 冲突。
    db.execute(delete(AaScheduleItem).where(
        AaScheduleItem.tenant_id == tenant_id,
        AaScheduleItem.batch_id == int(schedule_batch.id),
    ))
    schedule_batch.status = "PUBLISHED"
    schedule_rows = []
    for cls in classes:
        room = classrooms[class_index[int(cls.id)]]
        major = major_by_id[int(cls.major_id)]
        suffixes = ("06", "07", "08", "09") if str(cls.grade) == "2024" else ("01", "02", "03", "04")
        for position, suffix in enumerate(suffixes):
            course = courses[f"{major.code}-{suffix}"]
            task = task_by_key[(int(cls.id), int(course.id))]
            schedule_rows.append({
                "tenant_id": tenant_id,
                "batch_id": int(schedule_batch.id),
                "task_id": int(task.id),
                "course_id": int(course.id),
                "course_name": course.course_name,
                "class_id": int(cls.id),
                "class_name": task.teaching_class_name,
                "teacher_key": task.teacher_key,
                "teacher_name": task.teacher_name,
                "weekday": 1 + position,
                "slot_no": 1 + position * 2,
                "start_week": 1,
                "end_week": 18,
                "week_parity": "ALL",
                "classroom_id": int(room.id),
                "classroom_text": room.room_name,
                "status": "EFFECTIVE",
                "source": "AUTO",
            })
    _bulk_insert(db, AaScheduleItem, schedule_rows, chunk_size=1500)
    db.commit()

    # 成绩任务与明细完全从 t_acad_grade 回链重建，避免“补任务却另造成绩”。
    old_grade_tasks = list(db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == tenant_id,
        AaGradeTask.term_code == "2025-2026-2",
        AaGradeTask.is_deleted.is_(False),
    )).all())
    old_grade_task_ids = [int(row.id) for row in old_grade_tasks]
    if old_grade_task_ids:
        db.execute(delete(AaGradeRecord).where(
            AaGradeRecord.tenant_id == tenant_id,
            AaGradeRecord.task_id.in_(old_grade_task_ids),
        ))
        db.execute(delete(AaGradeTask).where(
            AaGradeTask.tenant_id == tenant_id,
            AaGradeTask.id.in_(old_grade_task_ids),
        ))
        db.flush()

    grade_task_rows = []
    for task in tasks:
        course = courses[str(task.course_code)]
        grade_task_rows.append({
            "tenant_id": tenant_id,
            "teaching_task_id": int(task.id),
            "term_id": int(task_batch.term_id),
            "term_code": "2025-2026-2",
            "course_id": int(course.id),
            "course_name": course.course_name,
            "class_id": int(task.class_id),
            "teacher_key": task.teacher_key,
            "credit": float(course.credit),
            "usual_ratio": 30,
            "midterm_ratio": 0,
            "final_ratio": 70,
            "pass_line": 60,
            "status": "PUBLISHED",
            "submitted_at": datetime(2026, 7, 1, 10, 0),
            "college_reviewed_at": datetime(2026, 7, 2, 9, 0),
            "academic_reviewed_at": datetime(2026, 7, 3, 9, 0),
            "publish_at": datetime(2026, 7, 4, 9, 0),
        })
    _bulk_insert(db, AaGradeTask, grade_task_rows, chunk_size=1000)
    db.flush()
    grade_task_by_tt = {
        int(teaching_task_id): int(grade_task_id)
        for grade_task_id, teaching_task_id in db.execute(select(
            AaGradeTask.id, AaGradeTask.teaching_task_id,
        ).where(
            AaGradeTask.tenant_id == tenant_id,
            AaGradeTask.term_code == "2025-2026-2",
            AaGradeTask.is_deleted.is_(False),
        )).all()
    }

    grade_record_rows = []
    for task in tasks:
        grade_task_id = grade_task_by_tt[int(task.id)]
        for student in rosters[int(task.class_id)]:
            grade = grade_lookup.get((int(student.id), str(task.course_name)))
            if grade is None:
                raise RuntimeError(f"历史成绩回链缺失 student={student.id} course={task.course_name}")
            total = int(grade.score or 0)
            grade_record_rows.append({
                "tenant_id": tenant_id,
                "task_id": grade_task_id,
                "student_id": int(student.id),
                "usual_score": min(100, total + 9),
                "final_score": max(0, total - 4),
                "total_score": total,
                "pass_status": grade.pass_status,
                "acad_grade_id": int(grade.id),
                "source": "PUBLISH",
                "version_no": 1,
                "exception_flag": "NORMAL",
            })
    if len(grade_record_rows) != EXPECTED_HISTORICAL_GRADE_RECORDS_FINAL:
        raise RuntimeError(f"历史成绩明细闭环失败 expected=52000 actual={len(grade_record_rows)}")
    _bulk_insert(db, AaGradeRecord, grade_record_rows, chunk_size=2000)
    db.commit()

    # 考试课程按最终 1024 教学任务重建；考场/考位随后由统一容量重排器生成。
    old_exam_courses = list(db.scalars(select(AaExamCourse).where(
        AaExamCourse.tenant_id == tenant_id,
        AaExamCourse.batch_id == int(exam_batch.id),
        AaExamCourse.is_deleted.is_(False),
    )).all())
    old_exam_course_ids = [int(row.id) for row in old_exam_courses]
    if old_exam_course_ids:
        room_ids = list(db.scalars(select(AaExamRoom.id).where(
            AaExamRoom.tenant_id == tenant_id,
            AaExamRoom.exam_course_id.in_(old_exam_course_ids),
        )))
        if room_ids:
            db.execute(delete(AaExamRoomStudent).where(
                AaExamRoomStudent.tenant_id == tenant_id,
                AaExamRoomStudent.exam_room_id.in_(room_ids),
            ))
            db.execute(delete(AaExamInvigilator).where(
                AaExamInvigilator.tenant_id == tenant_id,
                AaExamInvigilator.exam_room_id.in_(room_ids),
            ))
            db.execute(delete(AaExamRoom).where(
                AaExamRoom.tenant_id == tenant_id,
                AaExamRoom.id.in_(room_ids),
            ))
        db.execute(delete(AaExamCourse).where(
            AaExamCourse.tenant_id == tenant_id,
            AaExamCourse.id.in_(old_exam_course_ids),
        ))
        db.flush()

    class_by_id = {int(row.id): row for row in classes}
    exam_rows = []
    for idx, task in enumerate(tasks):
        cls = class_by_id[int(task.class_id)]
        major = major_by_id[int(cls.major_id)]
        day = datetime(2026, 6, 22) + timedelta(days=idx % 10)
        exam_rows.append({
            "tenant_id": tenant_id,
            "batch_id": int(exam_batch.id),
            "teaching_task_id": int(task.id),
            "course_id": int(task.course_id),
            "course_name": task.course_name,
            "class_id": int(task.class_id),
            "class_name": cls.class_name,
            "college_id": int(major.college_id),
            "teacher_key": task.teacher_key,
            "teacher_name": task.teacher_name,
            "expected_students": len(rosters[int(task.class_id)]),
            "exam_date": day.strftime("%Y-%m-%d"),
            "start_time": "09:00" if idx % 2 == 0 else "14:30",
            "end_time": "10:40" if idx % 2 == 0 else "16:10",
            "duration_minutes": 100,
            "status": "CONFIRMED",
        })
    _bulk_insert(db, AaExamCourse, exam_rows, chunk_size=1000)
    db.commit()

    return validate_historical_teaching_closure_20k(db, tenant_id)


def validate_historical_teaching_closure_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaExamCourse,
        AaGradeRecord,
        AaGradeTask,
        AaScheduleItem,
        AaTeachingTask,
        AaTeachingTaskBatch,
    )

    batch = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == tenant_id,
        AaTeachingTaskBatch.batch_name == "2025-2026学年第二学期教学任务",
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).one()
    tasks = int(db.scalar(select(func.count()).select_from(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.batch_id == int(batch.id),
        AaTeachingTask.status == "READY",
        AaTeachingTask.is_deleted.is_(False),
    )) or 0)
    grade_tasks = int(db.scalar(select(func.count()).select_from(AaGradeTask).where(
        AaGradeTask.tenant_id == tenant_id,
        AaGradeTask.term_code == "2025-2026-2",
        AaGradeTask.status == "PUBLISHED",
        AaGradeTask.is_deleted.is_(False),
    )) or 0)
    grade_task_ids = list(db.scalars(select(AaGradeTask.id).where(
        AaGradeTask.tenant_id == tenant_id,
        AaGradeTask.term_code == "2025-2026-2",
        AaGradeTask.is_deleted.is_(False),
    )))
    grade_records = int(db.scalar(select(func.count()).select_from(AaGradeRecord).where(
        AaGradeRecord.tenant_id == tenant_id,
        AaGradeRecord.task_id.in_(grade_task_ids or [0]),
        AaGradeRecord.is_deleted.is_(False),
    )) or 0)
    schedule_items = int(db.scalar(select(func.count()).select_from(AaScheduleItem).where(
        AaScheduleItem.tenant_id == tenant_id,
        AaScheduleItem.task_id.in_(select(AaTeachingTask.id).where(
            AaTeachingTask.tenant_id == tenant_id,
            AaTeachingTask.batch_id == int(batch.id),
            AaTeachingTask.is_deleted.is_(False),
        )),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    )) or 0)
    exam_courses = int(db.scalar(select(func.count()).select_from(AaExamCourse).where(
        AaExamCourse.tenant_id == tenant_id,
        AaExamCourse.teaching_task_id.in_(select(AaTeachingTask.id).where(
            AaTeachingTask.tenant_id == tenant_id,
            AaTeachingTask.batch_id == int(batch.id),
            AaTeachingTask.is_deleted.is_(False),
        )),
        AaExamCourse.status == "CONFIRMED",
        AaExamCourse.is_deleted.is_(False),
    )) or 0)
    report = {
        "historicalTasks": tasks,
        "historicalScheduleItems": schedule_items,
        "historicalGradeTasks": grade_tasks,
        "historicalGradeRecords": grade_records,
        "historicalExamCourses": exam_courses,
    }
    expected = {
        "historicalTasks": EXPECTED_HISTORICAL_TASKS_FINAL,
        "historicalScheduleItems": EXPECTED_HISTORICAL_TASKS_FINAL,
        "historicalGradeTasks": EXPECTED_HISTORICAL_TASKS_FINAL,
        "historicalGradeRecords": EXPECTED_HISTORICAL_GRADE_RECORDS_FINAL,
        "historicalExamCourses": EXPECTED_HISTORICAL_EXAM_COURSES_FINAL,
    }
    mismatch = {k: {"expected": v, "actual": report[k]} for k, v in expected.items() if report[k] != v}
    if mismatch:
        raise RuntimeError(f"历史教学闭环验收失败: {mismatch}")
    report["passed"] = True
    return report


def validate_school_academic_final_20k(db, tenant_id: int) -> dict:
    """完整演示校最终 13B 规模合同；区别于基础 seed 的 20K 快速合同。"""
    from app.models import (
        AaCourse,
        AaExamCourse,
        AaExamRoomStudent,
        AaGradeRecord,
        AaGradeTask,
        AaProgram,
        AaProgramBinding,
        AaProgramCourse,
        AaRegistration,
        AaScheduleItem,
        AaTeachingTask,
    )

    def count(model, *where):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            model.is_deleted.is_(False),
            *where,
        )) or 0)

    report = {
        "courses": count(AaCourse),
        "programs": count(AaProgram),
        "programBindings": count(AaProgramBinding, AaProgramBinding.status == "ACTIVE"),
        "programCourses": count(AaProgramCourse),
        "registrations": count(AaRegistration),
        "teachingTasks": count(AaTeachingTask),
        "scheduleItems": count(AaScheduleItem),
        "gradeTasks": count(AaGradeTask),
        "gradeRecords": count(AaGradeRecord),
        "examCourses": count(AaExamCourse),
        "examSeats": count(AaExamRoomStudent),
    }
    expected = {
        "courses": EXPECTED_COURSES_FINAL,
        "programs": EXPECTED_PROGRAMS,
        "programBindings": EXPECTED_PROGRAMS,
        "programCourses": EXPECTED_PROGRAM_COURSES_FINAL,
        "registrations": 33_000,
        "teachingTasks": EXPECTED_TOTAL_TASKS_FINAL,
        "scheduleItems": EXPECTED_TOTAL_SCHEDULE_ITEMS_FINAL,
        "gradeTasks": EXPECTED_HISTORICAL_TASKS_FINAL,
        "gradeRecords": EXPECTED_HISTORICAL_GRADE_RECORDS_FINAL,
        "examCourses": EXPECTED_HISTORICAL_EXAM_COURSES_FINAL,
        "examSeats": EXPECTED_HISTORICAL_GRADE_RECORDS_FINAL,
    }
    mismatch = {k: {"expected": v, "actual": report[k]} for k, v in expected.items() if report[k] != v}
    if mismatch:
        raise RuntimeError(f"20K 完整教务终态验收失败: {mismatch}")
    report["passed"] = True
    return report
