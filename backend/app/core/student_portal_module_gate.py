"""Conditional module entitlement gate for student PC portal routes."""
from __future__ import annotations

from typing import Optional

from fastapi import Header, Request

from app.core.exceptions import unauthorized
from app.core.permissions import is_super_admin
from app.core.security import decode_token

_MARKER = "/portal/internship"


def enforce_student_portal_module_access(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Require the internship entitlement only for `/portal/internship/*`.

    The main portal router contains many domains, so applying `require_module`
    to the whole router would incorrectly block academic/affairs/graduation.
    """
    if _MARKER not in request.url.path:
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
    if is_super_admin(user):
        return user
    from app.db.session import db_enabled
    if not db_enabled():
        return user
    tenant_id = int(claims.get("tenantId") or 0)
    if not tenant_id:
        raise unauthorized("令牌缺少租户信息，请重新登录")
    from app.services.module_access_service import assert_module_access
    assert_module_access(
        tenant_id, "internship", write=request.method.upper() not in ("GET", "HEAD", "OPTIONS"))
    return user
