"""教师端·迎新绿色通道审核（移动端加壳，零建表）。

学生在小程序提交绿色通道申请后，此前仅 PC 端可审核；本 router 把审核搬到教师小程序，
复用 PC 侧 orientation_service 的审核落库逻辑，只做「教师校验 + 审计 + 参数校验」包装：
- GET  /mobile/teacher/orientation/green-channels            待审队列（默认 SUBMITTED/REVIEWING）
- POST /mobile/teacher/orientation/green-channels/{gid}/review  审核（APPROVE/REJECT/RETURN）

不新建表、不写迁移；独立文件避让并行编辑中的 mobile.py。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.exceptions import AppException
from app.core.response import success
from app.core.security import get_current_user
from app.services import mobile_teacher_service as tea
from app.services import orientation_service as ori

router = APIRouter(prefix="/mobile", tags=["移动端聚合"])


@router.get("/teacher/orientation/green-channels", summary="教师·迎新绿色通道审核队列（本校）")
def teacher_gc_list(status: str | None = None, user=Depends(get_current_user)):
    tea._require_teacher(user)
    items, total = ori.list_green_channels(1, 50, status=status)
    if not status:
        items = [x for x in items if x.get("status") in ("SUBMITTED", "REVIEWING")]
        total = len(items)
    return success({"hasData": total > 0, "list": items, "total": total})


@router.post("/teacher/orientation/green-channels/{gid}/review",
             summary="教师·迎新绿色通道审核（APPROVE/REJECT/RETURN）")
def teacher_gc_review(gid: str, body: dict = Body(...), user=Depends(get_current_user)):
    tea._require_teacher(user)
    action = str(body.get("action") or "").upper()
    comment = str(body.get("comment") or body.get("reason") or "").strip()
    if action in ("REJECT", "RETURN") and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回/退回原因不少于 5 个字")
    if action == "APPROVE":
        result = ori.approve_green_channel(gid, comment)
    elif action == "REJECT":
        result = ori.reject_green_channel(gid, comment)
    elif action == "RETURN":
        result = ori.return_green_channel(gid, comment)
    else:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT/RETURN")
    tea._audit_write("MOBILE_GC_REVIEW", "orientation/green-channel:" + str(gid),
                     {"operator": user.get("realName"), "action": action, "comment": comment[:200]})
    return success(result if isinstance(result, dict) else {"ok": True}, message="审核完成")
