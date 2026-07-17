"""学生 PC 门户 · 路由聚合（/api/v1/portal/*）。

学生端专用：不挂 require_staff 门禁（与 /mobile 一致），由服务层 _require_student 收口——
非学生令牌一律 NO_PERMISSION(403001)。家长侧只读入口在后续增量单独挂载。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.student_portal.services import common_service as common
from app.student_portal.services import guardian_service as guardian
from app.student_portal.services import parent_link_service as parent
from app.student_portal.services import profile_service as profile

router = APIRouter(prefix="/portal", tags=["学生PC门户"])


# ── PC 重活公共底座：电子签署（可插拔）+ 打印/导出留痕 ──
@router.post("/common/sign", summary="电子签署（默认可靠留痕；法律级待采购接入）")
def common_sign(user=Depends(get_current_user), body: dict = Body(...)):
    return success(common.sign(user, body))


@router.post("/common/print-log", summary="打印留痕（本人·审计+水印）")
def common_print_log(user=Depends(get_current_user), body: dict = Body(...)):
    return success(common.print_log(user, body))


@router.post("/common/export-log", summary="导出留痕（本人·审计+水印）")
def common_export_log(user=Depends(get_current_user), body: dict = Body(...)):
    return success(common.export_log(user, body))


# ── 我的档案（学籍信息只读 + 敏感明文授权查看）──
@router.get("/profile/enrollment", summary="我的学籍信息（本人·只读·默认脱敏）")
def profile_enrollment(user=Depends(get_current_user)):
    return success(profile.enrollment(user))


@router.post("/profile/sensitive", summary="授权查看敏感字段明文（本人·填原因·留痕）")
def profile_sensitive(user=Depends(get_current_user), body: dict = Body(...)):
    return success(profile.sensitive_view(user, body))


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


# ── 家长（proxy）侧：验证码登录 + 只读查看（otp/login 免登录）──
@router.post("/guardian/otp", summary="家长登录·请求验证码（公开）")
def guardian_otp(body: dict = Body(...)):
    return success(guardian.request_otp(body))


@router.post("/guardian/login", summary="家长登录·手机号+验证码（公开，签发GUARDIAN令牌）")
def guardian_login(body: dict = Body(...)):
    return success(guardian.login(body))


@router.get("/guardian/students", summary="家长查看被授权学生（只读·授权范围）")
def guardian_students(user=Depends(get_current_user)):
    return success(guardian.list_students(user))
