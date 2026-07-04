"""认证：mock 登录 / 当前用户 / 切换身份。路径对齐用户需求 §四。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.schemas.auth import MockLoginRequest, SwitchRoleRequest
from app.services import mock_audit_service as audit
from app.services import mock_auth_service as auth_svc

router = APIRouter()


@router.post("/mock-login", summary="Mock 登录（返回演示令牌 + 多身份）")
def mock_login(body: MockLoginRequest):
    result = auth_svc.login(body.tenantCode, body.loginName, body.userType, body.clientType)
    audit.record("登录", method="POST", path="/api/v1/auth/mock-login",
                 status_code=200, target_type="auth", target_id=result["user"]["userId"])
    return success(result, message="登录成功")


@router.get("/me", summary="当前用户 + 当前身份 + 可用身份列表")
def me(user=Depends(get_current_user)):
    return success(auth_svc.get_me(user))


@router.post("/switch-role", summary="切换当前身份（菜单/待办/数据范围随之变化）")
def switch_role(body: SwitchRoleRequest, user=Depends(get_current_user)):
    result = auth_svc.switch_role(user, body.contextId, body.clientType)
    audit.record("切换身份", method="POST", path="/api/v1/auth/switch-role",
                 status_code=200, target_type="authz", target_id=body.contextId)
    return success(result, message="身份切换成功")


@router.post("/logout", summary="登出（mock：令牌即弃；TODO P1/P2 接真实会话吊销）")
def logout(user=Depends(get_current_user)):
    audit.record("登出", method="POST", path="/api/v1/auth/logout",
                 status_code=200, target_type="auth", target_id=user.get("userId", "-"))
    return success({"loggedOut": True}, message="已登出")
