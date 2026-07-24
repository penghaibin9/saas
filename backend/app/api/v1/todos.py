"""
待办与消息（对齐 docs/05-数据接口权限与安全/api/04-待办审批消息API.md）
────────────────────────────────────────────────────────────
契约路径为 /api/v1/{端}/todos、/api/v1/{端}/messages（端 = admin / student-mini / teacher-mobile）。
用工厂函数为每个端生成独立 router，避免 operationId 冲突。

数据源：真实库 t_unified_todo / t_unified_message（见 services/workbench_todo_service）。
可见性由该服务统一收敛为「本人指派 + 本人数据范围内的池待办」，学生端严格本人。
DB 未启用时：非生产可回落静态样例；生产（APP_ENV/ENVIRONMENT=prod）直接报错，禁止假待办。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.response import paginate, success
from app.core.security import get_current_user, require_staff
from app.db.session import db_enabled
from app.services import workbench_todo_service as svc
from app.services.mock_data import MOCK_MESSAGES, MOCK_TODOS


class CompleteBody(BaseModel):
    comment: Optional[str] = None
    requestId: Optional[str] = None


def _use_real_db() -> bool:
    """真库优先；生产环境禁止 MOCK 待办/消息回落（P1/P6 验收：生产无假数据）。"""
    if db_enabled():
        return True
    if settings.is_prod:
        raise AppException(
            "SERVER_ERROR",
            "生产环境未启用数据库，待办与消息不可用",
            details={"reason": "DB_REQUIRED_IN_PROD"},
        )
    return False


def make_router(client: str) -> APIRouter:
    """client: admin / student-mini / teacher-mobile"""
    router = APIRouter(prefix=f"/{client}", tags=[f"04·待办与消息（{client}）"])
    # 管理端/教师端待办仅教职工可访问，学生令牌一律 403（此前用 get_current_user，学生可越权拉 /admin/todos）；
    # student-mini 是学生本人端，保持 get_current_user 不拦。
    guard = get_current_user if client == "student-mini" else require_staff

    # ── 4.x 待办列表 ──
    @router.get("/todos", summary="待办列表", name=f"{client}_todos_list")
    def list_todos(status: Optional[str] = Query(default=None, description="PENDING / DONE"),
                   todoType: Optional[str] = Query(default=None, description="APPROVAL/REVIEW/RISK/SUBMIT/CONFIRM"),
                   page: int = Query(default=1, ge=1),
                   pageSize: int = Query(default=20, ge=1, le=100),
                   user=Depends(guard)):
        if _use_real_db():
            items, total = svc.list_todos(user, status, todoType, page, pageSize)
            return success(paginate(items, total, page, pageSize))
        items = [t for t in MOCK_TODOS
                 if (not status or t["status"] == status)
                 and (not todoType or t["todoType"] == todoType)]
        total = len(items)
        start = (page - 1) * pageSize
        return success(paginate(items[start:start + pageSize], total, page, pageSize))

    # ── 待办角标 ──
    @router.get("/todos/count", summary="待办计数（红点角标）", name=f"{client}_todos_count")
    def todos_count(user=Depends(guard)):
        if _use_real_db():
            return success(svc.count_todos(user))
        pending = [t for t in MOCK_TODOS if t["status"] == "PENDING"]
        by_type: dict[str, int] = {}
        for t in pending:
            by_type[t["todoType"]] = by_type.get(t["todoType"], 0) + 1
        return success({"total": len(pending), "byType": by_type})

    # ── 待办详情 ──
    @router.get("/todos/{todo_id}", summary="待办详情", name=f"{client}_todo_detail")
    def todo_detail(todo_id: str, user=Depends(guard)):
        if _use_real_db():
            d = svc.get_todo(user, todo_id)
            if not d:
                raise not_found("待办不存在")
            return success(d)
        todo = next((t for t in MOCK_TODOS if t["todoId"] == todo_id), None)
        if not todo:
            raise not_found("待办不存在")
        return success({**todo, "actions": ["COMPLETE"] if todo["status"] == "PENDING" else []})

    # ── 确认类待办完成 ──
    @router.post("/todos/{todo_id}/complete", summary="待办完成", name=f"{client}_todo_complete")
    def complete_todo(todo_id: str, body: CompleteBody, user=Depends(guard)):
        if _use_real_db():
            data, err = svc.complete_todo(user, todo_id, body.comment)
            if err == "NOT_FOUND":
                raise not_found("待办不存在")
            if err == "ALREADY_DONE":
                raise AppException("DATA_CONFLICT", "待办已完成，请勿重复操作",
                                   details={"reason": "TODO_ALREADY_COMPLETED"})
            return success(data)
        todo = next((t for t in MOCK_TODOS if t["todoId"] == todo_id), None)
        if not todo:
            raise not_found("待办不存在")
        if todo["status"] == "DONE":
            raise AppException("DATA_CONFLICT", "待办已完成，请勿重复操作",
                               details={"reason": "TODO_ALREADY_COMPLETED"})
        todo["status"] = "DONE"
        return success({"todoId": todo_id, "status": "DONE"})

    # ── 消息列表 ──
    @router.get("/messages", summary="消息列表", name=f"{client}_messages_list")
    def list_messages(
        readStatus: Optional[str] = Query(default=None, description="UNREAD / READ"),
        category: Optional[str] = Query(default=None, description="EMERGENCY/ANNOUNCEMENT/..."),
        priority: Optional[str] = Query(default=None),
        pendingAck: Optional[bool] = Query(default=None),
        page: int = Query(default=1, ge=1),
        pageSize: int = Query(default=20, ge=1, le=100),
        user=Depends(guard),
    ):
        if _use_real_db():
            from app.services import message_center_service as mc
            items, total = mc.list_messages(
                user, category=category, read_status=readStatus,
                priority=priority, pending_ack=pendingAck,
                page=page, page_size=pageSize)
            return success(paginate(items, total, page, pageSize))
        items = [m for m in MOCK_MESSAGES if not readStatus or m["readStatus"] == readStatus]
        total = len(items)
        start = (page - 1) * pageSize
        return success(paginate(items[start:start + pageSize], total, page, pageSize))

    # ── 未读计数 ──
    @router.get("/messages/count", summary="未读消息数", name=f"{client}_messages_count")
    def messages_count(user=Depends(guard)):
        if _use_real_db():
            from app.services import message_center_service as mc
            return success(mc.count_messages(user))
        return success({
            "unread": sum(1 for m in MOCK_MESSAGES if m["readStatus"] == "UNREAD"),
            "pendingAck": 0,
        })

    # ── 分类计数（左侧导航） ──
    @router.get("/messages/categories", summary="消息分类计数", name=f"{client}_messages_categories")
    def messages_categories(user=Depends(guard)):
        if _use_real_db():
            from app.services import message_center_service as mc
            return success(mc.category_counts(user))
        return success({"ALL": len(MOCK_MESSAGES), "UNREAD": 0, "READ": 0})

    # ── 批量已读（不确认） ──
    @router.post("/messages/read-all", summary="批量已读", name=f"{client}_messages_read_all")
    def messages_read_all(
        category: Optional[str] = Query(default=None),
        priority: Optional[str] = Query(default=None),
        user=Depends(guard),
    ):
        if _use_real_db():
            from app.services import message_center_service as mc
            return success(mc.read_all(user, category=category, priority=priority))
        n = 0
        for m in MOCK_MESSAGES:
            if m["readStatus"] == "UNREAD":
                m["readStatus"] = "READ"
                n += 1
        return success({"affectedCount": n, "updatedAt": None})

    # ── 消息详情（不自动已读） ──
    @router.get("/messages/{message_id}", summary="消息详情", name=f"{client}_message_detail")
    def message_detail(message_id: str, user=Depends(guard)):
        if _use_real_db():
            from app.services import message_center_service as mc
            d = mc.get_message(user, message_id)
            if not d:
                raise not_found("消息不存在")
            return success(d)
        msg = next((m for m in MOCK_MESSAGES if m["messageId"] == message_id), None)
        if not msg:
            raise not_found("消息不存在")
        return success(msg)

    # ── 标记已读 ──
    @router.post("/messages/{message_id}/read", summary="消息标记已读", name=f"{client}_message_read")
    def read_message(message_id: str, user=Depends(guard)):
        if _use_real_db():
            from app.services import message_center_service as mc
            d = mc.read_message(user, message_id)
            if not d:
                raise not_found("消息不存在")
            return success(d)
        msg = next((m for m in MOCK_MESSAGES if m["messageId"] == message_id), None)
        if not msg:
            raise not_found("消息不存在")
        msg["readStatus"] = "READ"
        return success({"messageId": message_id, "readStatus": "READ"})

    # ── 确认回执 ──
    @router.post("/messages/{message_id}/receipt", summary="消息确认回执", name=f"{client}_message_receipt")
    def message_receipt(message_id: str, user=Depends(guard)):
        if _use_real_db():
            from app.services import message_center_service as mc
            return success(mc.ack_message(user, message_id))
        msg = next((m for m in MOCK_MESSAGES if m["messageId"] == message_id), None)
        if not msg:
            raise not_found("消息不存在")
        msg["acked"] = True
        return success({"messageId": message_id, "acked": True})

    return router
