"""20K 售前学校 · 专业语义对账。

在主数据、六域、13B 教务事实生成后执行：
- 把 32 专业的 192 门专业课从泛化占位名改为专业核心课程；
- 把 80 家合作企业、160 个岗位与 2024 级学生专业严格对齐；
- 把 96 名毕设导师、1,120 个题目、6,400 名毕业年级学生按专业重新配对；
- 保留既有实习状态、打卡、周报、风险事实，不篡改业务过程，只修专业语义关系。

所有内容均为确定性虚构售前数据，只允许作用于 sandbox-school。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select

from app.services.sandbox_school_blueprint import (
    COLLEGE_MAJOR_BLUEPRINT,
    MAJOR_CLASS_COUNTS_PER_GRADE,
)
from app.services.sandbox_school_professional_catalog import professional_profile

COMPANY_CITIES = ("长沙", "株洲", "湘潭", "岳阳", "衡阳", "常德", "郴州", "广州", "深圳", "杭州")
COMPANY_BRANDS = ("华拓", "科创", "智联", "新程", "卓越", "湘江", "云启", "远航")
LEGACY_MAJOR_COURSE_LABELS = (
    "专业导论", "基础实训", "核心技能", "项目实践",
    "综合实训", "岗位技能", "综合项目", "生产性实训", "专业拓展",
)
ADVANCED_MAJOR_COURSE_LABELS = ("企业综合项目", "生产性实训", "专业拓展实践")
TOPIC_CATEGORIES = ("应用设计", "岗位实践", "流程优化", "技术方案")


def _major_specs() -> list[tuple[str, str, str]]:
    """(major_code, college_name, major_name)，顺序与主数据蓝图严格一致。"""
    out: list[tuple[str, str, str]] = []
    for college_code, college_name, majors in COLLEGE_MAJOR_BLUEPRINT:
        for index, major_name in enumerate(majors, 1):
            out.append((f"{college_code}M{index:02d}", college_name, major_name))
    return out


def _company_quota() -> dict[str, int]:
    """80 家合作企业：每专业至少 2 家，招生规模前 16 个专业增加到 3 家。"""
    specs = _major_specs()
    quota = {major_name: 2 for _code, _college, major_name in specs}
    ranked = sorted(
        specs,
        key=lambda item: (-MAJOR_CLASS_COUNTS_PER_GRADE[item[0]], item[0]),
    )
    for _code, _college, major_name in ranked[:16]:
        quota[major_name] += 1
    assert sum(quota.values()) == 80
    return quota


def _even_guiding_targets(students_by_major: dict[str, list]) -> dict[str, int]:
    """约 35% 学生进入前期指导；每专业保持偶数，确保 2 人/题且全校恰好 2,240 人。"""
    targets: dict[str, int] = {}
    for _code, _college, major_name in _major_specs():
        count = len(students_by_major[major_name])
        target = round(count * 0.35)
        if target % 2:
            target -= 1
        targets[major_name] = target

    expected = 2240
    deficit = expected - sum(targets.values())
    ordered = sorted(
        _major_specs(),
        key=lambda item: (-len(students_by_major[item[2]]), item[0]),
    )
    direction = 2 if deficit > 0 else -2
    while deficit != 0:
        changed = False
        for _code, _college, major_name in ordered:
            candidate = targets[major_name] + direction
            if candidate < 0 or candidate > len(students_by_major[major_name]):
                continue
            targets[major_name] = candidate
            deficit -= direction
            changed = True
            if deficit == 0:
                break
        if not changed:
            raise RuntimeError(f"毕设前期指导人数分配失败 deficit={deficit}")
    assert sum(targets.values()) == expected
    assert all(value % 2 == 0 for value in targets.values())
    return targets


def _course_name(profile, label_index: int, major_name: str) -> str:
    if label_index < len(profile.core_courses):
        return profile.core_courses[label_index]
    return f"{major_name}{ADVANCED_MAJOR_COURSE_LABELS[label_index - len(profile.core_courses)]}"


def _professionalize_academic(db, tenant_id: int) -> dict:
    from app.models import AaCourse, AcademicGrade, AcademicStudent, Major

    majors = list(db.execute(select(Major.id, Major.code, Major.major_name).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.code)).all())
    major_name_by_code = {row.code: row.major_name for row in majors}

    aa_updated = 0
    aa_courses = list(db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.is_all_major.is_(False),
        AaCourse.is_deleted.is_(False),
    )).all())
    for course in aa_courses:
        code = str(course.course_code or "")
        if "-" not in code:
            continue
        major_code, suffix = code.rsplit("-", 1)
        major_name = major_name_by_code.get(major_code)
        if not major_name or not suffix.isdigit():
            continue
        index = int(suffix) - 1
        profile = professional_profile(major_name)
        if 0 <= index < len(profile.core_courses):
            course.course_name = profile.core_courses[index]
            aa_updated += 1

    academic_major_by_id = {
        int(aid): major_name
        for aid, major_name in db.execute(select(AcademicStudent.id, AcademicStudent.major_name).where(
            AcademicStudent.tenant_id == tenant_id,
            AcademicStudent.is_deleted.is_(False),
        )).all()
    }
    grade_updated = 0
    grades = list(db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == tenant_id,
        AcademicGrade.is_deleted.is_(False),
    )).all())
    for row in grades:
        major_name = academic_major_by_id.get(int(row.acad_student_id))
        if not major_name:
            continue
        current = str(row.course_name or "")
        label_index = next(
            (
                idx for idx, label in enumerate(LEGACY_MAJOR_COURSE_LABELS)
                if current == f"{major_name}{label}"
            ),
            None,
        )
        if label_index is None:
            continue
        row.course_name = _course_name(professional_profile(major_name), label_index, major_name)
        grade_updated += 1

    db.commit()
    return {"aaMajorCourses": aa_updated, "academicGradeNames": grade_updated}


def _professionalize_internship(db, tenant_id: int) -> dict:
    from app.models import EmpCompany, InternshipPosition, InternshipRecord, Major, StudentProfile

    companies = list(db.scalars(select(EmpCompany).where(
        EmpCompany.tenant_id == tenant_id,
        EmpCompany.is_deleted.is_(False),
    ).order_by(EmpCompany.id)).all())
    positions = list(db.scalars(select(InternshipPosition).where(
        InternshipPosition.tenant_id == tenant_id,
        InternshipPosition.is_deleted.is_(False),
    ).order_by(InternshipPosition.id)).all())
    if len(companies) != 80 or len(positions) != 160:
        raise RuntimeError(f"实习企业/岗位基数异常 companies={len(companies)} positions={len(positions)}")

    quota = _company_quota()
    company_major: dict[int, str] = {}
    company_cursor = 0
    for major_order, (_major_code, _college_name, major_name) in enumerate(_major_specs()):
        profile = professional_profile(major_name)
        for local_index in range(1, quota[major_name] + 1):
            company = companies[company_cursor]
            company_cursor += 1
            city = COMPANY_CITIES[(major_order * 3 + local_index) % len(COMPANY_CITIES)]
            brand = COMPANY_BRANDS[(major_order + local_index) % len(COMPANY_BRANDS)]
            company.name = f"{city}{brand}{major_name[:4]}产教合作{local_index:02d}有限公司"
            company.industry = profile.industry
            company.city = city
            company.region = city
            company.address = f"{city}市产教融合园区{major_order + 1}区{local_index}号"
            company.nature = "民营企业" if local_index % 3 else "产教融合企业"
            company.scale = "中型" if local_index % 2 else "大型"
            company_major[int(company.id)] = major_name
    if company_cursor != 80:
        raise RuntimeError(f"企业专业分配异常 cursor={company_cursor}")

    positions_by_company: dict[int, list] = defaultdict(list)
    for position in positions:
        positions_by_company[int(position.company_id)].append(position)

    positions_by_major: dict[str, list] = defaultdict(list)
    for company in companies:
        major_name = company_major[int(company.id)]
        profile = professional_profile(major_name)
        for local_index, position in enumerate(positions_by_company[int(company.id)]):
            title = profile.internship_positions[local_index % len(profile.internship_positions)]
            position.company_name = company.name
            position.title = title
            position.category = f"{major_name}专业实践"
            position.major_requirement = major_name
            position.grade_requirement = "2024级"
            position.work_location = company.city
            position.work_address = company.address
            position.salary_range = "2800-4500元/月"
            position.subsidy = "餐补+交通补贴"
            position.headcount = 80
            position.allocated_count = 0
            position.remuneration_amount = 3200
            position.work_content = f"在企业导师指导下完成{title}相关岗位任务、过程记录与阶段总结。"
            positions_by_major[major_name].append(position)

    major_name_by_id = {
        int(mid): name
        for mid, name in db.execute(select(Major.id, Major.major_name).where(
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

    assigned_by_major: Counter[str] = Counter()
    records = list(db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.is_deleted.is_(False),
    ).order_by(InternshipRecord.id)).all())
    for record in records:
        major_name = student_major[int(record.student_id)]
        if record.destination_type != "ASSIGNED":
            record.enterprise_name = None
            record.position_name = None
            record.enterprise_id = None
            record.position_id = None
            continue
        pool = positions_by_major[major_name]
        if not pool:
            raise RuntimeError(f"专业无实习岗位: {major_name}")
        position = pool[assigned_by_major[major_name] % len(pool)]
        assigned_by_major[major_name] += 1
        record.enterprise_id = int(position.company_id)
        record.position_id = int(position.id)
        record.enterprise_name = position.company_name
        record.position_name = position.title

    db.commit()
    return {
        "companies": len(companies),
        "positions": len(positions),
        "assignedRecords": sum(assigned_by_major.values()),
        "assignedByMajor": dict(assigned_by_major),
    }


def _professionalize_graduation(db, tenant_id: int) -> dict:
    from app.models import (
        GraduationMentor,
        GraduationStudent,
        GraduationTopic,
        InternshipPosition,
        Major,
        StudentProfile,
    )

    majors = list(db.execute(select(
        Major.id, Major.code, Major.major_name, Major.college_id,
    ).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.code)).all())
    major_id_by_name = {row.major_name: int(row.id) for row in majors}
    major_name_by_id = {int(row.id): row.major_name for row in majors}
    college_id_by_name = {row.major_name: int(row.college_id) for row in majors}

    student_major_by_profile_id = {
        int(sid): major_name_by_id[int(major_id)]
        for sid, major_id in db.execute(select(
            StudentProfile.id, StudentProfile.major_id,
        ).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.grade == "2024",
            StudentProfile.is_deleted.is_(False),
        )).all()
    }

    students = list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.student_no)).all())
    students_by_major: dict[str, list] = defaultdict(list)
    for student in students:
        major_name = student_major_by_profile_id[int(student.student_id)]
        students_by_major[major_name].append(student)
    guiding_targets = _even_guiding_targets(students_by_major)

    mentors = list(db.scalars(select(GraduationMentor).where(
        GraduationMentor.tenant_id == tenant_id,
        GraduationMentor.is_deleted.is_(False),
    ).order_by(GraduationMentor.id)).all())
    if len(mentors) != 96:
        raise RuntimeError(f"毕设导师基数异常: {len(mentors)}")

    mentors_by_major: dict[str, list] = defaultdict(list)
    mentor_cursor = 0
    for major_code, college_name, major_name in _major_specs():
        # 32 专业按“每届班数 - 1”配置专职毕设导师，恰好 96 人；长尾专业至少 1 人。
        mentor_count = MAJOR_CLASS_COUNTS_PER_GRADE[major_code] - 1
        profile = professional_profile(major_name)
        for _ in range(mentor_count):
            mentor = mentors[mentor_cursor]
            mentor_cursor += 1
            mentor.college_id = str(college_id_by_name[major_name])
            mentor.college_name = college_name
            mentor.major_name = major_name
            mentor.research_direction = f"{profile.industry}·{major_name}岗位实践"
            mentor.max_capacity = 120
            mentor.current_count = 0
            mentors_by_major[major_name].append(mentor)
    if mentor_cursor != 96:
        raise RuntimeError(f"毕设导师专业分配异常 cursor={mentor_cursor}")

    topics = list(db.scalars(select(GraduationTopic).where(
        GraduationTopic.tenant_id == tenant_id,
        GraduationTopic.is_deleted.is_(False),
    ).order_by(GraduationTopic.id)).all())
    expected_topics = sum(guiding_targets.values()) // 2
    if len(topics) != expected_topics:
        raise RuntimeError(f"毕设题目基数异常 expected={expected_topics} actual={len(topics)}")

    # 企业归属不靠行业名称猜测，直接取已经专业化的岗位 major_requirement → company_id 事实。
    company_major = {
        int(company_id): major_name
        for company_id, major_name in db.execute(select(
            InternshipPosition.company_id,
            InternshipPosition.major_requirement,
        ).where(
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.major_requirement.is_not(None),
            InternshipPosition.is_deleted.is_(False),
        )).all()
    }
    from app.models import EmpCompany
    companies_by_major: dict[str, list] = defaultdict(list)
    for company in db.scalars(select(EmpCompany).where(
        EmpCompany.tenant_id == tenant_id,
        EmpCompany.is_deleted.is_(False),
    ).order_by(EmpCompany.id)).all():
        major_name = company_major.get(int(company.id))
        if major_name:
            companies_by_major[major_name].append(company)

    topics_by_major: dict[str, list] = defaultdict(list)
    topic_cursor = 0
    global_topic_no = 1
    for _major_code, _college_name, major_name in _major_specs():
        profile = professional_profile(major_name)
        mentor_pool = mentors_by_major[major_name]
        company_pool = companies_by_major[major_name]
        major_topic_count = guiding_targets[major_name] // 2
        for local_index in range(major_topic_count):
            topic = topics[topic_cursor]
            topic_cursor += 1
            mentor = mentor_pool[local_index % len(mentor_pool)]
            template = profile.graduation_topics[local_index % len(profile.graduation_topics)]
            enterprise_topic = bool(company_pool) and local_index % 5 == 0
            company = company_pool[local_index % len(company_pool)] if enterprise_topic else None
            topic.topic_no = f"GD2027-{global_topic_no:04d}"
            global_topic_no += 1
            topic.title = f"{template}（{local_index + 1:03d}）"
            topic.source = "企业课题" if enterprise_topic else "教师申报"
            topic.source_type = "ENTERPRISE" if enterprise_topic else "TEACHER"
            topic.enterprise_name = company.name if company else None
            topic.advisor_name = mentor.teacher_name
            topic.advisor_mentor_id = int(mentor.id)
            topic.college_id = str(college_id_by_name[major_name])
            topic.major_id = str(major_id_by_name[major_name])
            topic.major_name = major_name
            topic.category = TOPIC_CATEGORIES[local_index % len(TOPIC_CATEGORIES)]
            topic.difficulty = "HARD" if local_index % 5 == 0 else "MEDIUM"
            topic.requirements = f"围绕{profile.industry}真实岗位任务完成调研、方案、实施验证和过程材料。"
            topic.outcome = "形成可验收的实践成果、技术/业务文档和毕业设计总结。"
            topic.skills = "、".join(profile.core_courses[:3])
            topic.capacity = 2
            topic.selected = 2
            topic.review_status = "APPROVED"
            topic.status = "CONFIRMED"
            topics_by_major[major_name].append(topic)
    if topic_cursor != len(topics):
        raise RuntimeError(f"毕设题目专业分配异常 cursor={topic_cursor} total={len(topics)}")

    mentor_student_count: Counter[int] = Counter()
    for _major_code, _college_name, major_name in _major_specs():
        rows = students_by_major[major_name]
        guiding_target = guiding_targets[major_name]
        topic_pool = topics_by_major[major_name]
        mentor_pool = mentors_by_major[major_name]
        for index, student in enumerate(rows):
            if index < guiding_target:
                topic = topic_pool[index // 2]
                mentor = next(
                    item for item in mentor_pool
                    if int(item.id) == int(topic.advisor_mentor_id)
                )
                student.stage = "GUIDING"
                student.topic_id = int(topic.id)
                student.topic_title = topic.title
                student.topic_source = topic.source
            else:
                mentor = mentor_pool[index % len(mentor_pool)]
                student.stage = "TOPIC_SELECTING"
                student.topic_id = None
                student.topic_title = None
                student.topic_source = None
            student.mentor_id = int(mentor.id)
            student.advisor_name = mentor.teacher_name
            student.student_group = f"{major_name}过程组{(index % len(mentor_pool)) + 1}"
            mentor_student_count[int(mentor.id)] += 1

    for mentor in mentors:
        mentor.current_count = mentor_student_count[int(mentor.id)]
        if mentor.current_count > mentor.max_capacity:
            raise RuntimeError(
                f"毕设导师超容量 mentor={mentor.teacher_name} "
                f"current={mentor.current_count} max={mentor.max_capacity}"
            )

    db.commit()
    return {
        "mentors": len(mentors),
        "topics": len(topics),
        "guiding": sum(guiding_targets.values()),
        "topicSelecting": len(students) - sum(guiding_targets.values()),
        "guidingByMajor": guiding_targets,
    }


def validate_professional_school_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AaCourse,
        GraduationMentor,
        GraduationStudent,
        GraduationTopic,
        InternshipPosition,
        InternshipRecord,
        Major,
        StudentProfile,
    )

    major_name_by_id = {
        int(mid): name
        for mid, name in db.execute(select(Major.id, Major.major_name).where(
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )).all()
    }

    expected_core_names = {
        course_name
        for _code, _college, major_name in _major_specs()
        for course_name in professional_profile(major_name).core_courses
    }
    aa_major_courses = list(db.execute(select(AaCourse.course_name).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.is_all_major.is_(False),
        AaCourse.is_deleted.is_(False),
    )).all())
    bad_aa_courses = [name for (name,) in aa_major_courses if name not in expected_core_names]

    student_major = {
        int(sid): major_name_by_id[int(mid)]
        for sid, mid in db.execute(select(StudentProfile.id, StudentProfile.major_id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.grade == "2024",
            StudentProfile.is_deleted.is_(False),
        )).all()
    }
    position_major = {
        int(pid): requirement
        for pid, requirement in db.execute(select(
            InternshipPosition.id, InternshipPosition.major_requirement,
        ).where(
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.is_deleted.is_(False),
        )).all()
    }
    internship_mismatch = 0
    assigned_count = 0
    for sid, pid, destination in db.execute(select(
        InternshipRecord.student_id,
        InternshipRecord.position_id,
        InternshipRecord.destination_type,
    ).where(
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.is_deleted.is_(False),
    )).all():
        if destination != "ASSIGNED":
            continue
        assigned_count += 1
        if not pid or position_major.get(int(pid)) != student_major[int(sid)]:
            internship_mismatch += 1

    topic_major = {
        int(tid): str(mid)
        for tid, mid in db.execute(select(
            GraduationTopic.id, GraduationTopic.major_id,
        ).where(
            GraduationTopic.tenant_id == tenant_id,
            GraduationTopic.is_deleted.is_(False),
        )).all()
    }
    mentor_major = {
        int(mid): major_name
        for mid, major_name in db.execute(select(
            GraduationMentor.id, GraduationMentor.major_name,
        ).where(
            GraduationMentor.tenant_id == tenant_id,
            GraduationMentor.is_deleted.is_(False),
        )).all()
    }
    guiding = 0
    selecting = 0
    graduation_mismatch = 0
    for stage, topic_id, mentor_id, major_id in db.execute(select(
        GraduationStudent.stage,
        GraduationStudent.topic_id,
        GraduationStudent.mentor_id,
        GraduationStudent.major_id,
    ).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
    )).all():
        major_name = major_name_by_id[int(major_id)]
        if not mentor_id or mentor_major.get(int(mentor_id)) != major_name:
            graduation_mismatch += 1
        if stage == "GUIDING":
            guiding += 1
            if not topic_id or topic_major.get(int(topic_id)) != str(major_id):
                graduation_mismatch += 1
        elif stage == "TOPIC_SELECTING":
            selecting += 1
            if topic_id is not None:
                graduation_mismatch += 1
        else:
            graduation_mismatch += 1

    report = {
        "aaMajorCourses": len(aa_major_courses),
        "badAaMajorCourseNames": len(bad_aa_courses),
        "assignedInternships": assigned_count,
        "internshipMajorMismatches": internship_mismatch,
        "graduationMajorMismatches": graduation_mismatch,
        "graduationGuiding": guiding,
        "graduationTopicSelecting": selecting,
    }
    expected = {
        "aaMajorCourses": 192,
        "badAaMajorCourseNames": 0,
        "assignedInternships": 6100,
        "internshipMajorMismatches": 0,
        "graduationMajorMismatches": 0,
        "graduationGuiding": 2240,
        "graduationTopicSelecting": 4160,
    }
    mismatches = {
        key: {"expected": expected[key], "actual": report[key]}
        for key in expected
        if report[key] != expected[key]
    }
    if mismatches:
        raise RuntimeError(f"20K 专业语义验收失败: {mismatches}")
    report["passed"] = True
    return report


def professionalize_school_20k(db, tenant_id: int) -> dict:
    result = {
        "academic": _professionalize_academic(db, tenant_id),
        "internship": _professionalize_internship(db, tenant_id),
        "graduation": _professionalize_graduation(db, tenant_id),
    }
    result["validation"] = validate_professional_school_20k(db, tenant_id)
    return result
