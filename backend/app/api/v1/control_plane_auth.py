"""Replacement endpoints for control-plane auth P0 A/B.

URLs and request DTOs stay byte-compatible with ``app.api.v1.auth``.  The
aggregating router removes the five legacy APIRoutes before mounting these, so
there is one public handler per method/path and no route-order shadowing.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.auth import (
    CaptchaRequest,
    ChangePasswordRequest,
    PasswordLoginRequest,
    RefreshRequest,
    WxBindRequest,
)
from app.core.response import success
from app.core.security import get_current_user
from app.services import auth_challenge_service as captcha_svc
from app.services import control_plane_auth_service as p0
from app.services import mock_audit_service as audit

router = APIRouter(prefix="/auth")


@router.post("/captcha", summary="获取登录图形验证码（跨 Worker 持久一次性状态）")
def captcha(body: CaptchaRequest):
    return success(captcha_svc.issue_captcha(
        body.scene, body.tenantCode, body.loginName,
        body.clientNonce, body.clientType,
    ))


@router.post("/login", summary="账号密码登录（分布式风控 + 显式租户安全策略）")
def login(body: PasswordLoginRequest):
    p0.login_rate_guard()
    scene = captcha_svc.PLATFORM_LOGIN if body.clientType.strip().upper() == "PLATFORM_PC" else captcha_svc.PASSWORD_LOGIN
    captcha_svc.enforce_login_captcha(
        scene, body.tenantCode, body.loginName,
        body.captchaId, body.captchaCode, body.clientNonce, body.clientType,
    )
    result = p0.login_with_password(
        body.loginName.strip(), body.password, body.tenantCode, body.clientType,
    )
    audit.record("登录", method="POST", path="/api/v1/auth/login",
                 status_code=200, target_type="auth", target_id=result["userId"])
    return success(result, message="登录成功")


@router.post("/refresh", summary="刷新令牌（按当前有效安全策略重新签发）")
def refresh(body: RefreshRequest):
    result = p0.refresh(body.refreshToken)
    audit.record("TOKEN_REFRESH", target_type="auth", target_id="policy-bound")
    return success(result, message="已刷新")


@router.post("/change-password", summary="本人自助修改密码（显式租户密码策略 + 分布式失败锁）")
def change_password(body: ChangePasswordRequest, user=Depends(get_current_user)):
    result = p0.change_own_password(user, body.oldPassword, body.newPassword)
    audit.record("修改密码", method="POST", path="/api/v1/auth/change-password",
                 status_code=200, target_type="auth", target_id=str(user.get("userId", "-")))
    return success(result, message="密码修改成功，请妥善保管")


@router.post("/wx-bind", summary="微信绑定校园账号（同一分布式风控/租户策略）")
def wx_bind(body: WxBindRequest):
    p0.login_rate_guard()
    captcha_svc.enforce_login_captcha(
        captcha_svc.WX_BIND, body.tenantCode, body.loginName,
        body.captchaId, body.captchaCode, body.clientNonce, body.clientType,
    )
    result = p0.wx_bind(body.wxToken, body.loginName.strip(), body.password, body.tenantCode)
    audit.record("微信绑定", method="POST", path="/api/v1/auth/wx-bind",
                 status_code=200, target_type="auth", target_id=result.get("userId", "-"))
    return success(result, message="绑定成功")
