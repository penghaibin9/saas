"""学生与监护人门户岗位实习模块授权及遗留写入口前置门。"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import Header, Request

from app.core.exceptions import AppException, unauthorized
from app.core.permissions import is_super_admin
from app.core.security import decode_token

_MARKERS = (
    "/portal/internship",
    "/portal/guardian/internship",
)
_BASE = "/portal/internship"


def _legacy_error(label: str) -> None:
    raise AppException(
        "DATA_CONFLICT",
        f"旧版{label}写入口已停用，请刷新页面后通过当前批次版本化入口办理",
    )


def _reject_legacy_write(request: Request) -> None:
    path = request.url.path.rstrip("/")
    method = request.method.upper()
    if method not in ("POST", "PUT"):
        return
    if path == f"{_BASE}/applications" and method == "POST":
        _legacy_error("正式实习申请")
    if path.startswith(f"{_BASE}/leaves") and method == "POST":
        suffix = path[len(f"{_BASE}/leaves"):].strip("/")
        if suffix == "apply" or re.fullmatch(r"[^/]+/(withdraw|return)", suffix or ""):
            _legacy_error("实习请假")
    if path.startswith(f"{_BASE}/makeup") and method == "POST":
        suffix = path[len(f"{_BASE}/makeup"):].strip("/")
        if not suffix or re.fullmatch(r"[^/]+/withdraw", suffix or ""):
            _legacy_error("实习补卡")
    if path.startswith(f"{_BASE}/plan") and method == "POST":
        suffix = path[len(f"{_BASE}/plan"):].strip("/")
        if suffix == "acknowledge" or re.fullmatch(r"tasks/[^/]+/submit", suffix or ""):
            _legacy_error("实习计划")
    if path.startswith(f"{_BASE}/agreements") and method == "POST":
        suffix = path[len(f"{_BASE}/agreements"):].strip("/")
        if re.fullmatch(r"[^/]+/confirm", suffix or ""):
            _legacy_error("三方协议确认")


def enforce_student_portal_module_access(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """仅对学生/监护人岗位实习路由执行模块授权；遗留无版本写入口默认拒绝。"""
    if not any(marker in request.url.path for marker in _MARKERS):
        return None
    token = str(authorization or "").strip()
    if token.startswith("Bearer "):
        token = token[7:]
    if not token:
        raise unauthorized("未提供认证令牌")
    claims = decode_token(token)
    user = {
        "userId": claims.get("userId"),
        "userType": claims.get("userType"),
        "tenantId": claims.get("tenantId"),
        "tenantCode": claims.get("tid"),
        "currentRoleCode": claims.get("currentRoleCode"),
    }
    if not is_super_admin(user):
        from app.db.session import db_enabled
        if db_enabled():
            tenant_id = int(claims.get("tenantId") or 0)
            if not tenant_id:
                raise unauthorized("令牌缺少租户信息，请重新登录")
            from app.services.module_access_service import assert_module_access
            assert_module_access(
                tenant_id, "internship",
                write=request.method.upper() not in ("GET", "HEAD", "OPTIONS"),
            )
    _reject_legacy_write(request)
    return user
