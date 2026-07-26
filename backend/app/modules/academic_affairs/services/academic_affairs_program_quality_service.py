"""V2-01 培养方案质量校验与开课差异只读模型。

事实源保持不变：AaProgram/AaProgramCourse/AaProgramBinding/AaCourse/AaTeachingTask。
本模块不建立“教学执行计划”第二主表，只提供可解释校验结果和方案应开与教学任务实开的差异投影。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

_LEVEL_ORDER = {"BLOCKER": 0, "WARNING": 1, "INFO": 2}
_ACTIVE_PROGRAM_STATUSES = {"PUBLISHED", "ENABLED", "FROZEN"}


def _number(value, default=0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _safe_json(value, default):
    if not value:
        return default
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, type(default)) else default
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _issue(rule_code, level, message, *, object_id=None, field_path="", suggestion="", fix_route=""):
    return {
        "ruleCode": rule_code,
        "level": level,
        "objectId": str(object_id or ""),
        "fieldPath": field_path,
        "message": message,
        "suggestion": suggestion,
        "fixRoute": fix_route,
    }


def _plan_term_no(year_code: str | None, term_no: int | None, grade_year: str | None) -> int | None:
    """按入学年级和学年学期推导培养方案第几学期。"""
    try:
        start_year = int(str(year_code or "").split("-")[0])
        grade = int(str(grade_year or "").strip())
        term = int(term_no or 0)
    except (TypeError, ValueError):
        return None
    value = (start_year - grade) * 2 + term
    return value if 1 <= value <= 12 else None


def validate_program_db(db, program_id: int) -> dict:
    from app.models import (
        AaCourse,
        AaProgram,
        AaProgramBinding,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
        NationalStandardDocument,
        SchoolMajorStandardBinding,
    )

    program = db.query(AaProgram).filter(
        AaProgram.id == int(program_id),
        AaProgram.tenant_id == _tid(),
        AaProgram.is_deleted.is_(False),
    ).first()
    if not program:
        raise not_found("培养方案不存在")

    courses = db.query(AaProgramCourse).filter(
        AaProgramCourse.tenant_id == _tid(),
        AaProgramCourse.program_id == program.id,
        AaProgramCourse.is_deleted.is_(False),
    ).order_by(AaProgramCourse.open_term_no, AaProgramCourse.id).all()
    requirements = db.query(AaProgramGraduationRequirement).filter(
        AaProgramGraduationRequirement.tenant_id == _tid(),
        AaProgramGraduationRequirement.program_id == program.id,
        AaProgramGraduationRequirement.status == "ACTIVE",
        AaProgramGraduationRequirement.is_deleted.is_(False),
    ).all()
    practices = db.query(AaProgramPracticeSegment).filter(
        AaProgramPracticeSegment.tenant_id == _tid(),
        AaProgramPracticeSegment.program_id == program.id,
        AaProgramPracticeSegment.status == "ACTIVE",
        AaProgramPracticeSegment.is_deleted.is_(False),
    ).all()
    bindings = db.query(AaProgramBinding).filter(
        AaProgramBinding.tenant_id == _tid(),
        AaProgramBinding.program_id == program.id,
        AaProgramBinding.is_deleted.is_(False),
    ).all()

    course_ids = sorted({int(row.course_id) for row in courses if row.course_id})
    catalog_rows = db.query(AaCourse).filter(
        AaCourse.tenant_id == _tid(), AaCourse.id.in_(course_ids),
        AaCourse.is_deleted.is_(False),
    ).all() if course_ids else []
    catalog_by_id = {int(row.id): row for row in catalog_rows}
    enabled_codes = {
        str(code) for (code,) in db.query(AaCourse.course_code).filter(
            AaCourse.tenant_id == _tid(),
            AaCourse.status == "ENABLED",
            AaCourse.is_deleted.is_(False),
        ).all() if code
    }

    issues = []
    fix_route = f"/admin/academic-affairs/programs/{program.id}"
    if not (program.program_name or "").strip():
        issues.append(_issue("PROGRAM_NAME_REQUIRED", "BLOCKER", "方案名称为空", object_id=program.id,
                             field_path="programName", suggestion="填写能够识别专业和年级的方案名称", fix_route=fix_route))
    if not program.major_id:
        issues.append(_issue("PROGRAM_MAJOR_REQUIRED", "BLOCKER", "方案未绑定专业", object_id=program.id,
                             field_path="majorId", suggestion="选择适用专业", fix_route=fix_route))
    if not (program.grade_year or "").strip():
        issues.append(_issue("PROGRAM_GRADE_REQUIRED", "BLOCKER", "方案未填写适用年级", object_id=program.id,
                             field_path="gradeYear", suggestion="填写四位入学年级", fix_route=fix_route))
    elif not str(program.grade_year).isdigit() or len(str(program.grade_year)) != 4:
        issues.append(_issue("PROGRAM_GRADE_INVALID", "BLOCKER", "适用年级必须为四位年份", object_id=program.id,
                             field_path="gradeYear", suggestion="例如 2026", fix_route=fix_route))
    if program.total_credits is None or _number(program.total_credits) <= 0:
        issues.append(_issue("TOTAL_CREDIT_REQUIRED", "BLOCKER", "毕业总学分未设置或不大于0", object_id=program.id,
                             field_path="totalCredits", suggestion="按学校人才培养要求填写毕业总学分", fix_route=fix_route))
    if not courses:
        issues.append(_issue("PROGRAM_COURSE_EMPTY", "BLOCKER", "方案内没有课程", object_id=program.id,
                             field_path="courses", suggestion="从课程库添加本方案课程", fix_route=fix_route))

    seen = {}
    module_actual = defaultdict(float)
    credit_sum = 0.0
    for row in courses:
        row_route = f"{fix_route}?focus=course-{row.id}"
        identity = f"id:{row.course_id}" if row.course_id else f"name:{(row.course_name or '').strip().lower()}"
        if identity in seen:
            issues.append(_issue("DUPLICATE_COURSE", "BLOCKER", f"课程重复：{row.course_name or row.course_id}",
                                 object_id=row.id, field_path="courses", suggestion="保留一条并核对开课学期",
                                 fix_route=row_route))
        else:
            seen[identity] = row.id
        if not row.course_id:
            issues.append(_issue("COURSE_ID_REQUIRED", "BLOCKER", f"课程“{row.course_name or '未命名'}”未关联课程库",
                                 object_id=row.id, field_path="courseId", suggestion="从已启用课程库重新选择课程",
                                 fix_route=row_route))
        catalog = catalog_by_id.get(int(row.course_id)) if row.course_id else None
        if row.course_id and not catalog:
            issues.append(_issue("COURSE_NOT_FOUND", "BLOCKER", f"课程库记录不存在或已删除：{row.course_name or row.course_id}",
                                 object_id=row.id, field_path="courseId", suggestion="替换为有效课程版本",
                                 fix_route=row_route))
        elif catalog and catalog.status != "ENABLED":
            issues.append(_issue("COURSE_NOT_ENABLED", "BLOCKER", f"课程“{catalog.course_name}”当前状态为 {catalog.status}",
                                 object_id=row.id, field_path="courseId", suggestion="启用课程或替换课程版本",
                                 fix_route=row_route))
        if not row.course_name:
            issues.append(_issue("COURSE_NAME_REQUIRED", "BLOCKER", "方案课程名称为空", object_id=row.id,
                                 field_path="courseName", suggestion="从课程库刷新课程快照", fix_route=row_route))
        if row.open_term_no is None or not 1 <= int(row.open_term_no or 0) <= 12:
            issues.append(_issue("OPEN_TERM_INVALID", "BLOCKER", f"课程“{row.course_name or row.id}”开课学期无效",
                                 object_id=row.id, field_path="openTermNo", suggestion="填写1—12学期",
                                 fix_route=row_route))
        module = (row.module or "").strip()
        if not module:
            issues.append(_issue("COURSE_MODULE_REQUIRED", "BLOCKER", f"课程“{row.course_name or row.id}”未归入课程模块",
                                 object_id=row.id, field_path="module", suggestion="选择公共基础、专业核心、实践等模块",
                                 fix_route=row_route))
        credit = _number(row.credit_snapshot)
        if row.credit_snapshot is None or credit <= 0:
            issues.append(_issue("COURSE_CREDIT_INVALID", "BLOCKER", f"课程“{row.course_name or row.id}”学分未设置或不大于0",
                                 object_id=row.id, field_path="credit", suggestion="使用课程库正式学分快照",
                                 fix_route=row_route))
        else:
            credit_sum += credit
            if module:
                module_actual[module] += credit
        if catalog and row.credit_snapshot is not None and abs(credit - _number(catalog.credit)) > 0.001:
            issues.append(_issue("COURSE_CREDIT_SNAPSHOT_MISMATCH", "WARNING",
                                 f"课程“{catalog.course_name}”方案学分 {credit:g} 与课程库 { _number(catalog.credit):g } 不一致",
                                 object_id=row.id, field_path="credit", suggestion="确认是否保留历史快照或更新课程版本",
                                 fix_route=row_route))
        if catalog:
            component_hours = sum(int(value or 0) for value in (
                catalog.hours_theory, catalog.hours_practice, catalog.hours_experiment, catalog.hours_computer))
            total_hours = int(catalog.hours_total or 0)
            if total_hours <= 0:
                issues.append(_issue("COURSE_HOURS_MISSING", "WARNING", f"课程“{catalog.course_name}”未设置总学时",
                                     object_id=row.id, field_path="course.hoursTotal", suggestion="完善课程库学时结构",
                                     fix_route="/admin/academic-affairs/courses"))
            elif component_hours > total_hours:
                issues.append(_issue("COURSE_HOURS_OVERFLOW", "BLOCKER",
                                     f"课程“{catalog.course_name}”分项学时 {component_hours} 超过总学时 {total_hours}",
                                     object_id=row.id, field_path="course.hours", suggestion="修正课程库学时结构",
                                     fix_route="/admin/academic-affairs/courses"))
            elif component_hours and component_hours != total_hours:
                issues.append(_issue("COURSE_HOURS_MISMATCH", "WARNING",
                                     f"课程“{catalog.course_name}”分项学时 {component_hours} 与总学时 {total_hours} 不一致",
                                     object_id=row.id, field_path="course.hours", suggestion="确认是否存在其他学时类型",
                                     fix_route="/admin/academic-affairs/courses"))
            prereqs = _safe_json(catalog.prerequisite_codes_json, [])
            missing_prereqs = [str(code) for code in prereqs if str(code) not in enabled_codes]
            if missing_prereqs:
                issues.append(_issue("PREREQUISITE_UNRESOLVED", "WARNING",
                                     f"课程“{catalog.course_name}”先修课程不存在或未启用：{'、'.join(missing_prereqs[:5])}",
                                     object_id=row.id, field_path="course.prerequisites", suggestion="修正课程库先修关系",
                                     fix_route="/admin/academic-affairs/courses"))

    total_target = _number(program.total_credits)
    if total_target > 0:
        if credit_sum + 0.001 < total_target:
            issues.append(_issue("TOTAL_CREDIT_INSUFFICIENT", "BLOCKER",
                                 f"课程学分合计 {credit_sum:g} 未达到毕业总学分 {total_target:g}",
                                 object_id=program.id, field_path="totalCredits", suggestion="补充课程或调整毕业总学分",
                                 fix_route=fix_route))
        elif credit_sum - total_target > 0.001:
            issues.append(_issue("TOTAL_CREDIT_EXCEEDED", "WARNING",
                                 f"课程学分合计 {credit_sum:g} 超出毕业总学分 {total_target:g}",
                                 object_id=program.id, field_path="totalCredits", suggestion="确认超出学分是否属于选修冗余",
                                 fix_route=fix_route))

    requirement = _safe_json(program.requirement_json, {})
    structure = requirement.get("creditStructure") or []
    if not structure:
        issues.append(_issue("CREDIT_STRUCTURE_EMPTY", "BLOCKER", "尚未配置分模块学分要求",
                             object_id=program.id, field_path="requirement.creditStructure",
                             suggestion="配置公共基础、专业、实践等模块目标学分", fix_route=fix_route))
    target_by_module = {}
    for item in structure:
        module = str(item.get("module") or "").strip()
        if not module:
            issues.append(_issue("CREDIT_STRUCTURE_MODULE_EMPTY", "BLOCKER", "学分结构存在空模块名称",
                                 object_id=program.id, field_path="requirement.creditStructure",
                                 suggestion="填写模块名称", fix_route=fix_route))
            continue
        if module in target_by_module:
            issues.append(_issue("CREDIT_STRUCTURE_DUPLICATE", "BLOCKER", f"学分结构模块重复：{module}",
                                 object_id=program.id, field_path="requirement.creditStructure",
                                 suggestion="合并重复模块", fix_route=fix_route))
        target_by_module[module] = _number(item.get("creditTarget"))
    if target_by_module and total_target > 0:
        target_sum = sum(target_by_module.values())
        if abs(target_sum - total_target) > 0.001:
            issues.append(_issue("MODULE_TARGET_SUM_MISMATCH", "BLOCKER",
                                 f"模块目标学分合计 {target_sum:g} 与毕业总学分 {total_target:g} 不一致",
                                 object_id=program.id, field_path="requirement.creditStructure",
                                 suggestion="调整模块目标，使其与毕业总学分一致", fix_route=fix_route))
    for module, actual in module_actual.items():
        if target_by_module and module not in target_by_module:
            issues.append(_issue("COURSE_MODULE_UNKNOWN", "BLOCKER", f"课程模块“{module}”未配置目标学分",
                                 object_id=program.id, field_path="requirement.creditStructure",
                                 suggestion="在学分结构中增加该模块或调整课程归类", fix_route=fix_route))
    for module, target in target_by_module.items():
        actual = module_actual.get(module, 0.0)
        if actual + 0.001 < target:
            issues.append(_issue("MODULE_CREDIT_INSUFFICIENT", "BLOCKER",
                                 f"模块“{module}”已排 {actual:g} 学分，低于目标 {target:g}",
                                 object_id=program.id, field_path="requirement.creditStructure",
                                 suggestion="补充该模块课程或调整目标", fix_route=fix_route))

    if not requirements:
        issues.append(_issue("GRADUATION_REQUIREMENT_EMPTY", "BLOCKER", "尚未配置结构化毕业要求",
                             object_id=program.id, field_path="graduationRequirements",
                             suggestion="至少配置知识、能力、素质或职业证书要求", fix_route=fix_route))
    practice_names = Counter((row.segment_name or "").strip() for row in practices)
    for row in practices:
        if not (row.segment_name or "").strip():
            issues.append(_issue("PRACTICE_NAME_REQUIRED", "BLOCKER", "实践环节名称为空", object_id=row.id,
                                 field_path="practiceSegments.segmentName", suggestion="填写实践环节名称", fix_route=fix_route))
        if row.open_term_no is None or not 1 <= int(row.open_term_no or 0) <= 12:
            issues.append(_issue("PRACTICE_TERM_INVALID", "BLOCKER", f"实践环节“{row.segment_name or row.id}”学期无效",
                                 object_id=row.id, field_path="practiceSegments.openTermNo", suggestion="填写1—12学期",
                                 fix_route=fix_route))
        if row.weeks is None or _number(row.weeks) <= 0:
            issues.append(_issue("PRACTICE_WEEKS_INVALID", "BLOCKER", f"实践环节“{row.segment_name or row.id}”周数无效",
                                 object_id=row.id, field_path="practiceSegments.weeks", suggestion="填写大于0的实践周数",
                                 fix_route=fix_route))
        if practice_names[(row.segment_name or "").strip()] > 1:
            issues.append(_issue("PRACTICE_DUPLICATE", "WARNING", f"实践环节名称重复：{row.segment_name}",
                                 object_id=row.id, field_path="practiceSegments", suggestion="确认是否需要合并",
                                 fix_route=fix_route))
    if not practices:
        issues.append(_issue("PRACTICE_SEGMENT_EMPTY", "WARNING", "方案尚未配置集中性实践教学环节",
                             object_id=program.id, field_path="practiceSegments",
                             suggestion="职业院校方案通常应配置实习、课程设计或毕业设计等实践环节", fix_route=fix_route))

    active_bindings = [row for row in bindings if row.status == "ACTIVE"]
    binding_keys = Counter((row.major_id, row.grade_year, row.class_id) for row in active_bindings)
    for row in active_bindings:
        key = (row.major_id, row.grade_year, row.class_id)
        if binding_keys[key] > 1:
            issues.append(_issue("ACTIVE_BINDING_DUPLICATE", "BLOCKER", "同一专业、年级、班级存在重复有效绑定",
                                 object_id=row.id, field_path="bindings", suggestion="只保留一个ACTIVE绑定",
                                 fix_route=fix_route))
        if program.major_id and row.major_id != program.major_id:
            issues.append(_issue("BINDING_MAJOR_MISMATCH", "BLOCKER", "方案绑定专业与方案主档专业不一致",
                                 object_id=row.id, field_path="bindings.majorId", suggestion="修正绑定范围",
                                 fix_route=fix_route))
        if program.grade_year and row.grade_year and str(row.grade_year) != str(program.grade_year):
            issues.append(_issue("BINDING_GRADE_MISMATCH", "WARNING", "绑定年级与方案适用年级不一致",
                                 object_id=row.id, field_path="bindings.gradeYear", suggestion="确认是否为特例绑定",
                                 fix_route=fix_route))
    if program.status == "ENABLED" and not active_bindings:
        issues.append(_issue("ACTIVE_BINDING_MISSING", "BLOCKER", "启用方案没有有效专业年级/班级绑定",
                             object_id=program.id, field_path="bindings", suggestion="发布后绑定适用年级或班级",
                             fix_route=fix_route))

    standard_bound = False
    if program.major_id:
        standard_bound = db.query(SchoolMajorStandardBinding).join(
            NationalStandardDocument, NationalStandardDocument.id == SchoolMajorStandardBinding.document_id,
        ).filter(
            SchoolMajorStandardBinding.tenant_id == _tid(),
            SchoolMajorStandardBinding.school_major_id == program.major_id,
            SchoolMajorStandardBinding.binding_status == "ACTIVE",
            SchoolMajorStandardBinding.is_deleted.is_(False),
            NationalStandardDocument.is_deleted.is_(False),
        ).first() is not None
    if program.major_id and not standard_bound:
        issues.append(_issue("NATIONAL_STANDARD_UNBOUND", "WARNING", "专业尚未绑定有效国家教学标准",
                             object_id=program.id, field_path="nationalStandards",
                             suggestion="在实施与预设中心绑定对应国家专业教学标准",
                             fix_route="/admin/system/implementation/standards"))

    issues.sort(key=lambda item: (_LEVEL_ORDER.get(item["level"], 9), item["ruleCode"], item["objectId"]))
    counts = Counter(item["level"] for item in issues)
    return {
        "programId": str(program.id),
        "programName": program.program_name,
        "status": program.status,
        "creditSum": round(credit_sum, 2),
        "totalCredits": _number(program.total_credits) if program.total_credits is not None else None,
        "courseCount": len(courses),
        "practiceCount": len(practices),
        "activeBindingCount": len(active_bindings),
        "counts": {"blocker": counts["BLOCKER"], "warning": counts["WARNING"], "info": counts["INFO"]},
        "canSubmit": counts["BLOCKER"] == 0,
        "conclusion": "校验通过，可提交审核" if counts["BLOCKER"] == 0 else f"存在 {counts['BLOCKER']} 个阻断项",
        "issues": issues,
    }


def validate_program(user, program_id: int) -> dict:
    with session() as db:
        return validate_program_db(db, program_id)


def program_governance_summary(user) -> dict:
    from app.models import AaProgram
    with session() as db:
        rows = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(), AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.id.desc()).all()
        items = []
        for row in rows:
            result = validate_program_db(db, row.id)
            items.append({
                "programId": str(row.id), "programName": row.program_name,
                "majorId": str(row.major_id or ""), "gradeYear": row.grade_year or "",
                "version": row.version, "status": row.status,
                "totalCredits": _number(row.total_credits) if row.total_credits is not None else None,
                "courseCount": result["courseCount"], "blockerCount": result["counts"]["blocker"],
                "warningCount": result["counts"]["warning"], "canSubmit": result["canSubmit"],
                "conclusion": result["conclusion"],
            })
        return {
            "totalPrograms": len(items),
            "readyPrograms": sum(1 for item in items if item["canSubmit"]),
            "blockedPrograms": sum(1 for item in items if not item["canSubmit"]),
            "missingMajor": sum(1 for row in rows if not row.major_id),
            "missingGrade": sum(1 for row in rows if not row.grade_year),
            "items": items,
        }


def opening_differences(user, term_id: int, major_id: int | None = None, grade_year: str | None = None,
                        status: str | None = None) -> dict:
    from app.models import (
        AaCourse, AaProgram, AaProgramBinding, AaProgramCourse, AaTeachingTask,
        AaTeachingTaskBatch, AaTerm, Major, SchoolClass,
    )
    from app.modules.academic_affairs.services.academic_affairs_stats_service import _resolve_scope

    with session() as db:
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id), AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            raise not_found("学期不存在")
        scope = _resolve_scope(user, db)
        programs = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(), AaProgram.status == "ENABLED",
            AaProgram.is_deleted.is_(False),
        ).all()
        if major_id:
            programs = [row for row in programs if int(row.major_id or 0) == int(major_id)]
        if grade_year:
            programs = [row for row in programs if str(row.grade_year or "") == str(grade_year)]

        batch_ids = [value for (value,) in db.query(AaTeachingTaskBatch.id).filter(
            AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term.id,
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).all()]
        existing_tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id.in_(batch_ids),
            AaTeachingTask.status != "MERGED", AaTeachingTask.is_deleted.is_(False),
        ).all() if batch_ids else []
        task_map = defaultdict(list)
        for task in existing_tasks:
            task_map[(int(task.course_id), int(task.class_id or 0))].append(task)

        rows = []
        for program in programs:
            bindings = db.query(AaProgramBinding).filter(
                AaProgramBinding.tenant_id == _tid(), AaProgramBinding.program_id == program.id,
                AaProgramBinding.status == "ACTIVE", AaProgramBinding.is_deleted.is_(False),
            ).all()
            program_courses = db.query(AaProgramCourse).filter(
                AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == program.id,
                AaProgramCourse.is_deleted.is_(False),
            ).all()
            for binding in bindings:
                plan_term = _plan_term_no(term.year_code, term.term_no, binding.grade_year or program.grade_year)
                if binding.class_id:
                    target_classes = [db.get(SchoolClass, int(binding.class_id))]
                else:
                    target_classes = db.query(SchoolClass).filter(
                        SchoolClass.tenant_id == _tid(), SchoolClass.major_id == binding.major_id,
                        SchoolClass.grade == (binding.grade_year or program.grade_year),
                        SchoolClass.class_status == "NORMAL", SchoolClass.is_deleted.is_(False),
                    ).all()
                target_classes = [row for row in target_classes if row]
                if not scope.all:
                    if scope.class_ids:
                        target_classes = [row for row in target_classes if int(row.id) in scope.class_ids]
                    elif scope.college_ids:
                        allowed = set(scope.college_ids)
                        target_classes = [row for row in target_classes if row.major_id and (
                            (db.get(Major, int(row.major_id))).college_id if db.get(Major, int(row.major_id)) else None
                        ) in allowed]
                    else:
                        target_classes = []
                if not target_classes:
                    rows.append({
                        "key": f"program-{program.id}-binding-{binding.id}",
                        "programId": str(program.id), "programName": program.program_name,
                        "gradeYear": binding.grade_year or program.grade_year or "", "classId": "", "className": "",
                        "courseId": "", "courseCode": "", "courseName": "", "planTermNo": plan_term,
                        "status": "NO_CLASS", "message": "有效方案绑定未匹配到可用行政班",
                        "taskIds": [], "teacherName": "",
                    })
                    continue
                selected_courses = [row for row in program_courses if plan_term and row.open_term_no == plan_term]
                if plan_term is None:
                    selected_courses = program_courses
                for clazz in target_classes:
                    if plan_term is None:
                        rows.append({
                            "key": f"program-{program.id}-class-{clazz.id}-term-unresolved",
                            "programId": str(program.id), "programName": program.program_name,
                            "gradeYear": binding.grade_year or program.grade_year or "", "classId": str(clazz.id),
                            "className": clazz.class_name, "courseId": "", "courseCode": "", "courseName": "",
                            "planTermNo": None, "status": "TERM_UNRESOLVED",
                            "message": "无法根据入学年级和当前学期推导方案学期", "taskIds": [], "teacherName": "",
                        })
                    for pc in selected_courses:
                        catalog = db.get(AaCourse, int(pc.course_id)) if pc.course_id else None
                        if not pc.course_id or not catalog:
                            item_status = "COURSE_UNRESOLVED"
                            message = "方案课程未关联有效课程库记录"
                            tasks = []
                        else:
                            tasks = task_map.get((int(pc.course_id), int(clazz.id)), [])
                            if not tasks:
                                item_status, message = "MISSING_TASK", "方案应开课程尚未生成教学任务"
                            elif len(tasks) > 1:
                                item_status, message = "DUPLICATE_TASK", f"同一课程班级存在 {len(tasks)} 条教学任务"
                            elif abs(_number(pc.credit_snapshot) - _number(catalog.credit)) > 0.001:
                                item_status, message = "CREDIT_MISMATCH", "方案学分快照与课程库当前学分不一致"
                            elif not tasks[0].teacher_key:
                                item_status, message = "NO_TEACHER", "教学任务尚未绑定稳定教师工号"
                            else:
                                item_status, message = "READY", "方案应开与教学任务一致"
                        task = tasks[0] if len(tasks) == 1 else None
                        rows.append({
                            "key": f"program-{program.id}-class-{clazz.id}-course-{pc.id}",
                            "programId": str(program.id), "programName": program.program_name,
                            "gradeYear": binding.grade_year or program.grade_year or "", "classId": str(clazz.id),
                            "className": clazz.class_name, "courseId": str(pc.course_id or ""),
                            "courseCode": catalog.course_code if catalog else "", "courseName": pc.course_name or (catalog.course_name if catalog else ""),
                            "planTermNo": plan_term, "status": item_status, "message": message,
                            "taskIds": [str(item.id) for item in tasks], "teacherName": task.teacher_name if task else "",
                        })

        if status:
            rows = [row for row in rows if row["status"] == status]
        counts = Counter(row["status"] for row in rows)
        return {
            "termId": str(term.id), "termCode": f"{term.year_code}-{term.term_no}",
            "summary": {
                "total": len(rows), "ready": counts["READY"],
                "missingTask": counts["MISSING_TASK"], "duplicateTask": counts["DUPLICATE_TASK"],
                "unresolved": counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"],
                "noTeacher": counts["NO_TEACHER"], "creditMismatch": counts["CREDIT_MISMATCH"],
            },
            "items": rows,
        }
