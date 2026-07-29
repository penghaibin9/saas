"""V2-01 培养方案质量读侧安全层。

管理型质量工作台不复用统计域的宽口径：教务处/校管全校，学院和明确班级按统一数据范围，
普通任课教师未配置管理范围时 fail-closed。
"""
from __future__ import annotations

from app.core.affairs_security import no_data_scope
from app.services.db_service import _tid, session

from . import academic_affairs_program_quality_final_service as _base
from .academic_affairs_task_security_facade import _scope


def __getattr__(name):
    return getattr(_base, name)


def _allowed_major_ids(db, scope) -> set[int]:
    from app.models import Major, SchoolClass

    if scope.all:
        return set()
    major_ids = set()
    if scope.college_ids:
        major_ids.update(
            int(value) for (value,) in db.query(Major.id).filter(
                Major.tenant_id == _tid(),
                Major.college_id.in_(list(scope.college_ids)),
                Major.is_deleted.is_(False),
            ).all()
        )
    if scope.class_ids:
        major_ids.update(
            int(value) for (value,) in db.query(SchoolClass.major_id).filter(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(list(scope.class_ids)),
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
        return scope
    if scope.all:
        return scope
    allowed_major_ids = _allowed_major_ids(db, scope)
    if not program.major_id or int(program.major_id) not in allowed_major_ids:
        raise no_data_scope("该培养方案不在当前学院或班级数据范围内")
    return scope


def validate_program(user, program_id: int) -> dict:
    with session() as db:
        _ensure_program_scope(db, user, program_id)
        return _base.validate_program_db(db, program_id)


def program_governance_summary(user) -> dict:
    with session() as db:
        scope = _scope(user, db)
        allowed_major_ids = _allowed_major_ids(db, scope)
    result = _base.program_governance_summary(user)
    if scope.all:
        return result
    items = [
        item for item in result.get("items", [])
        if str(item.get("majorId") or "").isdigit()
        and int(item["majorId"]) in allowed_major_ids
    ]
    return {
        "totalPrograms": len(items),
        "readyPrograms": sum(1 for item in items if item.get("canSubmit")),
        "blockedPrograms": sum(1 for item in items if not item.get("canSubmit")),
        "missingMajor": 0,
        "missingGrade": sum(1 for item in items if not item.get("gradeYear")),
        "items": items,
    }


def opening_differences(user, term_id: int, major_id: int | None = None, grade_year: str | None = None,
                        status: str | None = None) -> dict:
    from app.models import Major, SchoolClass

    with session() as db:
        scope = _scope(user, db)
        allowed_major_ids = _allowed_major_ids(db, scope)
        allowed_class_ids = set(scope.class_ids or set())
        if not scope.all and not allowed_class_ids and allowed_major_ids:
            allowed_class_ids = {
                int(value) for (value,) in db.query(SchoolClass.id).filter(
                    SchoolClass.tenant_id == _tid(),
                    SchoolClass.major_id.in_(list(allowed_major_ids)),
                    SchoolClass.is_deleted.is_(False),
                ).all()
            }
        if major_id and not scope.all and int(major_id) not in allowed_major_ids:
            raise no_data_scope("所选专业不在当前数据范围内")

    result = _base.opening_differences(user, term_id, major_id, grade_year, status)
    if scope.all:
        return result
    items = [
        item for item in result.get("items", [])
        if str(item.get("classId") or "").isdigit()
        and int(item["classId"]) in allowed_class_ids
    ]
    from collections import Counter
    counts = Counter(item["status"] for item in items)
    result["items"] = items
    result["summary"] = {
        "total": len(items), "ready": counts["READY"],
        "missingTask": counts["MISSING_TASK"], "duplicateTask": counts["DUPLICATE_TASK"],
        "overOpened": counts["OVER_OPENED"],
        "unresolved": counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"],
        "noTeacher": counts["NO_TEACHER"], "creditMismatch": counts["CREDIT_MISMATCH"],
    }
    return result
