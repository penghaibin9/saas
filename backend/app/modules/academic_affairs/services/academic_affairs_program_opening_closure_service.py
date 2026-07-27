"""V2 R7 培养方案校验器与开课差异最终层。

不建立“教学执行计划”第二主表，继续以：
AaProgram/AaProgramCourse/AaProgramBinding/AaCourse/AaTeachingTask 为事实源。

本层修正旧差异投影的三个生产缺口：
- PUBLISHED/ENABLED/FROZEN 均属于有有效绑定时可执行的方案，不能只读取 ENABLED；
- 差异同时核对教学任务总学时，避免课程对上了但实际任务课时错误仍显示一致；
- 所有结果先按统一学院/班级数据范围收敛，再形成首屏摘要，筛选不改变全局结论。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from app.core.affairs_security import no_data_scope
from app.core.exceptions import not_found
from app.services.db_service import _tid, session

from . import academic_affairs_program_quality_complete_service as _complete
from .academic_affairs_program_quality_security_service import _allowed_major_ids
from .academic_affairs_task_security_facade import _scope

_ACTIVE_PROGRAM_STATUSES = {"PUBLISHED", "ENABLED", "FROZEN"}
_ALLOWED_DIFF_STATUSES = {
    "READY", "MISSING_TASK", "DUPLICATE_TASK", "OVER_OPENED",
    "NO_TEACHER", "CREDIT_MISMATCH", "HOURS_MISMATCH",
    "COURSE_UNRESOLVED", "TERM_UNRESOLVED", "NO_CLASS",
}


def __getattr__(name):
    return getattr(_complete, name)


def _number(value, default=0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _summary(items) -> dict:
    counts = Counter(str(item.get("status") or "") for item in items)
    blockers = (
        counts["MISSING_TASK"] + counts["DUPLICATE_TASK"] + counts["OVER_OPENED"]
        + counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"]
        + counts["CREDIT_MISMATCH"] + counts["HOURS_MISMATCH"]
    )
    return {
        "total": len(items),
        "ready": counts["READY"],
        "missingTask": counts["MISSING_TASK"],
        "duplicateTask": counts["DUPLICATE_TASK"],
        "overOpened": counts["OVER_OPENED"],
        "unresolved": counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"],
        "noTeacher": counts["NO_TEACHER"],
        "creditMismatch": counts["CREDIT_MISMATCH"],
        "hoursMismatch": counts["HOURS_MISMATCH"],
        "blockerCount": blockers,
        "canGenerateOrConfirm": blockers == 0,
        "conclusion": "本学期开课与有效培养方案一致" if blockers == 0 else f"存在 {blockers} 个开课阻断差异",
    }


def _plan_term_no(year_code, term_no, grade_year):
    return _complete._ui._final._plan_term_no(year_code, term_no, grade_year)


def _task_row_status(program_course, catalog, tasks) -> tuple[str, str]:
    if not program_course.course_id or not catalog:
        return "COURSE_UNRESOLVED", "方案课程未关联有效课程库版本"
    if not tasks:
        return "MISSING_TASK", "方案应开课程尚未生成教学任务"
    if len(tasks) > 1:
        return "DUPLICATE_TASK", f"同一课程与行政班存在 {len(tasks)} 条教学任务"
    task = tasks[0]
    if abs(_number(program_course.credit_snapshot) - _number(catalog.credit)) > 0.001:
        return "CREDIT_MISMATCH", "方案学分快照与课程库当前学分不一致"
    catalog_hours = int(getattr(catalog, "hours_total", 0) or 0)
    task_hours = int(getattr(task, "total_hours", 0) or 0)
    if catalog_hours > 0 and task_hours != catalog_hours:
        return "HOURS_MISMATCH", f"教学任务总学时 {task_hours} 与课程库总学时 {catalog_hours} 不一致"
    if not (task.teacher_key or "").strip():
        return "NO_TEACHER", "教学任务尚未绑定稳定教师工号"
    return "READY", "方案应开课程、教学任务、学分和学时一致"


def opening_differences(user, term_id: int, major_id: int | None = None, grade_year: str | None = None,
                        status: str | None = None) -> dict:
    from app.models import (
        AaCourse, AaProgram, AaProgramBinding, AaProgramCourse, AaTeachingTask,
        AaTeachingTaskBatch, AaTerm, Major, SchoolClass,
    )

    active_filter = str(status or "").strip().upper()
    if active_filter and active_filter not in _ALLOWED_DIFF_STATUSES:
        active_filter = ""

    with session() as db:
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id),
            AaTerm.tenant_id == _tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            raise not_found("学期不存在")

        scope = _scope(user, db)
        allowed_major_ids = _allowed_major_ids(db, scope)
        allowed_class_ids = set(int(value) for value in (scope.class_ids or set()))
        if not scope.all and not allowed_class_ids and allowed_major_ids:
            allowed_class_ids = {
                int(value) for (value,) in db.query(SchoolClass.id).filter(
                    SchoolClass.tenant_id == _tid(),
                    SchoolClass.major_id.in_(list(allowed_major_ids)),
                    SchoolClass.class_status == "NORMAL",
                    SchoolClass.is_deleted.is_(False),
                ).all()
            }
        if major_id and not scope.all and int(major_id) not in allowed_major_ids:
            raise no_data_scope("所选专业不在当前数据范围内")

        programs = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(),
            AaProgram.status.in_(sorted(_ACTIVE_PROGRAM_STATUSES)),
            AaProgram.is_deleted.is_(False),
        ).all()
        if major_id:
            programs = [row for row in programs if int(row.major_id or 0) == int(major_id)]
        if grade_year:
            programs = [row for row in programs if str(row.grade_year or "") == str(grade_year)]
        if not scope.all:
            programs = [row for row in programs if row.major_id and int(row.major_id) in allowed_major_ids]

        batch_ids = [int(value) for (value,) in db.query(AaTeachingTaskBatch.id).filter(
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.term_id == int(term.id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).all()]
        tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id.in_(batch_ids),
            AaTeachingTask.status != "MERGED",
            AaTeachingTask.is_deleted.is_(False),
        ).all() if batch_ids else []
        if not scope.all:
            tasks = [task for task in tasks if task.class_id and int(task.class_id) in allowed_class_ids]
        task_map = defaultdict(list)
        for task in tasks:
            task_map[(int(task.course_id), int(task.class_id or 0))].append(task)

        items = []
        expected_keys = set()
        for program in programs:
            bindings = db.query(AaProgramBinding).filter(
                AaProgramBinding.tenant_id == _tid(),
                AaProgramBinding.program_id == int(program.id),
                AaProgramBinding.status == "ACTIVE",
                AaProgramBinding.is_deleted.is_(False),
            ).all()
            program_courses = db.query(AaProgramCourse).filter(
                AaProgramCourse.tenant_id == _tid(),
                AaProgramCourse.program_id == int(program.id),
                AaProgramCourse.is_deleted.is_(False),
            ).all()
            for binding in bindings:
                binding_grade = binding.grade_year or program.grade_year
                plan_term = _plan_term_no(term.year_code, term.term_no, binding_grade)
                if binding.class_id:
                    target_classes = [db.query(SchoolClass).filter(
                        SchoolClass.id == int(binding.class_id),
                        SchoolClass.tenant_id == _tid(),
                        SchoolClass.class_status == "NORMAL",
                        SchoolClass.is_deleted.is_(False),
                    ).first()]
                else:
                    target_classes = db.query(SchoolClass).filter(
                        SchoolClass.tenant_id == _tid(),
                        SchoolClass.major_id == binding.major_id,
                        SchoolClass.grade == binding_grade,
                        SchoolClass.class_status == "NORMAL",
                        SchoolClass.is_deleted.is_(False),
                    ).all()
                target_classes = [row for row in target_classes if row]
                if not scope.all:
                    target_classes = [row for row in target_classes if int(row.id) in allowed_class_ids]

                if not target_classes:
                    items.append({
                        "key": f"program-{program.id}-binding-{binding.id}",
                        "programId": str(program.id), "programName": program.program_name,
                        "programStatus": program.status, "majorId": str(program.major_id or binding.major_id or ""),
                        "gradeYear": binding_grade or "", "classId": "", "className": "",
                        "courseId": "", "courseCode": "", "courseName": "", "planTermNo": plan_term,
                        "status": "NO_CLASS", "message": "有效方案绑定未匹配到正常在用行政班",
                        "taskIds": [], "teacherName": "", "responsibility": "PROGRAM_BINDING",
                        "fixRoute": f"/admin/academic-affairs/programs/{program.id}",
                    })
                    continue

                for clazz in target_classes:
                    if plan_term is None:
                        items.append({
                            "key": f"program-{program.id}-class-{clazz.id}-term-unresolved",
                            "programId": str(program.id), "programName": program.program_name,
                            "programStatus": program.status, "majorId": str(program.major_id or binding.major_id or ""),
                            "gradeYear": binding_grade or "", "classId": str(clazz.id),
                            "className": clazz.class_name, "courseId": "", "courseCode": "", "courseName": "",
                            "planTermNo": None, "status": "TERM_UNRESOLVED",
                            "message": "无法根据入学年级和当前学期推导方案学期；系统未猜测全部课程",
                            "taskIds": [], "teacherName": "", "responsibility": "PROGRAM_BINDING",
                            "fixRoute": f"/admin/academic-affairs/programs/{program.id}",
                        })
                        continue

                    selected_courses = [row for row in program_courses if int(row.open_term_no or 0) == int(plan_term)]
                    for program_course in selected_courses:
                        catalog = db.query(AaCourse).filter(
                            AaCourse.id == int(program_course.course_id or 0),
                            AaCourse.tenant_id == _tid(),
                            AaCourse.is_deleted.is_(False),
                        ).first() if program_course.course_id else None
                        key = (int(program_course.course_id or 0), int(clazz.id))
                        matched_tasks = task_map.get(key, []) if program_course.course_id else []
                        item_status, message = _task_row_status(program_course, catalog, matched_tasks)
                        if program_course.course_id:
                            expected_keys.add(key)
                        task = matched_tasks[0] if len(matched_tasks) == 1 else None
                        items.append({
                            "key": f"program-{program.id}-class-{clazz.id}-course-{program_course.id}",
                            "programId": str(program.id), "programName": program.program_name,
                            "programStatus": program.status, "majorId": str(program.major_id or binding.major_id or ""),
                            "gradeYear": binding_grade or "", "classId": str(clazz.id), "className": clazz.class_name,
                            "courseId": str(program_course.course_id or ""),
                            "courseCode": catalog.course_code if catalog else "",
                            "courseName": program_course.course_name or (catalog.course_name if catalog else ""),
                            "planTermNo": plan_term, "status": item_status, "message": message,
                            "taskIds": [str(row.id) for row in matched_tasks],
                            "teacherName": task.teacher_name if task else "",
                            "responsibility": "TEACHING_TASK" if item_status in {
                                "MISSING_TASK", "DUPLICATE_TASK", "NO_TEACHER", "HOURS_MISMATCH"
                            } else "PROGRAM_COURSE",
                            "fixRoute": (
                                "/admin/academic-affairs/teaching-tasks"
                                if item_status in {"MISSING_TASK", "DUPLICATE_TASK", "NO_TEACHER", "HOURS_MISMATCH"}
                                else f"/admin/academic-affairs/programs/{program.id}"
                            ),
                        })

        for task in tasks:
            key = (int(task.course_id), int(task.class_id or 0))
            if key in expected_keys:
                continue
            clazz = db.query(SchoolClass).filter(
                SchoolClass.id == int(task.class_id or 0),
                SchoolClass.tenant_id == _tid(),
                SchoolClass.is_deleted.is_(False),
            ).first() if task.class_id else None
            major_value = int(clazz.major_id) if clazz and clazz.major_id else None
            if major_id and major_value != int(major_id):
                continue
            if not scope.all and (not task.class_id or int(task.class_id) not in allowed_class_ids):
                continue
            items.append({
                "key": f"over-opened-task-{task.id}",
                "programId": "", "programName": "", "programStatus": "",
                "majorId": str(major_value or ""), "gradeYear": getattr(clazz, "grade", "") or "",
                "classId": str(task.class_id or ""),
                "className": getattr(clazz, "class_name", "") or task.teaching_class_name or "",
                "courseId": str(task.course_id), "courseCode": task.course_code or "",
                "courseName": task.course_name or "", "planTermNo": None,
                "status": "OVER_OPENED", "message": "教学任务存在，但不属于当前生效方案本学期应开课程",
                "taskIds": [str(task.id)], "teacherName": task.teacher_name or "",
                "responsibility": "TEACHING_TASK", "fixRoute": "/admin/academic-affairs/teaching-tasks",
            })

        items.sort(key=lambda row: (
            0 if row["status"] != "READY" else 1,
            row.get("majorId") or "", row.get("gradeYear") or "",
            row.get("className") or "", row.get("courseCode") or row.get("courseName") or "",
        ))
        full_summary = _summary(items)
        display_items = [row for row in items if row["status"] == active_filter] if active_filter else items
        return {
            "termId": str(term.id),
            "termCode": f"{term.year_code}-{term.term_no}",
            "activeProgramStatuses": sorted(_ACTIVE_PROGRAM_STATUSES),
            "summary": full_summary,
            "filteredTotal": len(display_items),
            "activeFilter": active_filter,
            "items": display_items,
        }
