"""Fail-closed transfer target scope validation for the approval center.

A workflow node configured with ROLE_AND_SCOPE requires two independent proofs before a
pending task can be transferred:

1. the target owns the node's approver role (checked by approval_production_guard), and
2. the target's effective data scope covers the approval business object.

The second proof deliberately reuses the existing structured data-scope evaluator rather
than inventing approval-only scope semantics.  When the approval source cannot be reduced
to a verifiable resource for a scoped node, transfer is denied instead of falling back to
"same role == safe".
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import no_permission


def _node_scope_code(node) -> str:
    from app.services.data_scope_service import normalize_scope

    strategy = str(getattr(node, "assignee_strategy", "") or "").strip().upper()
    if strategy != "ROLE_AND_SCOPE":
        raise no_permission("当前审批节点没有可验证的 ROLE_AND_SCOPE 分派策略，禁止转办")
    raw = str(getattr(node, "data_scope_code", "") or "").strip()
    if not raw:
        raise no_permission("当前审批节点缺少数据范围配置，禁止转办")
    return normalize_scope(raw)


def _resolve_source_student_id(db, *, tenant_id: int, inst) -> int | None:
    """Resolve a stable student id from approval-side persisted evidence only."""
    from app.models import UnifiedTodo, User

    # UnifiedTodo is the preferred cross-domain bridge: domains that create a student
    # approval already persist the stable student_id next to source_module/source_biz_id.
    student_id = db.scalar(select(UnifiedTodo.student_id).where(
        UnifiedTodo.tenant_id == tenant_id,
        UnifiedTodo.source_module == inst.source_module,
        UnifiedTodo.source_biz_id == inst.source_biz_id,
        UnifiedTodo.student_id.is_not(None),
        UnifiedTodo.is_deleted.is_(False),
    ).order_by(UnifiedTodo.id.desc()).limit(1))
    if student_id:
        return int(student_id)

    # Student-originated workflows remain verifiable even if their domain did not create
    # a UnifiedTodo yet.  Never infer a teacher/admin applicant to be the business student.
    applicant = db.scalars(select(User).where(
        User.id == int(inst.applicant_id or 0),
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
        User.status.in_(("ACTIVE", "active")),
    )).first()
    if applicant is None or str(applicant.user_type or "").upper() != "STUDENT":
        return None

    from app.services import student_account_link_service as link_service

    value = link_service.get_student_id_by_user(
        db,
        tenant_id=tenant_id,
        user_id=int(applicant.id),
        allow_legacy_fallback=True,
        login_name=applicant.login_name,
    )
    return int(value) if value else None


def _student_scope_resource(db, *, tenant_id: int, student_id: int) -> dict | None:
    from app.models import Major, SchoolClass, StudentProfile

    student = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(student_id),
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    )).first()
    if student is None:
        return None

    class_id = getattr(student, "class_id", None)
    major_id = getattr(student, "major_id", None)
    college_id = getattr(student, "college_id", None)

    school_class = None
    if class_id:
        school_class = db.scalars(select(SchoolClass).where(
            SchoolClass.id == int(class_id),
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.is_deleted.is_(False),
        )).first()
        if school_class is not None and not major_id:
            major_id = getattr(school_class, "major_id", None)

    if major_id and not college_id:
        major = db.scalars(select(Major).where(
            Major.id == int(major_id),
            Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False),
        )).first()
        if major is not None:
            college_id = getattr(major, "college_id", None)

    return {
        "studentId": str(student.id),
        "classId": str(class_id) if class_id else "",
        "majorId": str(major_id) if major_id else "",
        "collegeId": str(college_id) if college_id else "",
        "ownerUserId": "",
    }


def _target_role_context(db, *, target, role_code: str) -> dict:
    """Build the same claims shape used by production authentication for one target role."""
    from app.services import auth_service_db

    contexts = auth_service_db._role_contexts(db, target)
    context = auth_service_db._pick_context(contexts, role_code=role_code)
    if context is None:
        raise no_permission(f"转办目标没有可用的责任角色上下文 {role_code}")
    claims = auth_service_db._claims(db, target, context, contexts, "PC")
    claims["dataScope"] = context.get("dataScope") or ""
    return claims


def _resource_for_scope(db, *, tenant_id: int, inst, scope_code: str) -> dict | None:
    if scope_code == "TENANT":
        return {"tenantId": str(tenant_id)}
    if scope_code == "SELF":
        return {"ownerUserId": f"db-{int(inst.applicant_id or 0)}"}

    if scope_code in {
        "COLLEGE", "MAJOR", "COUNSELOR_CLASSES", "GD_STUDENTS", "INTERN_STUDENTS",
    }:
        student_id = _resolve_source_student_id(db, tenant_id=tenant_id, inst=inst)
        if not student_id:
            return None
        return _student_scope_resource(db, tenant_id=tenant_id, student_id=student_id)

    # COURSE / DORM_BUILDING / CUSTOM / TEMP_AUTH / funding and psychology scopes need
    # domain-specific persisted evidence that WorkflowInstance does not currently carry.
    # Until that evidence exists, deny transfer rather than widening access.
    return None


def assert_transfer_target_scope(
    db,
    *,
    tenant_id: int,
    task,
    inst,
    node,
    target,
    role_code: str,
) -> str:
    """Raise NO_PERMISSION unless target role + effective scope covers this approval object."""
    del task  # reserved for future task-level scope snapshots; keep the atomic call contract stable.
    from app.services.data_scope_service import normalize_scope, simulate_access

    scope_code = _node_scope_code(node)
    target_ctx = _target_role_context(db, target=target, role_code=role_code)
    target_scope = normalize_scope(target_ctx.get("dataScope") or "SELF")
    if target_scope != scope_code:
        raise no_permission(
            f"转办目标角色的数据范围 {target_scope} 与当前节点要求 {scope_code} 不一致"
        )

    resource = _resource_for_scope(
        db, tenant_id=tenant_id, inst=inst, scope_code=scope_code,
    )
    if resource is None:
        raise no_permission("无法验证当前审批对象的数据范围，已按 fail-closed 禁止转办")

    decision = simulate_access(
        target_ctx,
        resource_type="APPROVAL_TRANSFER",
        resource=resource,
    )
    if not bool(decision.get("allowed")):
        raise no_permission(
            "转办目标不在当前审批对象的数据范围内："
            + str(decision.get("reason") or scope_code)
        )
    return scope_code
