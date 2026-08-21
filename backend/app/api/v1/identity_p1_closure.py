"""SYS-03 production identity mutation endpoints for the existing exception workspace."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.exceptions import AppException
from app.core.permissions import require_any_permission
from app.core.response import success

router = APIRouter(prefix="/system", tags=["系统管理·身份生产闭环"])


@router.post("/accounts/{user_id}/repair-binding", summary="修复稳定身份绑定（串行化+原子审计）")
def repair_identity_binding(
    user_id: int,
    body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.user.bind", "systemAdmin.user.manage")),
):
    from app.services import identity_binding_p1_guard_service as guard

    payload = body or {}
    raw_student_id = str(payload.get("studentId") or "").strip()
    if not raw_student_id.isdigit():
        raise AppException("VALIDATION_ERROR", "studentId 必须是学籍主档主键")
    return success(
        guard.repair_binding(
            user_id,
            student_id=int(raw_student_id),
            reason=str(payload.get("reason") or ""),
            expected_version=payload.get("expectedVersion"),
            user=user,
        ),
        message="绑定已修复",
    )


@router.post("/accounts/{user_id}/unbind", summary="解除稳定身份绑定（串行化+原子审计）")
def unbind_identity(
    user_id: int,
    body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.user.bind", "systemAdmin.user.manage")),
):
    from app.services import identity_binding_p1_guard_service as guard

    payload = body or {}
    return success(
        guard.unbind(
            user_id,
            reason=str(payload.get("reason") or ""),
            expected_version=payload.get("expectedVersion"),
            user=user,
        ),
        message="绑定已解除",
    )
