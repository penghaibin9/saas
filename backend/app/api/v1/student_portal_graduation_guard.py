"""Student-portal graduation routes that must shadow legacy handlers."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.services import graduation_extension_service as extension_svc
from app.modules.graduation.services.graduation_material_temp_service import abandon_temporary_material
from app.modules.graduation.services.graduation_taskbook_confirmation_service import (
    confirm_with_evidence,
)

router = APIRouter(prefix="/portal/graduation", tags=["学生PC门户-毕业设计高风险修复"])


@router.post("/taskbook/sign", summary="任务书电子确认（版本+内容哈希+原子留痕）")
def graduation_taskbook_sign_evidence(
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    payload = body or {}
    return success(confirm_with_evidence(
        user,
        expected_version=payload.get("taskbookVersion") or payload.get("expectedVersion"),
        confirm=bool(payload.get("confirm")),
    ))


@router.get("/extensions/my", summary="本人优秀成果与延期答辩状态")
def graduation_extensions_my(user=Depends(get_current_user)):
    return success(extension_svc.my_extensions(user))


@router.post("/defense-delay/apply", summary="学生本人申请延期答辩")
def graduation_defense_delay_apply(
    body: dict = Body(...), user=Depends(get_current_user),
):
    return success(extension_svc.apply_delay(
        user, body.get("reason") or "", body.get("evidence") or [],
    ), message="延期答辩申请已提交，等待指导教师审核")


@router.post("/materials/{file_id}/abandon", summary="放弃本人未绑定的毕业设计临时附件")
def graduation_material_abandon(file_id: str, user=Depends(get_current_user)):
    return success(abandon_temporary_material(file_id, user), message="临时附件已清理")
