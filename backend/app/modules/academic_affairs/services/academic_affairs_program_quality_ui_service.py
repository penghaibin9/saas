"""V2-01 培养方案质量最终展示层。

- 差异类型筛选只改变明细，不重算首屏全局摘要；
- ``NO_CLASS`` 没有 classId，按方案专业数据范围保留；
- 给所有差异项补充 majorId，便于前端解释和范围审计。
"""
from __future__ import annotations

from collections import Counter

from app.core.affairs_security import no_data_scope
from app.services.db_service import _tid, session

from . import academic_affairs_program_quality_security_service as _security

_final = _security._base


def __getattr__(name):
    return getattr(_security, name)


def _summary(items) -> dict:
    counts = Counter(item["status"] for item in items)
    return {
        "total": len(items),
        "ready": counts["READY"],
        "missingTask": counts["MISSING_TASK"],
        "duplicateTask": counts["DUPLICATE_TASK"],
        "overOpened": counts["OVER_OPENED"],
        "unresolved": counts["COURSE_UNRESOLVED"] + counts["TERM_UNRESOLVED"] + counts["NO_CLASS"],
        "noTeacher": counts["NO_TEACHER"],
        "creditMismatch": counts["CREDIT_MISMATCH"],
    }


def opening_differences(user, term_id: int, major_id: int | None = None, grade_year: str | None = None,
                        status: str | None = None) -> dict:
    from app.models import AaProgram, SchoolClass
    from .academic_affairs_task_security_facade import _scope

    with session() as db:
        scope = _scope(user, db)
        allowed_major_ids = _security._allowed_major_ids(db, scope)
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

    result = _final.opening_differences(user, term_id, major_id, grade_year, None)
    items = list(result.get("items") or [])
    program_ids = {
        int(item["programId"]) for item in items
        if str(item.get("programId") or "").isdigit()
    }
    class_ids = {
        int(item["classId"]) for item in items
        if str(item.get("classId") or "").isdigit()
    }
    with session() as db:
        program_major = {
            int(row.id): int(row.major_id) if row.major_id else None
            for row in db.query(AaProgram).filter(
                AaProgram.tenant_id == _tid(),
                AaProgram.id.in_(list(program_ids) or [-1]),
                AaProgram.is_deleted.is_(False),
            ).all()
        }
        class_major = {
            int(row.id): int(row.major_id) if row.major_id else None
            for row in db.query(SchoolClass).filter(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(list(class_ids) or [-1]),
                SchoolClass.is_deleted.is_(False),
            ).all()
        }

    for item in items:
        program_value = int(item["programId"]) if str(item.get("programId") or "").isdigit() else None
        class_value = int(item["classId"]) if str(item.get("classId") or "").isdigit() else None
        item["majorId"] = str(
            program_major.get(program_value)
            or class_major.get(class_value)
            or ""
        )

    if not scope.all:
        items = [
            item for item in items
            if (
                str(item.get("classId") or "").isdigit()
                and int(item["classId"]) in allowed_class_ids
            ) or (
                item.get("status") == "NO_CLASS"
                and str(item.get("majorId") or "").isdigit()
                and int(item["majorId"]) in allowed_major_ids
            )
        ]

    full_summary = _summary(items)
    display_items = [item for item in items if item["status"] == status] if status else items
    result["items"] = display_items
    result["summary"] = full_summary
    result["filteredTotal"] = len(display_items)
    result["activeFilter"] = status or ""
    return result
