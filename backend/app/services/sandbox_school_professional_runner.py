"""20K 专业语义编排器：保持专业真实性，同时避免大成绩表 ORM 全量物化。

历史 AcademicGrade 约 17 万行。专业课名称校正必须在 MySQL 侧集合更新，禁止把全表
load 成 ORM 对象逐行修改；13B 自身只有数千条课程快照，可精确同步课程库、培养方案、
教学任务/教学班、课表、成绩任务和考试课程，避免老师钻详情时看见旧泛化课名。
"""
from __future__ import annotations

from sqlalchemy import case, func, select, update

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


def _rename_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for _major_code, _college_name, major_name in _major_specs():
        for index, label in enumerate(LEGACY_MAJOR_COURSE_LABELS):
            out[f"{major_name}{label}"] = _target_course_name(major_name, index)
    return out


def _sync_aa_course_snapshots(db, tenant_id: int, rename_map: dict[str, str]) -> dict:
    from app.models import AaExamCourse, AaGradeTask, AaProgramCourse, AaScheduleItem, AaTeachingTask

    updated = {
        "programCourses": 0,
        "teachingTasks": 0,
        "scheduleItems": 0,
        "gradeTasks": 0,
        "examCourses": 0,
        "teachingClassNames": 0,
    }
    model_fields = (
        (AaProgramCourse, "course_name", "programCourses"),
        (AaScheduleItem, "course_name", "scheduleItems"),
        (AaGradeTask, "course_name", "gradeTasks"),
        (AaExamCourse, "course_name", "examCourses"),
    )
    for model, field_name, counter_key in model_fields:
        field = getattr(model, field_name)
        rows = list(db.scalars(select(model).where(
            model.tenant_id == tenant_id,
            field.in_(tuple(rename_map)),
            model.is_deleted.is_(False),
        )).all())
        for row in rows:
            old = str(getattr(row, field_name) or "")
            new = rename_map.get(old)
            if new and new != old:
                setattr(row, field_name, new)
                updated[counter_key] += 1

    teaching_tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.is_deleted.is_(False),
    )).all())
    for task in teaching_tasks:
        old = str(task.course_name or "")
        new = rename_map.get(old)
        if not new or new == old:
            continue
        task.course_name = new
        updated["teachingTasks"] += 1
        if task.teaching_class_name and old in task.teaching_class_name:
            task.teaching_class_name = task.teaching_class_name.replace(old, new)
            updated["teachingClassNames"] += 1

    return updated


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

    rename_map = _rename_map()
    snapshots = _sync_aa_course_snapshots(db, tenant_id, rename_map)

    # 旧 academic 域历史成绩约 174,600 行。一次 UPDATE 在数据库侧完成，不查询 AcademicStudent，
    # 不把大成绩表拉进 Python。
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
        "courseSnapshots": snapshots,
        "gradeRewriteMode": "SQL_CASE_UPDATE",
    }


def validate_professional_academic_snapshots(db, tenant_id: int) -> dict:
    """只读验证所有 13B 课程快照都已脱离旧泛化命名。"""
    from app.models import AaExamCourse, AaGradeTask, AaProgramCourse, AaScheduleItem, AaTeachingTask

    rename_map = _rename_map()
    old_names = tuple(rename_map)
    models = (
        ("programCourses", AaProgramCourse, AaProgramCourse.course_name),
        ("teachingTasks", AaTeachingTask, AaTeachingTask.course_name),
        ("scheduleItems", AaScheduleItem, AaScheduleItem.course_name),
        ("gradeTasks", AaGradeTask, AaGradeTask.course_name),
        ("examCourses", AaExamCourse, AaExamCourse.course_name),
    )
    residual = {}
    for name, model, field in models:
        residual[name] = int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            field.in_(old_names),
            model.is_deleted.is_(False),
        )) or 0)

    bad_teaching_class_names = 0
    for value in db.scalars(select(AaTeachingTask.teaching_class_name).where(
        AaTeachingTask.tenant_id == tenant_id,
        AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.teaching_class_name.is_not(None),
    )).all():
        text = str(value or "")
        if any(old in text for old in old_names):
            bad_teaching_class_names += 1
    residual["teachingClassNames"] = bad_teaching_class_names

    if any(residual.values()):
        raise RuntimeError(f"13B 专业课程快照仍含旧泛化名称: {residual}")
    return {"legacyCourseSnapshotResidue": residual, "passed": True}


def professionalize_school_20k(db, tenant_id: int) -> dict:
    result = {
        "academic": professionalize_academic_fast(db, tenant_id),
        "internship": _professionalize_internship(db, tenant_id),
        "graduation": _professionalize_graduation(db, tenant_id),
    }
    result["academicSnapshotValidation"] = validate_professional_academic_snapshots(db, tenant_id)
    result["validation"] = validate_professional_school_20k(db, tenant_id)
    return result
