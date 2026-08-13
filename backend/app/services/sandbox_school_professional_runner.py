"""20K 专业语义编排器：保持专业真实性，同时避免大成绩表 ORM 全量物化。

历史 AcademicGrade 约 17 万行。专业课名称校正必须在 MySQL 侧集合更新，禁止把全表
load 成 ORM 对象逐行修改；实习与毕设仍复用经过真实关系验收的专业对账函数。
"""
from __future__ import annotations

from sqlalchemy import case, select, update

from app.services.sandbox_school_professional_catalog import professional_profile
from app.services.sandbox_school_professional_reconcile import (
    ADVANCED_MAJOR_COURSE_LABELS,
    LEGACY_MAJOR_COURSE_LABELS,
    _major_specs,
    _professionalize_graduation,
    _professionalize_internship,
    validate_professional_school_20k,
)


def _target_course_name(major_name: str, label_index: int) -> str:
    profile = professional_profile(major_name)
    if label_index < len(profile.core_courses):
        return profile.core_courses[label_index]
    return f"{major_name}{ADVANCED_MAJOR_COURSE_LABELS[label_index - len(profile.core_courses)]}"


def professionalize_academic_fast(db, tenant_id: int) -> dict:
    from app.models import AaCourse, AcademicGrade, Major

    major_name_by_code = {
        code: name
        for code, name in db.execute(select(Major.code, Major.major_name).where(
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )).all()
    }

    # 13B 课程库只有 192 条专业课程，ORM 更新规模固定且很小。
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

    # 旧 academic 域历史成绩约 174,600 行。直接按“旧课程名 → 新课程名”构造 CASE，
    # 一次 UPDATE 在数据库侧完成，不查询 AcademicStudent、不把 AcademicGrade 拉进 Python。
    rename_map: dict[str, str] = {}
    for _major_code, _college_name, major_name in _major_specs():
        for index, label in enumerate(LEGACY_MAJOR_COURSE_LABELS):
            rename_map[f"{major_name}{label}"] = _target_course_name(major_name, index)

    grade_updated = 0
    if rename_map:
        result = db.execute(
            update(AcademicGrade)
            .where(
                AcademicGrade.tenant_id == tenant_id,
                AcademicGrade.course_name.in_(tuple(rename_map)),
                AcademicGrade.is_deleted.is_(False),
            )
            .values(
                course_name=case(
                    rename_map,
                    value=AcademicGrade.course_name,
                    else_=AcademicGrade.course_name,
                )
            )
        )
        grade_updated = int(result.rowcount or 0)

    db.commit()
    return {
        "aaMajorCourses": aa_updated,
        "academicGradeNames": grade_updated,
        "gradeRewriteMode": "SQL_CASE_UPDATE",
    }


def professionalize_school_20k(db, tenant_id: int) -> dict:
    result = {
        "academic": professionalize_academic_fast(db, tenant_id),
        "internship": _professionalize_internship(db, tenant_id),
        "graduation": _professionalize_graduation(db, tenant_id),
    }
    result["validation"] = validate_professional_school_20k(db, tenant_id)
    return result
