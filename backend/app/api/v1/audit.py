"""
审计日志（占位，对齐冻结契约 §九）
────────────────────────────────────────────────────────────
登录/登出/身份切换/上传/导入导出等埋点已通过 services/audit_log.record() 写入内存队列，
此处提供 PC 管理端查询入口。接库后改查 t_security_audit / t_operation_audit_log。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.permissions import enforce_permission
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.services import audit_log

router = APIRouter(prefix="/admin/audit-logs", tags=["09·审计日志（占位）"])


def _ensure_audit_viewer(user: dict) -> dict:
    """审计日志读写受 systemAdmin.audit.view 管控（P1-8 收口）：
    此前仅排除学生、任意教职工均可读全校安全审计；现要求 systemAdmin.audit.view，
    只有安全审计岗/学校管理员/超管放行（辅导员等无该权限的教职工一律 403+拒绝审计）。
    用 enforce_permission 函数内联（不嵌套 Depends），沿用避免 DB 模式 TestClient 挂起的写法。"""
    return enforce_permission(user, "systemAdmin.audit.view")


@router.get("", summary="审计日志列表（占位：内存队列）")
def list_audit_logs(action: Optional[str] = Query(default=None,
                    description="LOGIN / LOGOUT / CONTEXT_SWITCH / FILE_UPLOAD / IMPORT / EXPORT ..."),
                    page: int = Query(default=1, ge=1),
                    pageSize: int = Query(default=20, ge=1, le=100),
                    user=Depends(get_current_user)):
    _ensure_audit_viewer(user)
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
    _ensure_audit_viewer(user)
    items, total = audit_log.query(page, pageSize, action, operator, dateFrom, dateTo)
    return success(paginate(items, total, page, pageSize))


@alias_router.post("/mock-record", summary="写入一条演示审计记录（联调用）")
def mock_record(user=Depends(get_current_user)):
    _ensure_audit_viewer(user)
    audit_log.record("MOCK", "demo", detail={"path": "/api/v1/audit/mock-record", "method": "POST"})
    return success({"recorded": True}, message="已写入内存审计队列（DB_ENABLED=true 后写 t_security_audit_log）")
