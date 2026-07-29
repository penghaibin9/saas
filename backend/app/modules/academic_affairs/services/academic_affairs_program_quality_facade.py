"""培养方案最终质量门禁 facade。

除 submit_program 外全部复用既有培养方案服务；提交审核在同一事务内执行 R7 结构化校验，
存在 BLOCKER 时禁止进入学院审核；提交前必须再次验证当前学院/班级数据范围，不能因 facade 绕过旧服务安全层。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_program_service as _legacy
from .academic_affairs_program_binding_quality_service import validate_program_db
from .academic_affairs_program_quality_security_service import _ensure_program_scope


def __getattr__(name):
    return getattr(_legacy, name)


def submit_program(program_id, user) -> dict:
    from app.models import AaProgram

    with session() as db:
        # facade 自己持有事务和状态迁移，因此必须在同一事务内重做数据范围校验。
        _ensure_program_scope(db, user, int(program_id))
        program = db.query(AaProgram).filter(
            AaProgram.id == int(program_id),
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        ).with_for_update().first()
        if not program:
            raise not_found("培养方案不存在")
        if program.status not in ("DRAFT", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅编制/退回态方案可提交")

        validation = validate_program_db(db, program.id)
        blockers = [item for item in validation["issues"] if item["level"] == "BLOCKER"]
        if blockers:
            preview = "；".join(item["message"] for item in blockers[:5])
            suffix = f"；另有 {len(blockers) - 5} 项" if len(blockers) > 5 else ""
            raise AppException(
                "PROGRAM_VALIDATION_BLOCKED",
                f"方案存在 {len(blockers)} 个阻断项：{preview}{suffix}",
                details={
                    "programId": str(program.id),
                    "blockerCount": len(blockers),
                    "issues": blockers[:20],
                },
                http_status=409,
            )

        claimed = db.query(AaProgram).filter(
            AaProgram.id == program.id,
            AaProgram.tenant_id == _tid(),
            AaProgram.status.in_(["DRAFT", "RETURNED"]),
        ).update({AaProgram.status: "COLLEGE_REVIEW"}, synchronize_session=False)
        if not claimed:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "方案已提交或状态已变更")
        program.status = "COLLEGE_REVIEW"
        _legacy._audit(
            db,
            program.id,
            "SUBMIT",
            f"validator=R7;creditSum={validation['creditSum']};warnings={validation['counts']['warning']}",
        )
        db.commit()
        db.refresh(program)
        result = _legacy._row(program)
        result["validation"] = {
            "blockerCount": 0,
            "warningCount": validation["counts"]["warning"],
            "conclusion": validation["conclusion"],
        }
        return result


# 防止后续完整路径直接导入旧模块绕过质量门禁。
_legacy.submit_program = submit_program
