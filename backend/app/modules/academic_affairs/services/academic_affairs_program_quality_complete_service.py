"""V2-01 培养方案质量完整公开层。

页面校验/治理摘要使用“结构校验 + 实践学分 + 全局绑定唯一性”；开课差异复用最终范围和展示层。
"""
from __future__ import annotations

from app.services.db_service import _tid, session

from . import academic_affairs_program_quality_ui_service as _ui
from .academic_affairs_program_binding_quality_service import validate_program_db
from .academic_affairs_program_quality_security_service import _allowed_major_ids, _ensure_program_scope
from .academic_affairs_task_security_facade import _scope


def __getattr__(name):
    return getattr(_ui, name)


def validate_program(user, program_id: int) -> dict:
    with session() as db:
        _ensure_program_scope(db, user, program_id)
        return validate_program_db(db, program_id)


def program_governance_summary(user) -> dict:
    from app.models import AaProgram

    with session() as db:
        scope = _scope(user, db)
        allowed_major_ids = _allowed_major_ids(db, scope)
        query = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        )
        programs = query.order_by(AaProgram.id.desc()).all()
        if not scope.all:
            programs = [
                row for row in programs
                if row.major_id and int(row.major_id) in allowed_major_ids
            ]

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


opening_differences = _ui.opening_differences
