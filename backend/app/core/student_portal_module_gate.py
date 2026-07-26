"""学生与监护人门户岗位实习模块授权及遗留写入口前置门。"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, Request

from app.core.exceptions import AppException, unauthorized
from app.core.permissions import is_super_admin
from app.core.security import decode_token

_MARKERS = (
    "/portal/internship",
    "/portal/guardian/internship",
)
_LEGACY_APPLICATION_PATH = "/portal/internship/applications"


def _reject_legacy_application_write(request: Request) -> None:
    path = request.url.path.rstrip("/")
    if path == _LEGACY_APPLICATION_PATH and request.method.upper() == "POST":
        raise AppException(
            "DATA_CONFLICT",
            "旧版正式实习申请写入口已停用，请刷新页面后通过版本化入口办理",
        )


def enforce_student_portal_module_access(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """仅对学生/监护人岗位实习路由执行模块授权；遗留无版本写入口默认拒绝。"""
    if not any(marker in request.url.path for marker in _MARKERS):
        return None
    token = (authorization or "").strip()
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
    _reject_legacy_application_write(request)
    return user
