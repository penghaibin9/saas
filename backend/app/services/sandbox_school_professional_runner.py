"""20K 专业语义编排器：保持专业真实性，同时避免大成绩表 ORM 全量物化。

历史 AcademicGrade 约 17 万行。专业课名称校正必须在 MySQL 侧集合更新，禁止把全表
load 成 ORM 对象逐行修改；13B 自身只有数千条课程快照，可按 course_id/class_id/task_id
从 canonical 关系重建课程名、教学班名和课表班名，避免字符串替换遗漏或误判。
"""
from __future__ import annotations

from sqlalchemy import func, select, text

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


def _canonical_major_course_category(label_index: int) -> str:
    """完整三年制课程目录的 canonical 类别：01-17 专业核心，18-23 集中实践。"""
    if 0 <= label_index < 17:
        return "MAJOR_CORE"
    if 17 <= label_index < 23:
        return "PRACTICE"
    raise ValueError(f"专业课程序号越界: {label_index + 1}")


def _rename_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for _major_code, _college_name, major_name in _major_specs():
        for index, label in enumerate(LEGACY_MAJOR_COURSE_LABELS):
            out[f"{major_name}{label}"] = _target_course_name(major_name, index)
    return out


def _reconcile_academic_grade_names(db, tenant_id: int) -> dict:
    """按学生专业和原始课程顺序幂等收口历史成绩课名。

    不能用“当前课名 -> 目标课名”反复替换：某些专业的目标课名可能恰好
    也是另一个旧占位课名，二次执行会产生链式误改。基础 seed 对每个学生按
    固定顺序写入 9/18 条成绩，因此以 (acad_student_id, id) 中的顺序定位
    9 门专业课，可恢复且可重复验证。
    """
    from app.models import AcademicGrade, AcademicStudent

    student_meta = {
        int(student_id): (str(major_name), str(grade))
        for student_id, major_name, grade in db.execute(
            select(AcademicStudent.id, AcademicStudent.major_name, AcademicStudent.grade).where(
                AcademicStudent.tenant_id == tenant_id,
                AcademicStudent.is_deleted.is_(False),
            )
        ).all()
    }
    if not student_meta:
        raise RuntimeError("20K 学业成绩专业化失败：无学生学业档案")

    update_sql = text(
        "UPDATE t_acad_grade SET course_name=:course_name "
        "WHERE id=:grade_id AND tenant_id=:tenant_id AND is_deleted=0"
    )
    pending: list[dict] = []
    checked = 0
    mismatch_count = 0
    updated = 0
    current_student_id: int | None = None
    current_ordinal = 0

    def _assert_row_count(student_id: int | None, row_count: int) -> None:
        if student_id is None:
            return
        _major_name, grade = student_meta[student_id]
        expected = 18 if grade == "2024" else 9
        if row_count != expected:
            raise RuntimeError(
                "20K 学业成绩专业化失败："
                f"acadStudentId={student_id} grade={grade} rows={row_count} expected={expected}"
            )

    rows = db.execute(
        select(AcademicGrade.id, AcademicGrade.acad_student_id, AcademicGrade.course_name)
        .where(
            AcademicGrade.tenant_id == tenant_id,
            AcademicGrade.is_deleted.is_(False),
        )
        .order_by(AcademicGrade.acad_student_id, AcademicGrade.id)
        .execution_options(yield_per=2000)
    )
    for grade_id, acad_student_id, current_name in rows:
        sid = int(acad_student_id)
        if sid not in student_meta:
            raise RuntimeError(f"20K 学业成绩存在无档案学生：acadStudentId={sid}")
        if current_student_id != sid:
            _assert_row_count(current_student_id, current_ordinal)
            current_student_id = sid
            current_ordinal = 0
        current_ordinal += 1
        checked += 1

        label_index: int | None = None
        if 6 <= current_ordinal <= 9:
            label_index = current_ordinal - 6
        elif 14 <= current_ordinal <= 18:
            label_index = current_ordinal - 10
        if label_index is None:
            continue

        major_name, _grade = student_meta[sid]
        expected_name = _target_course_name(major_name, label_index)
        if str(current_name or "") == expected_name:
            continue
        mismatch_count += 1
        pending.append({
            "course_name": expected_name,
            "grade_id": int(grade_id),
            "tenant_id": tenant_id,
        })
        if len(pending) >= 2000:
            result = db.execute(update_sql, pending)
            updated += int(result.rowcount or 0)
            pending.clear()

    _assert_row_count(current_student_id, current_ordinal)
    if pending:
        result = db.execute(update_sql, pending)
        updated += int(result.rowcount or 0)
    if updated != mismatch_count:
        raise RuntimeError(
            f"20K 学业成绩课名收口行数异常：mismatch={mismatch_count} updated={updated}"
        )
    return {
        "checked": checked,
        "mismatches": mismatch_count,
        "updated": updated,
        "mode": "STUDENT_MAJOR_AND_GRADE_ORDINAL",
    }


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
    # 基础 seed 的 category 仍保留 generic 分类；专业化时必须与最终三年制 140 学分
    # 模块口径一起收口，否则 01/04/05 会在完整目录里留下 DISCIPLINE_BASIC/PRACTICE 漂移。
    aa_updated = 0
    aa_category_updated = 0
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
            canonical_category = _canonical_major_course_category(index)
            if str(course.category or "") != canonical_category:
                course.category = canonical_category
                aa_category_updated += 1

    # flush 后关系快照读取到的就是课程库最终专业课名。
    db.flush()
    snapshots = _sync_aa_course_snapshots(db, tenant_id)

    grade_reconciliation = _reconcile_academic_grade_names(db, tenant_id)

    db.commit()
    return {
        "aaMajorCourses": aa_updated,
        "aaMajorCourseCategories": aa_category_updated,
        "academicGradeNames": grade_reconciliation["updated"],
        "academicGradeReconciliation": grade_reconciliation,
        "courseSnapshots": snapshots,
        "gradeRewriteMode": "STUDENT_MAJOR_AND_GRADE_ORDINAL",
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


def reconcile_professional_academic_snapshots(db, tenant_id: int) -> dict:
    """后续阶段新增 13B 快照后，按 canonical 外键关系收口并立即只读复验。"""
    updated = _sync_aa_course_snapshots(db, tenant_id)
    db.commit()
    return {
        "updated": updated,
        "validation": validate_professional_academic_snapshots(db, tenant_id),
    }


def professionalize_school_20k(db, tenant_id: int) -> dict:
    result = {
        "academic": professionalize_academic_fast(db, tenant_id),
        "internship": _professionalize_internship(db, tenant_id),
        "graduation": _professionalize_graduation(db, tenant_id),
    }
    result["academicSnapshotValidation"] = validate_professional_academic_snapshots(db, tenant_id)
    result["validation"] = validate_professional_school_20k(db, tenant_id)
    return result
