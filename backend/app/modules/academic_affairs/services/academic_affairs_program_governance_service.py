"""培养方案治理与开课差异服务。

核心结构校验复用 ``academic_affairs_program_quality_service``；本服务只补跨表规则、
数据范围和开课差异。无 Facade、无导入副作用、无第二套教学执行计划事实。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import not_found
from app.services.db_service import _tid, session

from . import academic_affairs_program_quality_service as validator

_ACTIVE_PROGRAM_STATUSES = {"PUBLISHED", "ENABLED", "FROZEN"}
_ALLOWED_DIFF_STATUSES = {
    "READY", "MISSING_TASK", "DUPLICATE_TASK", "OVER_OPENED",
    "NO_TEACHER", "CREDIT_MISMATCH", "HOURS_MISMATCH",
    "COURSE_UNRESOLVED", "TERM_UNRESOLVED", "NO_CLASS",
}


def _scope(user, db):
    ctx = build_affairs_context(user, db)
    scope_type = str(getattr(ctx, "scope_type", None) or "NONE").upper()
    if scope_type in {"NONE", "BLOCKED"}:
        raise no_data_scope("当前身份未配置可管理的学院或班级范围")
    return ctx


def _allowed_major_ids(db, scope) -> set[int]:
    from app.models import Major, SchoolClass

    if str(getattr(scope, "scope_type", "")).upper() == "TENANT_ALL":
        return set()
    major_ids = set()
    college_ids = {int(v) for v in (getattr(scope, "college_ids", None) or []) if str(v).isdigit()}
    class_ids = {int(v) for v in (getattr(scope, "class_ids", None) or []) if str(v).isdigit()}
    if college_ids:
        major_ids.update(
            int(value) for (value,) in db.query(Major.id).filter(
                Major.tenant_id == _tid(),
                Major.college_id.in_(sorted(college_ids)),
                Major.is_deleted.is_(False),
            ).all()
        )
    if class_ids:
        major_ids.update(
            int(value) for (value,) in db.query(SchoolClass.major_id).filter(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(sorted(class_ids)),
                SchoolClass.major_id.is_not(None),
                SchoolClass.is_deleted.is_(False),
            ).all() if value
        )
    return major_ids


def _ensure_program_scope(db, user, program_id: int):
    from app.models import AaProgram

    scope = _scope(user, db)
    program = db.query(AaProgram).filter(
        AaProgram.id == int(program_id),
        AaProgram.tenant_id == _tid(),
        AaProgram.is_deleted.is_(False),
    ).first()
    if not program:
        raise not_found("培养方案不存在")
    if str(getattr(scope, "scope_type", "")).upper() == "TENANT_ALL":
        return scope, program
    allowed_major_ids = _allowed_major_ids(db, scope)
    if not program.major_id or int(program.major_id) not in allowed_major_ids:
        raise no_data_scope("该培养方案不在当前学院或班级数据范围内")
    return scope, program


def _refresh_summary(result: dict) -> dict:
    counts = Counter(item["level"] for item in result.get("issues", []))
    result["counts"] = {
        "blocker": counts["BLOCKER"],
        "warning": counts["WARNING"],
        "info": counts["INFO"],
    }
    result["canSubmit"] = counts["BLOCKER"] == 0
    result["conclusion"] = (
        "校验通过，可提交审核"
        if counts["BLOCKER"] == 0
        else f"存在 {counts['BLOCKER']} 个阻断项"
    )
    result["issues"].sort(key=lambda item: (
        validator._LEVEL_ORDER.get(item["level"], 9),
        item["ruleCode"],
        item.get("objectId") or "",
    ))
    return result


def validate_program_db(db, program_id: int) -> dict:
    from app.models import AaProgram, AaProgramBinding, AaProgramPracticeSegment, SchoolClass

    result = validator.validate_program_db(db, program_id)
    program = db.query(AaProgram).filter(
        AaProgram.id == int(program_id),
        AaProgram.tenant_id == _tid(),
        AaProgram.is_deleted.is_(False),
    ).first()
    if not program:
        raise not_found("培养方案不存在")

    practices = db.query(AaProgramPracticeSegment).filter(
        AaProgramPracticeSegment.tenant_id == _tid(),
        AaProgramPracticeSegment.program_id == int(program_id),
        AaProgramPracticeSegment.status == "ACTIVE",
        AaProgramPracticeSegment.is_deleted.is_(False),
    ).all()
    practice_credit = 0.0
    for row in practices:
        if row.credit is None:
            result["issues"].append(validator._issue(
                "PRACTICE_CREDIT_MISSING", "BLOCKER",
                f"实践环节“{row.segment_name or row.id}”未设置学分",
                object_id=row.id, field_path="practiceSegments.credit",
                suggestion="填写实践环节学分，确保毕业总学分可核对",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))
        elif validator._number(row.credit) < 0:
            result["issues"].append(validator._issue(
                "PRACTICE_CREDIT_INVALID", "BLOCKER",
                f"实践环节“{row.segment_name or row.id}”学分不可为负数",
                object_id=row.id, field_path="practiceSegments.credit",
                suggestion="修正实践学分",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))
        else:
            practice_credit += validator._number(row.credit)

    course_credit = float(result.get("creditSum") or 0)
    total_credit = course_credit + practice_credit
    result["courseCreditSum"] = round(course_credit, 2)
    result["practiceCreditSum"] = round(practice_credit, 2)
    result["creditSum"] = round(total_credit, 2)
    result["issues"] = [
        item for item in result["issues"]
        if item["ruleCode"] not in {"TOTAL_CREDIT_INSUFFICIENT", "TOTAL_CREDIT_EXCEEDED"}
    ]
    target = validator._number(program.total_credits) if program.total_credits is not None else 0.0
    if target > 0:
        if total_credit + 0.001 < target:
            result["issues"].append(validator._issue(
                "TOTAL_CREDIT_INSUFFICIENT", "BLOCKER",
                f"课程与实践学分合计 {total_credit:g} 未达到毕业总学分 {target:g}",
                object_id=program_id, field_path="totalCredits",
                suggestion="补充课程/实践环节或调整毕业总学分",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))
        elif total_credit - target > 0.001:
            result["issues"].append(validator._issue(
                "TOTAL_CREDIT_EXCEEDED", "WARNING",
                f"课程与实践学分合计 {total_credit:g} 超出毕业总学分 {target:g}",
                object_id=program_id, field_path="totalCredits",
                suggestion="确认超出部分是否属于选修冗余",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))

    bindings = db.query(AaProgramBinding).filter(
        AaProgramBinding.tenant_id == _tid(),
        AaProgramBinding.program_id == int(program_id),
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    ).all()
    for binding in bindings:
        route = f"/admin/academic-affairs/programs/{program_id}"
        if binding.class_id:
            clazz = db.query(SchoolClass).filter(
                SchoolClass.id == int(binding.class_id),
                SchoolClass.tenant_id == _tid(),
                SchoolClass.is_deleted.is_(False),
            ).first()
            if not clazz:
                result["issues"].append(validator._issue(
                    "BINDING_CLASS_NOT_FOUND", "BLOCKER",
                    f"班级特例绑定指向不存在或已删除班级：{binding.class_id}",
                    object_id=binding.id, field_path="bindings.classId",
                    suggestion="删除失效绑定或重新选择本校班级", fix_route=route,
                ))
            else:
                if binding.major_id and clazz.major_id and int(binding.major_id) != int(clazz.major_id):
                    result["issues"].append(validator._issue(
                        "BINDING_CLASS_MAJOR_MISMATCH", "BLOCKER",
                        f"班级“{clazz.class_name}”所属专业与方案绑定专业不一致",
                        object_id=binding.id, field_path="bindings.classId",
                        suggestion="修正班级特例或专业绑定", fix_route=route,
                    ))
                if binding.grade_year and str(clazz.grade or "") != str(binding.grade_year):
                    result["issues"].append(validator._issue(
                        "BINDING_CLASS_GRADE_MISMATCH", "BLOCKER",
                        f"班级“{clazz.class_name}”年级与方案绑定年级不一致",
                        object_id=binding.id, field_path="bindings.gradeYear",
                        suggestion="修正绑定年级或选择正确班级", fix_route=route,
                    ))
                if str(clazz.class_status or "").upper() != "NORMAL":
                    result["issues"].append(validator._issue(
                        "BINDING_CLASS_INACTIVE", "BLOCKER",
                        f"班级“{clazz.class_name}”当前状态为 {clazz.class_status}，不可作为生效方案绑定",
                        object_id=binding.id, field_path="bindings.classId",
                        suggestion="选择正常在用班级或停用该绑定", fix_route=route,
                    ))

        conflicts = db.query(AaProgramBinding, AaProgram).join(
            AaProgram, AaProgram.id == AaProgramBinding.program_id,
        ).filter(
            AaProgramBinding.tenant_id == _tid(),
            AaProgramBinding.program_id != int(program_id),
            AaProgramBinding.major_id == binding.major_id,
            AaProgramBinding.grade_year == binding.grade_year,
            AaProgramBinding.class_id.is_(None) if binding.class_id is None else AaProgramBinding.class_id == binding.class_id,
            AaProgramBinding.status == "ACTIVE",
            AaProgramBinding.is_deleted.is_(False),
            AaProgram.tenant_id == _tid(),
            AaProgram.status.in_(sorted(_ACTIVE_PROGRAM_STATUSES)),
            AaProgram.is_deleted.is_(False),
        ).all()
        if conflicts:
            names = "、".join(str(other_program.program_name) for _binding, other_program in conflicts[:3])
            result["issues"].append(validator._issue(
                "ACTIVE_BINDING_CROSS_PROGRAM_CONFLICT", "BLOCKER",
                f"同一专业年级/班级已被其它生效方案绑定：{names}",
                object_id=binding.id, field_path="bindings",
                suggestion="只保留一个生效方案，旧版本改为SUPERSEDED或停用", fix_route=route,
            ))

    return _refresh_summary(result)


def validate_program(user, program_id: int) -> dict:
    with session() as db:
        _ensure_program_scope(db, user, program_id)
        return validate_program_db(db, program_id)


def program_governance_summary(user) -> dict:
    from app.models import AaProgram

    with session() as db:
        scope = _scope(user, db)
        tenant_all = str(getattr(scope, "scope_type", "")).upper() == "TENANT_ALL"
        allowed_major_ids = _allowed_major_ids(db, scope)
        programs = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.id.desc()).all()
        if not tenant_all:
            programs = [row for row in programs if row.major_id and int(row.major_id) in allowed_major_ids]

        items = []
        for row in programs:
            validation = validate_program_db(db, row.id)
            items.append({
                "programId": str(row.id),
                "programName": row.program_name,
                "majorId": str(row.major_id or ""),
                "gradeYear": row.grade_year or "",
                "version": row.version,
                "status": row.status,
                "totalCredits": float(row.total_credits) if row.total_credits is not None else None,
                "creditSum": validation["creditSum"],
                "courseCount": validation["courseCount"],
                "blockerCount": validation["counts"]["blocker"],
                "warningCount": validation["counts"]["warning"],
                "canSubmit": validation["canSubmit"],
                "conclusion": validation["conclusion"],
            })
        return {
            "totalPrograms": len(items),
            "readyPrograms": sum(1 for item in items if item["canSubmit"]),
            "blockedPrograms": sum(1 for item in items if not item["canSubmit"]),
            "missingMajor": sum(1 for row in programs if not row.major_id),
            "missingGrade": sum(1 for row in programs if not row.grade_year),
            "items": items,
        }


def _summary(items) -> dict:
    counts = Counter(str(item.get("status") or "") for item in items)
    blockers = (
        counts["MISSING_TASK"] + counts["DUPLICATE_TASK"] + counts["OVER_OPENED"]
        + counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"]
        + counts["CREDIT_MISMATCH"] + counts["HOURS_MISMATCH"]
    )
    return {
        "total": len(items), "ready": counts["READY"],
        "missingTask": counts["MISSING_TASK"], "duplicateTask": counts["DUPLICATE_TASK"],
        "overOpened": counts["OVER_OPENED"],
        "unresolved": counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"],
        "noTeacher": counts["NO_TEACHER"], "creditMismatch": counts["CREDIT_MISMATCH"],
        "hoursMismatch": counts["HOURS_MISMATCH"], "blockerCount": blockers,
        "canGenerateOrConfirm": blockers == 0,
        "conclusion": "本学期开课与有效培养方案一致" if blockers == 0 else f"存在 {blockers} 个开课阻断差异",
    }


def _task_row_status(program_course, catalog, tasks) -> tuple[str, str]:
    if not program_course.course_id or not catalog:
        return "COURSE_UNRESOLVED", "方案课程未关联有效课程库版本"
    if not tasks:
        return "MISSING_TASK", "方案应开课程尚未生成教学任务"
    if len(tasks) > 1:
        return "DUPLICATE_TASK", f"同一课程与行政班存在 {len(tasks)} 条教学任务"
    task = tasks[0]
    if abs(validator._number(program_course.credit_snapshot) - validator._number(catalog.credit)) > 0.001:
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
        AaTeachingTaskBatch, AaTerm, SchoolClass,
    )

    active_filter = str(status or "").strip().upper()
    if active_filter and active_filter not in _ALLOWED_DIFF_STATUSES:
        active_filter = ""

    with session() as db:
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id), AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            raise not_found("学期不存在")
        scope = _scope(user, db)
        tenant_all = str(getattr(scope, "scope_type", "")).upper() == "TENANT_ALL"
        allowed_major_ids = _allowed_major_ids(db, scope)
        allowed_class_ids = {int(v) for v in (getattr(scope, "class_ids", None) or []) if str(v).isdigit()}
        if not tenant_all and not allowed_class_ids and allowed_major_ids:
            allowed_class_ids = {
                int(value) for (value,) in db.query(SchoolClass.id).filter(
                    SchoolClass.tenant_id == _tid(),
                    SchoolClass.major_id.in_(sorted(allowed_major_ids)),
                    SchoolClass.class_status == "NORMAL",
                    SchoolClass.is_deleted.is_(False),
                ).all()
            }
        if major_id and not tenant_all and int(major_id) not in allowed_major_ids:
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
        if not tenant_all:
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
        if not tenant_all:
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
                plan_term = validator._plan_term_no(term.year_code, term.term_no, binding_grade)
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
                if not tenant_all:
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
                            "gradeYear": binding_grade or "", "classId": str(clazz.id), "className": clazz.class_name,
                            "courseId": "", "courseCode": "", "courseName": "", "planTermNo": None,
                            "status": "TERM_UNRESOLVED",
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
                            "fixRoute": "/admin/academic-affairs/teaching-tasks" if item_status in {
                                "MISSING_TASK", "DUPLICATE_TASK", "NO_TEACHER", "HOURS_MISMATCH"
                            } else f"/admin/academic-affairs/programs/{program.id}",
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
            items.append({
                "key": f"over-opened-task-{task.id}", "programId": "", "programName": "",
                "programStatus": "", "majorId": str(major_value or ""),
                "gradeYear": getattr(clazz, "grade", "") or "", "classId": str(task.class_id or ""),
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
            "termId": str(term.id), "termCode": f"{term.year_code}-{term.term_no}",
            "activeProgramStatuses": sorted(_ACTIVE_PROGRAM_STATUSES),
            "summary": full_summary, "filteredTotal": len(display_items),
            "activeFilter": active_filter, "items": display_items,
        }
