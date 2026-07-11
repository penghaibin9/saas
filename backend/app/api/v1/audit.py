"""
审计日志（占位，对齐冻结契约 §九）
────────────────────────────────────────────────────────────
登录/登出/身份切换/上传/导入导出等埋点已通过 services/audit_log.record() 写入内存队列，
此处提供 PC 管理端查询入口。接库后改查 t_security_audit / t_operation_audit_log。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.exceptions import no_permission
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.services import audit_log

router = APIRouter(prefix="/admin/audit-logs", tags=["09·审计日志（占位）"])


def _ensure_staff(user: dict) -> dict:
    """教职工/管理员专用（等同 require_staff，但不嵌套 Depends，避免 DB 模式下 TestClient 挂起）。"""
    if (user.get("userType") or "").strip().upper() == "STUDENT":
        raise no_permission("该接口仅教职工可用，请使用移动端个人页")
    return user


@router.get("", summary="审计日志列表（占位：内存队列）")
def list_audit_logs(action: Optional[str] = Query(default=None,
                    description="LOGIN / LOGOUT / CONTEXT_SWITCH / FILE_UPLOAD / IMPORT / EXPORT ..."),
                    page: int = Query(default=1, ge=1),
                    pageSize: int = Query(default=20, ge=1, le=100),
                    user=Depends(get_current_user)):
    _ensure_staff(user)
    items, total = audit_log.query(page, pageSize, action)
    return success(paginate(items, total, page, pageSize))


# ── BACKEND-OVERNIGHT 追加：任务规定路径别名 /api/v1/audit/* ──
alias_router = APIRouter(prefix="/audit", tags=["audit"])


@alias_router.get("/logs", summary="审计日志查询（支持 action/operator/dateFrom/dateTo 过滤；DB 模式含 ip/ua/method/path）")
def audit_logs(action: Optional[str] = Query(default=None),
               operator: Optional[str] = Query(default=None, description="操作人姓名模糊匹配"),
               dateFrom: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
               dateTo: Optional[str] = Query(default=None, description="截止日期 YYYY-MM-DD"),
               page: int = Query(default=1, ge=1),
               pageSize: int = Query(default=20, ge=1, le=100),
               user=Depends(get_current_user)):
    _ensure_staff(user)
    items, total = audit_log.query(page, pageSize, action, operator, dateFrom, dateTo)
    return success(paginate(items, total, page, pageSize))


@alias_router.post("/mock-record", summary="写入一条演示审计记录（联调用）")
def mock_record(user=Depends(get_current_user)):
    _ensure_staff(user)
    # 【安全修复】联调用审计写入端点在生产环境禁用，避免任意教职工向审计队列注入记录。
    if settings.is_prod:
        raise no_permission("联调端点已在生产环境禁用")
    audit_log.record("MOCK", "demo", detail={"path": "/api/v1/audit/mock-record", "method": "POST"})
    return success({"recorded": True}, message="已写入内存审计队列（DB_ENABLED=true 后写 t_security_audit_log）")
