"""V2-01 培养方案质量最终层。

在首轮校验/差异读模型上补齐：
- 集中实践学分计入方案毕业总学分；
- 缺实践学分形成可解释阻断；
- 无法推导方案学期时不猜测全部课程；
- 已生成但不属于本学期方案应开的教学任务标记为 OVER_OPENED。
"""
from __future__ import annotations

from collections import Counter

from app.services.db_service import _tid, session

from . import academic_affairs_program_quality_service as _base


def __getattr__(name):
    return getattr(_base, name)


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
    result["issues"].sort(
        key=lambda item: (
            _base._LEVEL_ORDER.get(item["level"], 9),
            item["ruleCode"],
            item.get("objectId") or "",
        )
    )
    return result


def validate_program_db(db, program_id: int) -> dict:
    from app.models import AaProgram, AaProgramPracticeSegment

    result = _base.validate_program_db(db, program_id)
    program = db.query(AaProgram).filter(
        AaProgram.id == int(program_id),
        AaProgram.tenant_id == _tid(),
        AaProgram.is_deleted.is_(False),
    ).first()
    practices = db.query(AaProgramPracticeSegment).filter(
        AaProgramPracticeSegment.tenant_id == _tid(),
        AaProgramPracticeSegment.program_id == int(program_id),
        AaProgramPracticeSegment.status == "ACTIVE",
        AaProgramPracticeSegment.is_deleted.is_(False),
    ).all()

    practice_credit = 0.0
    for row in practices:
        if row.credit is None:
            result["issues"].append(_base._issue(
                "PRACTICE_CREDIT_MISSING",
                "BLOCKER",
                f"实践环节“{row.segment_name or row.id}”未设置学分",
                object_id=row.id,
                field_path="practiceSegments.credit",
                suggestion="填写实践环节学分，确保毕业总学分可核对",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))
        elif _base._number(row.credit) < 0:
            result["issues"].append(_base._issue(
                "PRACTICE_CREDIT_INVALID",
                "BLOCKER",
                f"实践环节“{row.segment_name or row.id}”学分不可为负数",
                object_id=row.id,
                field_path="practiceSegments.credit",
                suggestion="修正实践学分",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))
        else:
            practice_credit += _base._number(row.credit)

    course_credit = float(result.get("creditSum") or 0)
    total_credit = course_credit + practice_credit
    result["courseCreditSum"] = round(course_credit, 2)
    result["practiceCreditSum"] = round(practice_credit, 2)
    result["creditSum"] = round(total_credit, 2)

    # 首轮只按课程学分判断总学分；最终层统一按课程+独立实践环节重新计算。
    result["issues"] = [
        item for item in result["issues"]
        if item["ruleCode"] not in {"TOTAL_CREDIT_INSUFFICIENT", "TOTAL_CREDIT_EXCEEDED"}
    ]
    target = _base._number(program.total_credits) if program and program.total_credits is not None else 0.0
    if target > 0:
        if total_credit + 0.001 < target:
            result["issues"].append(_base._issue(
                "TOTAL_CREDIT_INSUFFICIENT",
                "BLOCKER",
                f"课程与实践学分合计 {total_credit:g} 未达到毕业总学分 {target:g}",
                object_id=program_id,
                field_path="totalCredits",
                suggestion="补充课程/实践环节或调整毕业总学分",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))
        elif total_credit - target > 0.001:
            result["issues"].append(_base._issue(
                "TOTAL_CREDIT_EXCEEDED",
                "WARNING",
                f"课程与实践学分合计 {total_credit:g} 超出毕业总学分 {target:g}",
                object_id=program_id,
                field_path="totalCredits",
                suggestion="确认超出部分是否属于选修冗余",
                fix_route=f"/admin/academic-affairs/programs/{program_id}",
            ))
    return _refresh_summary(result)


def validate_program(user, program_id: int) -> dict:
    with session() as db:
        return validate_program_db(db, program_id)


def program_governance_summary(user) -> dict:
    from app.models import AaProgram

    with session() as db:
        programs = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.id.desc()).all()
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
                "totalCredits": _base._number(row.total_credits) if row.total_credits is not None else None,
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


def opening_differences(user, term_id: int, major_id: int | None = None, grade_year: str | None = None,
                        status: str | None = None) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    result = _base.opening_differences(user, term_id, major_id, grade_year, None)
    items = list(result.get("items") or [])

    unresolved_pairs = {
        (item["programId"], item["classId"])
        for item in items if item["status"] == "TERM_UNRESOLVED"
    }
    if unresolved_pairs:
        items = [
            item for item in items
            if item["status"] == "TERM_UNRESOLVED"
            or (item["programId"], item["classId"]) not in unresolved_pairs
        ]

    expected_keys = {
        (int(item["courseId"]), int(item["classId"]))
        for item in items
        if str(item.get("courseId") or "").isdigit()
        and str(item.get("classId") or "").isdigit()
        and item["status"] != "TERM_UNRESOLVED"
    }
    with session() as db:
        batch_ids = [value for (value,) in db.query(AaTeachingTaskBatch.id).filter(
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.term_id == int(term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).all()]
        tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id.in_(batch_ids),
            AaTeachingTask.status != "MERGED",
            AaTeachingTask.is_deleted.is_(False),
        ).all() if batch_ids else []
        for task in tasks:
            key = (int(task.course_id), int(task.class_id or 0))
            if key in expected_keys:
                continue
            items.append({
                "key": f"over-opened-task-{task.id}",
                "programId": "",
                "programName": "",
                "gradeYear": "",
                "classId": str(task.class_id or ""),
                "className": task.teaching_class_name or "",
                "courseId": str(task.course_id),
                "courseCode": task.course_code or "",
                "courseName": task.course_name or "",
                "planTermNo": None,
                "status": "OVER_OPENED",
                "message": "教学任务存在，但不属于当前有效方案本学期应开课程",
                "taskIds": [str(task.id)],
                "teacherName": task.teacher_name or "",
            })

    if status:
        items = [item for item in items if item["status"] == status]
    counts = Counter(item["status"] for item in items)
    result["items"] = items
    result["summary"] = {
        "total": len(items),
        "ready": counts["READY"],
        "missingTask": counts["MISSING_TASK"],
        "duplicateTask": counts["DUPLICATE_TASK"],
        "overOpened": counts["OVER_OPENED"],
        "unresolved": counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"],
        "noTeacher": counts["NO_TEACHER"],
        "creditMismatch": counts["CREDIT_MISMATCH"],
    }
    return result
