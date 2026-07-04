"""/api/v1 路由聚合（分端前缀对齐冻结契约 §一.3；BACKEND-OVERNIGHT 重建并补挂 students/approvals/audit）。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import approval, audit, auth, authz, dashboard, files, rbac, student, system, tenant, transfer
from app.api.v1 import file as file_simple
from app.api.v1 import import_export
from app.api.v1 import message as message_simple
from app.api.v1 import todo as todo_simple
from app.api.v1.todos import make_router as make_todos_router

api_router = APIRouter()

# 全端共用底座
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])       # /api/v1/auth/*
api_router.include_router(authz.router)                                      # /api/v1/authz/*（冻结契约）
api_router.include_router(tenant.router, prefix="/tenant", tags=["tenant"])  # /api/v1/tenant/brand
api_router.include_router(rbac.router, prefix="/rbac", tags=["rbac"])        # /api/v1/rbac/*
api_router.include_router(files.router)                                      # /api/v1/files/*（正式两步契约）
api_router.include_router(file_simple.router, prefix="/files", tags=["files"])  # /api/v1/files/upload-placeholder

# 业务第一批
api_router.include_router(student.router)                                    # /api/v1/students/*
api_router.include_router(approval.router)                                   # /api/v1/approvals/*

# 看板 / 待办 / 消息（扁平简化端点）
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(todo_simple.router, prefix="/todos", tags=["todos"])
api_router.include_router(message_simple.router, prefix="/messages", tags=["messages"])

# 分端：待办与消息（契约 04：/api/v1/{端}/todos、/messages）
api_router.include_router(make_todos_router("admin"))
api_router.include_router(make_todos_router("student-mini"))
api_router.include_router(make_todos_router("teacher-mobile"))

# 导入导出（占位）
api_router.include_router(import_export.import_router, prefix="/import", tags=["import-export"])
api_router.include_router(import_export.export_router, prefix="/export", tags=["import-export"])
api_router.include_router(transfer.router)                                   # /api/v1/admin/students/import|export（正式契约占位）

# 审计
api_router.include_router(audit.router)                                       # /api/v1/admin/audit-logs（PC 管理端）
api_router.include_router(audit.alias_router)                                 # /api/v1/audit/*（任务规定路径）

# 系统
api_router.include_router(system.router, tags=["system"])                     # /api/v1/system/info
