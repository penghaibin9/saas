"""教学任务生成的培养方案质量门禁。

最终教学任务服务继续复用教学周、当前方案学期和管理范围安全层；仅在生成前增加一次
“本次会被消费的 ENABLED 方案必须无 BLOCKER”检查，避免错误方案继续生成正式任务。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_task_security_facade as _base
from .academic_affairs_program_quality_final_service import validate_program_db
from .academic_affairs_program_quality_security_service import _allowed_major_ids

_original_generate_batch = _base.generate_batch


def __getattr__(name):
    return getattr(_base, name)


def _generation_programs(db, user, college_id=None):
    from app.models import AaProgram, Major

    scope = _base._scope(user, db)
    rows = db.query(AaProgram).filter(
        AaProgram.tenant_id == _tid(),
        AaProgram.status == "ENABLED",
        AaProgram.is_deleted.is_(False),
    ).all()

    if college_id:
        major_ids = {
            int(value) for (value,) in db.query(Major.id).filter(
                Major.tenant_id == _tid(),
                Major.college_id == int(college_id),
                Major.is_deleted.is_(False),
            ).all()
        }
        rows = [row for row in rows if row.major_id and int(row.major_id) in major_ids]
    elif not scope.all:
        allowed_major_ids = _allowed_major_ids(db, scope)
        rows = [
            row for row in rows
            if row.major_id and int(row.major_id) in allowed_major_ids
        ]
    return rows


def _generation_precheck(db, user, college_id=None) -> dict:
    programs = _generation_programs(db, user, college_id)
    if not programs:
        raise AppException(
            "PROGRAM_NOT_READY",
            "当前学院/数据范围没有已启用培养方案，不能生成教学任务",
            http_status=409,
        )

    blocked = []
    warning_count = 0
    for program in programs:
        result = validate_program_db(db, int(program.id))
        blockers = [item for item in result["issues"] if item["level"] == "BLOCKER"]
        warning_count += int(result["counts"]["warning"])
        if blockers:
            blocked.append({
                "programId": str(program.id),
                "programName": program.program_name,
                "blockerCount": len(blockers),
                "messages": [item["message"] for item in blockers[:3]],
            })

    if blocked:
        preview = "；".join(
            f"{item['programName']}：{'、'.join(item['messages'])}"
            for item in blocked[:3]
        )
        suffix = f"；另有 {len(blocked) - 3} 个方案" if len(blocked) > 3 else ""
        raise AppException(
            "PROGRAM_VALIDATION_BLOCKED",
            f"有 {len(blocked)} 个已启用方案存在阻断项，不能生成教学任务：{preview}{suffix}",
            http_status=409,
        )
    return {
        "programCount": len(programs),
        "warningCount": warning_count,
    }


def generate_batch(body, user) -> dict:
    college_id = int(body.collegeId) if getattr(body, "collegeId", None) else None
    with session() as db:
        precheck = _generation_precheck(db, user, college_id)

    result = _original_generate_batch(body, user)
    result["programValidation"] = {
        "programCount": precheck["programCount"],
        "warningCount": precheck["warningCount"],
        "conclusion": "已启用方案结构校验通过",
    }
    return result


# 防止后续完整路径直接命中下层任务facade绕过方案门禁。
_base.generate_batch = generate_batch
