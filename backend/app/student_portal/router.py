"""学生 PC 门户 · 路由聚合（/api/v1/portal/*）。

学生端专用：不挂 require_staff 门禁（与 /mobile 一致），由服务层 _require_student 收口——
非学生令牌一律 NO_PERMISSION(403001)。家长侧只读入口在后续增量单独挂载。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.student_portal.services import parent_link_service as parent

router = APIRouter(prefix="/portal", tags=["学生PC门户"])


# ── 家长授权代理（学生本人侧管理）──
@router.get("/parent/guardians", summary="我授权的家长列表（本人·手机号脱敏）")
def list_guardians(user=Depends(get_current_user)):
    return success(parent.list_guardians(user))


@router.post("/parent/guardians", summary="授权一个家长代理只读查看（本人）")
def bind_guardian(user=Depends(get_current_user), body: dict = Body(...)):
    return success(parent.bind_guardian(user, body))


@router.post("/parent/guardians/{link_id}/revoke", summary="撤销某个家长的查看授权（本人）")
def revoke_guardian(link_id: str, user=Depends(get_current_user)):
    return success(parent.revoke_guardian(user, link_id))
