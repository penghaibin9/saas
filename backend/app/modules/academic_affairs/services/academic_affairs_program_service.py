"""培养方案公开 Service。

原有 CRUD、审核与普通生命周期保存在 ``academic_affairs_program_core_service``；
A-W2 将绑定 scope 与版本链这三类必须串行/fail-closed 的高风险入口显式交给
``academic_affairs_program_authority_service``。本文件仍是唯一公开入口，不执行 monkey patch。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_program_authority_service as authority
from . import academic_affairs_program_core_service as _core
from . import academic_affairs_program_governance_service as governance


def __getattr__(name):
    """兼容既有调用方，同时保持一条明确的公开入口。"""
    return getattr(_core, name)


def bind_grade(program_id, user, grade_year, class_id=None) -> dict:
    """A-W2：按 scope 串行绑定；班级 override 不吞专业年级 fallback。"""
    return authority.bind_grade(program_id, user, grade_year, class_id)


def create_new_version(program_id, user, reason=None) -> dict:
    """A-W2：创建唯一直接后继并复制完整方案定义快照。"""
    return authority.create_new_version(program_id, user, reason)


def list_program_versions(program_id, user):
    """A-W2：版本链 fork/cycle/断链一律 fail-closed。"""
    return authority.list_program_versions(program_id, user)


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
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅编制或退回状态方案可提交")

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


def _assert_program_review_scope(db, user, program) -> None:
    """Authorize the locked review node; school-wide authority never impersonates college review."""
    from app.models import Major, SchoolClass

    ctx = build_affairs_context(user, db)
    scope_type = str(getattr(ctx, "scope_type", None) or "NONE").upper()
    if program.status == "ACADEMIC_REVIEW":
        if scope_type != "TENANT_ALL":
            raise no_data_scope("仅校级教务可执行培养方案终审")
        return
    if program.status != "COLLEGE_REVIEW":
        raise AppException("APPROVAL_VERSION_CONFLICT", "该方案当前状态不可审核")
    if scope_type == "TENANT_ALL":
        raise no_data_scope("学院审核必须由方案所属学院审批人执行")
    if not program.major_id:
        raise no_data_scope("培养方案缺少专业归属，无法证明学院审核权限")

    allowed_major_ids = set()
    college_ids = {int(value) for value in getattr(ctx, "college_ids", set()) if value is not None}
    if college_ids:
        allowed_major_ids.update(db.scalars(select(Major.id).where(
            Major.tenant_id == _tid(),
            Major.college_id.in_(sorted(college_ids)),
            Major.is_deleted.is_(False),
        )).all())
    class_ids = ctx.allowed_class_ids(db)
    if class_ids:
        allowed_major_ids.update(value for value in db.scalars(select(SchoolClass.major_id).where(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.id.in_(sorted(class_ids)),
            SchoolClass.is_deleted.is_(False),
        )).all() if value)
    if int(program.major_id) not in {int(value) for value in allowed_major_ids}:
        raise no_data_scope("该培养方案不在您的学院审核范围内")


def review_program(program_id, user, action, reason="") -> dict:
    """P1-03: serialize one review decision and enforce node-specific Authority."""
    from app.models import AaProgram

    action = str(action or "").upper()
    with session() as db:
        program = db.query(AaProgram).filter(
            AaProgram.id == int(program_id),
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        ).with_for_update().first()
        if not program:
            raise not_found("培养方案不存在")
        if program.status not in ("COLLEGE_REVIEW", "ACADEMIC_REVIEW"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该方案当前状态不可审核")

        _assert_program_review_scope(db, user, program)
        before_status = program.status
        if action == "APPROVE":
            program.status = "ACADEMIC_REVIEW" if before_status == "COLLEGE_REVIEW" else "PUBLISHED"
            _core._audit(db, program.id, "APPROVE", f"{before_status}->{program.status}")
        elif action in ("RETURN", "REJECT"):
            clean_reason = str(reason or "").strip()
            if len(clean_reason) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            program.status = "RETURNED"
            _core._audit(db, program.id, "RETURNED", clean_reason)
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")

        db.commit()
        db.refresh(program)
        return _core._row(program)
