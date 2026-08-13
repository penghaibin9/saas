"""20K 专业语义编排器：保持专业真实性，同时避免大成绩表 ORM 全量物化。

历史 AcademicGrade 约 17 万行。专业课名称校正必须在 MySQL 侧集合更新，禁止把全表
load 成 ORM 对象逐行修改；13B 自身只有数千条课程快照，可按 course_id/class_id/task_id
从 canonical 关系重建课程名、教学班名和课表班名，避免字符串替换遗漏或误判。
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


def _sync_aa_course_snapshots(db, tenant_id: int) -> dict:
    """按正式外键关系重建 13B 小表快照，不靠旧课名字符串猜替换。"""
    from app.models import (
        AaCourse,
        AaExamCourse,
        AaGradeTask,
        AaProgramCourse,
        AaScheduleItem,
        AaTeachingTask,
        SchoolClass,
    )

    course_name_by_id = {
        int(course_id): str(course_name)
        for course_id, course_name in db.execute(select(AaCourse.id, AaCourse.course_name).where(
            AaCourse.tenant_id == tenant_id,
            AaCourse.is_deleted.is_(False),
        )).all()
    }
    class_name_by_id = {
        int(class_id): str(class_name)
        for class_id, class_name in db.execute(select(SchoolClass.id, SchoolClass.class_name).where(
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.is_deleted.is_(False),
        )).all()
    }

    updated = {
        "programCourses": 0,
        "teachingTasks": 0,
        "scheduleItems": 0,
        "gradeTasks": 0,
        "examCourses": 0,
        "teachingClassNames": 0,
        "scheduleClassNames": 0,
    }

    model_fields = (
        (AaProgramCourse, "programCourses"),
        (AaGradeTask, "gradeTasks"),
        (AaExamCourse, "examCourses"),
    )
    for model, counter_key in model_fields:
        rows = list(
            db.scalars(
                select(model).where(
                    model.tenant_id == tenant_id,
                    model.is_deleted.is_(False),
                )
            ).all()
        )
        for row in rows:
            course_id = int(row.course_id) if row.course_id is not None else None
            canonical = course_name_by_id.get(course_id) if course_id is not None else None
            if canonical is not None and str(row.course_name or "") != canonical:
                row.course_name = canonical
                updated[counter_key] += 1

    teaching_tasks = list(
        db.scalars(
            select(AaTeachingTask).where(
                AaTeachingTask.tenant_id == tenant_id,
                AaTeachingTask.is_deleted.is_(False),
            )
        ).all()
    )
    teaching_class_by_task_id: dict[int, str | None] = {}
    for task in teaching_tasks:
        course_id = int(task.course_id) if task.course_id is not None else None
        class_id = int(task.class_id) if task.class_id is not None else None
        canonical_course = course_name_by_id.get(course_id) if course_id is not None else None
        canonical_class = class_name_by_id.get(class_id) if class_id is not None else None
        if canonical_course is not None and str(task.course_name or "") != canonical_course:
            task.course_name = canonical_course
            updated["teachingTasks"] += 1
        expected_teaching_class = (
            f"{canonical_class}-{canonical_course}"
            if canonical_class is not None and canonical_course is not None
            else task.teaching_class_name
        )
        if expected_teaching_class is not None and task.teaching_class_name != expected_teaching_class:
            task.teaching_class_name = expected_teaching_class
            updated["teachingClassNames"] += 1
        teaching_class_by_task_id[int(task.id)] = task.teaching_class_name

    schedule_items = list(
        db.scalars(
            select(AaScheduleItem).where(
                AaScheduleItem.tenant_id == tenant_id,
                AaScheduleItem.is_deleted.is_(False),
            )
        ).all()
    )
    for item in schedule_items:
        course_id = int(item.course_id) if item.course_id is not None else None
        canonical_course = course_name_by_id.get(course_id) if course_id is not None else None
        if canonical_course is not None and str(item.course_name or "") != canonical_course:
            item.course_name = canonical_course
            updated["scheduleItems"] += 1
        task_id = int(item.task_id) if item.task_id is not None else None
        canonical_class_name = teaching_class_by_task_id.get(task_id) if task_id is not None else None
        if canonical_class_name is not None and item.class_name != canonical_class_name:
            item.class_name = canonical_class_name
            updated["scheduleClassNames"] += 1

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
    aa_courses = list(
        db.scalars(
            select(AaCourse).where(
                AaCourse.tenant_id == tenant_id,
                AaCourse.is_all_major.is_(False),
                AaCourse.is_deleted.is_(False),
            )
        ).all()
    )
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
            canonical = profile.core_courses[index]
            if course.course_name != canonical:
                course.course_name = canonical
                aa_updated += 1

    # flush 后关系快照读取到的就是课程库最终专业课名。
    db.flush()
    snapshots = _sync_aa_course_snapshots(db, tenant_id)

    rename_map = _rename_map()
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
    """只读验证 13B 快照与 course/class/task canonical 关系完全一致。"""
    from app.models import (
        AaCourse,
        AaExamCourse,
        AaGradeTask,
        AaProgramCourse,
        AaScheduleItem,
        AaTeachingTask,
        SchoolClass,
    )

    course_name_by_id = {
        int(course_id): str(course_name)
        for course_id, course_name in db.execute(select(AaCourse.id, AaCourse.course_name).where(
            AaCourse.tenant_id == tenant_id,
            AaCourse.is_deleted.is_(False),
        )).all()
    }
    class_name_by_id = {
        int(class_id): str(class_name)
        for class_id, class_name in db.execute(select(SchoolClass.id, SchoolClass.class_name).where(
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.is_deleted.is_(False),
        )).all()
    }

    mismatch = {
        "programCourses": 0,
        "teachingTasks": 0,
        "scheduleItems": 0,
        "gradeTasks": 0,
        "examCourses": 0,
        "teachingClassNames": 0,
        "scheduleClassNames": 0,
    }

    for model, key in (
        (AaProgramCourse, "programCourses"),
        (AaGradeTask, "gradeTasks"),
        (AaExamCourse, "examCourses"),
    ):
        for row in db.scalars(
            select(model).where(
                model.tenant_id == tenant_id,
                model.is_deleted.is_(False),
            )
        ).all():
            course_id = int(row.course_id) if row.course_id is not None else None
            canonical = course_name_by_id.get(course_id) if course_id is not None else None
            if canonical is not None and str(row.course_name or "") != canonical:
                mismatch[key] += 1

    teaching_class_by_task_id: dict[int, str | None] = {}
    for task in db.scalars(
        select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == tenant_id,
            AaTeachingTask.is_deleted.is_(False),
        )
    ).all():
        course_id = int(task.course_id) if task.course_id is not None else None
        class_id = int(task.class_id) if task.class_id is not None else None
        canonical_course = course_name_by_id.get(course_id) if course_id is not None else None
        canonical_class = class_name_by_id.get(class_id) if class_id is not None else None
        if canonical_course is not None and str(task.course_name or "") != canonical_course:
            mismatch["teachingTasks"] += 1
        expected = (
            f"{canonical_class}-{canonical_course}"
            if canonical_class is not None and canonical_course is not None
            else task.teaching_class_name
        )
        if expected is not None and task.teaching_class_name != expected:
            mismatch["teachingClassNames"] += 1
        teaching_class_by_task_id[int(task.id)] = expected

    for item in db.scalars(
        select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == tenant_id,
            AaScheduleItem.is_deleted.is_(False),
        )
    ).all():
        course_id = int(item.course_id) if item.course_id is not None else None
        canonical_course = course_name_by_id.get(course_id) if course_id is not None else None
        if canonical_course is not None and str(item.course_name or "") != canonical_course:
            mismatch["scheduleItems"] += 1
        task_id = int(item.task_id) if item.task_id is not None else None
        expected_class_name = teaching_class_by_task_id.get(task_id) if task_id is not None else None
        if expected_class_name is not None and item.class_name != expected_class_name:
            mismatch["scheduleClassNames"] += 1

    if any(mismatch.values()):
        raise RuntimeError(f"13B 专业课程/教学班快照与 canonical 关系不一致: {mismatch}")
    return {"snapshotRelationMismatches": mismatch, "passed": True}


def professionalize_school_20k(db, tenant_id: int) -> dict:
    result = {
        "academic": professionalize_academic_fast(db, tenant_id),
        "internship": _professionalize_internship(db, tenant_id),
        "graduation": _professionalize_graduation(db, tenant_id),
    }
    result["academicSnapshotValidation"] = validate_professional_academic_snapshots(db, tenant_id)
    result["validation"] = validate_professional_school_20k(db, tenant_id)
    return result
