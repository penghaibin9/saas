"""通用用户偏好 API（/api/v1/me/preferences）+ 轻量埋点（/me/telemetry）。

只读写「当前登录人自己」的偏好：user_key 一律取自令牌，不接受 body/query 传入用户标识，
杜绝改别人偏好；租户由上下文注入，天然行级隔离。

首个用途是新手引导「是否已看过」。任何登录身份（含学生）都可读写自己的偏好，
因此不挂 require_staff。

埋点与偏好分离：点击计数不得只落 preferences 冒充分析平台；telemetry 走审计队列。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Query

from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log
from app.services import user_preference_service as svc
from fastapi import Depends

router = APIRouter(prefix="/me", tags=["用户偏好"])


@router.get("/preferences", summary="我的偏好（本人；keys 可选，逗号分隔）")
def my_preferences(keys: str = Query("", description="逗号分隔的偏好键；留空返回全部"),
                   user=Depends(get_current_user)):
    wanted = [k.strip() for k in (keys or "").split(",") if k.strip()] or None
    return success(svc.get_preferences(user, wanted))


@router.post("/preferences", summary="设置我的偏好（本人）")
def set_my_preference(body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.set_preference(user, body.get("key"), body.get("value")), message="已保存")


@router.post("/telemetry", summary="本人埋点（工作台点击等；走审计通道，非偏好）")
def my_telemetry(body: dict = Body(...), user=Depends(get_current_user)):
    event = str((body or {}).get("event") or "WORKBENCH_CLICK").strip().upper()[:64] or "WORKBENCH_CLICK"
    detail = (body or {}).get("detail")
    if not isinstance(detail, dict):
        detail = {"raw": detail}
    role = (user or {}).get("currentRoleCode") or ""
    detail = {**detail, "role": role, "actorLogin": (user or {}).get("loginName") or ""}
    entry = audit_log.record(event, "workbench", detail=detail)
    return success({"recorded": bool(entry), "event": event}, message="已记录")
