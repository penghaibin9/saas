"""毕业设计移动端高风险精确路由与四端 DTO 安装。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.exceptions import no_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.services import graduation_extension_safety_service as extension_safety_svc
from app.modules.graduation.services import graduation_extension_service as extension_svc
from app.modules.graduation.services.graduation_contract_bridge import install_contract_bridge
from app.modules.graduation.services.graduation_material_temp_service import abandon_temporary_material
from app.modules.graduation.services.graduation_taskbook_confirmation_service import confirm_with_evidence

install_contract_bridge()
router = APIRouter(prefix="/mobile/graduation", tags=["移动端聚合-毕业设计高风险修复"])


def _student(user: dict) -> dict:
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise no_permission("该接口仅学生本人可用")
    return user


@router.post("/taskbook/confirm", summary="任务书·本人确认（内容哈希+版本证据）")
def graduation_taskbook_confirm_evidence(
    body: dict = Body(default={}), user=Depends(get_current_user),
):
    payload = dict(body or {})
    return success(confirm_with_evidence(
        _student(user),
        expected_version=payload.get("taskbookVersion") or payload.get("expectedVersion"),
        confirm=True,
    ), message="已确认")


@router.get("/extensions/my", summary="本人优秀成果与延期答辩状态")
def graduation_extensions_my(user=Depends(get_current_user)):
    return success(extension_safety_svc.my_extensions(_student(user)))


@router.post("/defense-delay/apply", summary="学生本人申请延期答辩")
def graduation_defense_delay_apply(
    body: dict = Body(...), user=Depends(get_current_user),
):
    return success(extension_svc.apply_delay(
        _student(user), body.get("reason") or "", body.get("evidence") or [],
    ), message="延期答辩申请已提交，等待指导教师审核")


@router.post("/materials/{file_id}/abandon", summary="放弃本人未绑定的毕业设计临时附件")
def graduation_material_abandon(file_id: str, user=Depends(get_current_user)):
    return success(abandon_temporary_material(file_id, _student(user)), message="临时附件已清理")
