"""standard-20k · 完整专业语义终态验收。

基础 professionalize 阶段继续由 ``validate_professional_school_20k`` 锁定最初 32×6=192 门
核心专业课、实习岗位与毕设专业关系；三年制培养方案扩容到 32×23=736 门专业/实践课后，
本模块负责最终态验收，避免拿旧 192 门 baseline validator 去误判合法的拓展课程。

最终规则不是放宽计数：每个专业 23 门课程的 course_code、course_name、category 都必须
逐门命中确定性专业画像，同时再次复核实习与毕设不存在跨专业错配。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.services.sandbox_school_curriculum_closure import MAJOR_EXTENSION_LABELS, PRACTICE_LABELS
from app.services.sandbox_school_professional_catalog import professional_profile
from app.services.sandbox_school_professional_reconcile import (
    ADVANCED_MAJOR_COURSE_LABELS,
    _major_specs,
)

EXPECTED_MAJOR_COURSES = 32 * 23
EXPECTED_PUBLIC_COURSES = 14
EXPECTED_TOTAL_COURSES = EXPECTED_MAJOR_COURSES + EXPECTED_PUBLIC_COURSES


def _expected_major_course_catalog() -> dict[str, tuple[str, str, str]]:
    """course_code -> (major_name, expected_name, expected_category)."""
    expected: dict[str, tuple[str, str, str]] = {}
    for major_code, _college_name, major_name in _major_specs():
        profile = professional_profile(major_name)
        names = [
            *profile.core_courses,
            *[f"{major_name}{label}" for label in ADVANCED_MAJOR_COURSE_LABELS],
            *[f"{major_name}{label}" for label in MAJOR_EXTENSION_LABELS],
            *[f"{major_name}{row[0]}" for row in PRACTICE_LABELS],
        ]
        if len(names) != 23:
            raise RuntimeError(f"专业课程画像数量异常 major={major_name} actual={len(names)}")
        for index, name in enumerate(names, 1):
            expected[f"{major_code}-{index:02d}"] = (
                major_name,
                str(name),
                "PRACTICE" if index >= 18 else "MAJOR_CORE",
            )
    if len(expected) != EXPECTED_MAJOR_COURSES:
        raise RuntimeError(
            f"完整专业课程画像数量异常 expected={EXPECTED_MAJOR_COURSES} actual={len(expected)}"
        )
    return expected


def validate_professional_school_final_20k(db, tenant_id: int) -> dict:
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

    expected_catalog = _expected_major_course_catalog()
    courses = list(db.execute(select(
        AaCourse.course_code,
        AaCourse.course_name,
        AaCourse.category,
        AaCourse.is_all_major,
    ).where(
        AaCourse.tenant_id == tenant_id,
        AaCourse.is_deleted.is_(False),
    )).all())
    total_courses = len(courses)
    public_courses = sum(1 for row in courses if bool(row.is_all_major))
    major_rows = [row for row in courses if not bool(row.is_all_major)]

    seen_codes: set[str] = set()
    bad_course_rows: list[dict] = []
    duplicate_codes: list[str] = []
    for row in major_rows:
        code = str(row.course_code or "")
        if code in seen_codes:
            duplicate_codes.append(code)
            continue
        seen_codes.add(code)
        expected = expected_catalog.get(code)
        if expected is None:
            bad_course_rows.append({
                "courseCode": code,
                "courseName": row.course_name,
                "reason": "UNEXPECTED_CODE",
            })
            continue
        major_name, expected_name, expected_category = expected
        if str(row.course_name or "") != expected_name or str(row.category or "") != expected_category:
            bad_course_rows.append({
                "courseCode": code,
                "majorName": major_name,
                "expectedName": expected_name,
                "actualName": row.course_name,
                "expectedCategory": expected_category,
                "actualCategory": row.category,
                "reason": "NAME_OR_CATEGORY_MISMATCH",
            })
    missing_codes = sorted(set(expected_catalog) - seen_codes)

    major_name_by_id = {
        int(mid): str(name)
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
    position_major = {
        int(pid): str(requirement or "")
        for pid, requirement in db.execute(select(
            InternshipPosition.id, InternshipPosition.major_requirement,
        ).where(
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.is_deleted.is_(False),
        )).all()
    }
    assigned_count = 0
    internship_mismatch = 0
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
        if not pid or position_major.get(int(pid)) != student_major.get(int(sid)):
            internship_mismatch += 1

    topic_major = {
        int(tid): str(mid)
        for tid, mid in db.execute(select(GraduationTopic.id, GraduationTopic.major_id).where(
            GraduationTopic.tenant_id == tenant_id,
            GraduationTopic.is_deleted.is_(False),
        )).all()
    }
    mentor_major = {
        int(mid): str(major_name or "")
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
        major_name = major_name_by_id.get(int(major_id))
        if not major_name or not mentor_id or mentor_major.get(int(mentor_id)) != major_name:
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
        "courseTotal": total_courses,
        "publicCourses": public_courses,
        "majorAndPracticeCourses": len(major_rows),
        "missingMajorCourseCodes": len(missing_codes),
        "duplicateMajorCourseCodes": len(duplicate_codes),
        "badMajorCourseRows": len(bad_course_rows),
        "assignedInternships": assigned_count,
        "internshipMajorMismatches": internship_mismatch,
        "graduationMajorMismatches": graduation_mismatch,
        "graduationGuiding": guiding,
        "graduationTopicSelecting": selecting,
    }
    expected = {
        "courseTotal": EXPECTED_TOTAL_COURSES,
        "publicCourses": EXPECTED_PUBLIC_COURSES,
        "majorAndPracticeCourses": EXPECTED_MAJOR_COURSES,
        "missingMajorCourseCodes": 0,
        "duplicateMajorCourseCodes": 0,
        "badMajorCourseRows": 0,
        "assignedInternships": 6100,
        "internshipMajorMismatches": 0,
        "graduationMajorMismatches": 0,
        "graduationGuiding": 2240,
        "graduationTopicSelecting": 4160,
    }
    mismatches = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected.items()
        if report[key] != value
    }
    if mismatches:
        raise RuntimeError(
            "20K 完整专业语义验收失败: "
            f"{mismatches}; missingSamples={missing_codes[:10]}; "
            f"duplicateSamples={duplicate_codes[:10]}; badSamples={bad_course_rows[:5]}"
        )
    report["passed"] = True
    return report
