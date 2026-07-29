"""培养方案公开 Service。

原有 CRUD、版本、审核和绑定实现保存在 ``academic_affairs_program_core_service``；
本文件是唯一公开入口，只显式增加提交前治理校验，不执行 monkey patch 或导入副作用。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_program_core_service as _core
from . import academic_affairs_program_governance_service as governance


def __getattr__(name):
    """兼容既有调用方，同时保持一条明确的公开入口。"""
    return getattr(_core, name)


def submit_program(program_id, user) -> dict:
    """提交审核前在同一事务内执行完整结构、实践学分和绑定唯一性校验。"""
    from app.models import AaProgram

    with session() as db:
        governance._ensure_program_scope(db, user, int(program_id))
        program = db.query(AaProgram).filter(
            AaProgram.id == int(program_id),
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        ).with_for_update().first()
        if not program:
            raise not_found("培养方案不存在")
        if program.status not in ("DRAFT", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅编制或退回状态的方案可提交")

        validation = governance.validate_program_db(db, program.id)
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
        _core._audit(
            db,
            program.id,
            "SUBMIT",
            f"validator=V2;creditSum={validation['creditSum']};warnings={validation['counts']['warning']}",
        )
        db.commit()
        db.refresh(program)
        result = _core._row(program)
        result["validation"] = {
            "blockerCount": 0,
            "warningCount": validation["counts"]["warning"],
            "conclusion": validation["conclusion"],
        }
        return result
