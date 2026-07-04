"""
简化消息列表（P0 基线，GET /api/v1/messages）
────────────────────────────────────────────────────────────
与分端消息 app/api/v1/todos.py 内 /{端}/messages（对齐正式冻结契约）并存：
本文件提供扁平化最小接口，复用此前已写好但未挂载的 services/mock_message_service.py，
便于 P0 基线联调与测试，不新增业务逻辑。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.core.security import get_current_user
from app.services import mock_message_service as message_svc

router = APIRouter(tags=["S8·简化-消息"])


@router.get("", summary="消息列表（简化，占位）")
def list_messages(
    readStatus: Optional[str] = Query(default=None, description="UNREAD / READ"),
    messageType: Optional[str] = Query(default=None, description="TODO_NOTICE/ANNOUNCEMENT/SYSTEM"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    user=Depends(get_current_user),
):
    return success(message_svc.list_messages(readStatus, messageType, page, pageSize))


@router.post("/{message_id}/read", summary="标记消息已读（占位）")
def message_read(message_id: str, user=Depends(get_current_user)):
    return success(message_svc.mark_read(message_id), message="已读")
