"""认证：mock 登录 / 当前用户 / 切换身份。路径对齐用户需求 §四。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.response import success
from app.core.security import get_current_user
from pydantic import BaseModel, Field

from app.schemas.auth import MockLoginRequest, SwitchRoleRequest
from app.services import auth_service_db
from app.services import mock_audit_service as audit
from app.services import mock_auth_service as mock_auth_svc
from app.core.context import get_request_meta
from app.core.exceptions import AppException, unauthorized
from app.core.security import create_access_token, decode_token
from app.core.token_store import block_jti, consume_refresh, issue_refresh, rate_limit


def _login_rate_guard():
    ip = (get_request_meta() or {}).get("ip") or "unknown"
    if not rate_limit(f"login:{ip}", 10, 60):
        audit.record("RATE_LIMITED", path="/api/v1/auth/*login", target_type="auth", target_id=ip)
        raise AppException("RATE_LIMITED", "登录过于频繁，请 1 分钟后再试")

router = APIRouter()


@router.post("/mock-login", summary="Mock 登录（返回演示令牌 + 多身份；生产环境默认关闭）")
def mock_login(body: MockLoginRequest):
    from app.core.config import settings
    if not settings.mock_login_enabled:
        # 生产环境（或显式 MOCK_LOGIN_ENABLED=false）：端点关闭，绝不签发免密令牌
        audit.record("MOCK_LOGIN_DENIED", path="/api/v1/auth/mock-login",
                     target_type="auth", target_id=body.loginName or "-")
        raise AppException("NO_PERMISSION", "演示登录已关闭，请使用账号密码登录")
    _login_rate_guard()
    result = mock_auth_svc.login(body.tenantCode, body.loginName, body.userType, body.clientType)
    audit.record("登录", method="POST", path="/api/v1/auth/mock-login",
                 status_code=200, target_type="auth", target_id=result["user"]["userId"])
    return success(result, message="登录成功")


class PasswordLoginRequest(BaseModel):
    tenantCode: str | None = Field(None, description="学校编码；同一工号存在于多校时必填")
    loginName: str = Field(..., description="工号/学号/登录名")
    password: str = Field(..., min_length=1, description="密码（仅 hash 入库，接口不回显）")
    clientType: str = Field("PC", description="PC / STUDENT_MINI / TEACHER_MINI / MP")


@router.post("/login", summary="账号密码登录（真实校验：t_user + pbkdf2 哈希；demo 账号仅访问 demo-school 租户）")
def login(body: PasswordLoginRequest):
    _login_rate_guard()
    result = auth_service_db.login_with_password(
        body.loginName.strip(), body.password, body.tenantCode, body.clientType)
    audit.record("登录", method="POST", path="/api/v1/auth/login",
                 status_code=200, target_type="auth", target_id=result["userId"])
    return success(result, message="登录成功")


class WxLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, description="wx.login 返回的临时登录凭证 code")
    bindAnother: bool = Field(False, description="已绑定微信继续绑定另一所学校")


@router.post("/wx-login", summary="微信一键登录（code→openid；已绑定则登录，未绑定返回 needBind+wxToken）")
def wx_login(body: WxLoginRequest):
    _login_rate_guard()
    from app.services import wx_auth_service
    result = wx_auth_service.wx_login(body.code, bind_another=body.bindAnother)
    if result.get("needBind"):
        audit.record("微信登录-待绑定", method="POST", path="/api/v1/auth/wx-login",
                     status_code=200, target_type="auth", target_id="-")
        return success(result, message="请绑定校园账号")
    if result.get("needSelectTenant"):
        audit.record("微信登录-待选择学校", method="POST", path="/api/v1/auth/wx-login",
                     status_code=200, target_type="auth", target_id="-")
        return success(result, message="请选择本次登录学校")
    audit.record("微信登录", method="POST", path="/api/v1/auth/wx-login",
                 status_code=200, target_type="auth", target_id=result.get("userId", "-"))
    return success(result, message="登录成功")


class WxSelectRequest(BaseModel):
    wxToken: str = Field(..., min_length=10)
    tenantCode: str = Field(..., min_length=1)


@router.post("/wx-select", summary="微信绑定多所学校时选择本次登录学校")
def wx_select(body: WxSelectRequest):
    _login_rate_guard()
    from app.services import wx_auth_service
    result = wx_auth_service.wx_select(body.wxToken, body.tenantCode)
    audit.record("微信登录-选择学校", method="POST", path="/api/v1/auth/wx-select",
                 status_code=200, target_type="auth", target_id=result.get("userId", "-"))
    return success(result, message="登录成功")


class WxBindRequest(BaseModel):
    wxToken: str = Field(..., min_length=10, description="wx-login 返回的绑定令牌（携带 openid）")
    tenantCode: str | None = Field(None, description="学校编码；同一工号存在于多校时必填")
    loginName: str = Field(..., min_length=1, description="学号/工号")
    password: str = Field(..., min_length=1, description="校园账号密码")


@router.post("/wx-bind", summary="微信绑定校园账号（首次；绑定后 openid 免密登录）")
def wx_bind(body: WxBindRequest):
    _login_rate_guard()
    from app.services import wx_auth_service
    result = wx_auth_service.wx_bind(
        body.wxToken, body.loginName.strip(), body.password, body.tenantCode)
    audit.record("微信绑定", method="POST", path="/api/v1/auth/wx-bind",
                 status_code=200, target_type="auth", target_id=result.get("userId", "-"))
    return success(result, message="绑定成功")


class ChangePasswordRequest(BaseModel):
    oldPassword: str = Field(..., min_length=1, description="原密码")
    newPassword: str = Field(..., min_length=8, description="新密码（至少8位）")


@router.post("/change-password", summary="本人自助修改密码（需登录，验证原密码；演示账号不支持）")
def change_password(body: ChangePasswordRequest, user=Depends(get_current_user)):
    result = auth_service_db.change_own_password(user, body.oldPassword, body.newPassword)
    audit.record("修改密码", method="POST", path="/api/v1/auth/change-password",
                 status_code=200, target_type="auth", target_id=str(user.get("userId", "-")))
    return success(result, message="密码修改成功，请妥善保管")


@router.get("/me", summary="当前用户 + 当前身份 + 可用身份列表")
def me(user=Depends(get_current_user)):
    if str(user.get("userId") or "").startswith("db-"):
        return success(auth_service_db.get_me(user))
    return success(mock_auth_svc.get_me(user))


@router.post("/switch-role", summary="切换当前身份（菜单/待办/数据范围随之变化）")
def switch_role(body: SwitchRoleRequest, user=Depends(get_current_user)):
    if str(user.get("userId") or "").startswith("db-"):
        result = auth_service_db.switch_role(user, body.contextId, body.clientType)
    else:
        result = mock_auth_svc.switch_role(user, body.contextId, body.clientType)
    audit.record("切换身份", method="POST", path="/api/v1/auth/switch-role",
                 status_code=200, target_type="authz", target_id=body.contextId)
    return success(result, message="身份切换成功")


class RefreshRequest(BaseModel):
    refreshToken: str = Field(..., min_length=10, description="登录返回的 refreshToken（一次性，轮换发新）")


@router.post("/refresh", summary="刷新令牌（refreshToken 一次性轮换，旧 access 不受影响直至过期/登出）")
def refresh(body: RefreshRequest):
    claims = consume_refresh(body.refreshToken)
    if not claims:
        raise unauthorized("refreshToken 无效或已使用，请重新登录")
    # 真实账号刷新前重新校验账号、租户、当前岗位与权限版本，防止已回收角色被旧 refresh 恢复。
    auth_service_db.validate_token_subject(claims)
    token = create_access_token(dict(claims))
    new_refresh = issue_refresh(claims)
    audit.record("TOKEN_REFRESH", target_type="auth", target_id=str(claims.get("userId", "-")))
    return success({"accessToken": token, "refreshToken": new_refresh,
                    "tokenType": "Bearer", "expiresIn": settings.JWT_EXPIRES_IN}, message="已刷新")


from typing import Optional as _Optional  # noqa: E402

from fastapi import Header  # noqa: E402


@router.post("/logout", summary="登出（access 令牌 jti 进入黑名单即刻失效；吊销该用户全部 refreshToken）")
def logout(user=Depends(get_current_user), authorization: _Optional[str] = Header(default=None)):
    from app.core.exceptions import AppException
    from app.core.token_store import revoke_refresh_by_user
    jti_ok = True
    refresh_ok = False
    errors = []
    try:
        raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "")
        claims = decode_token(raw) if raw else {}
        jti = claims.get("jti")
        if jti:
            jti_ok = bool(block_jti(jti, float(claims.get("exp") or 0) or None))
    except AppException as e:
        jti_ok = False
        errors.append(e.message)
    except Exception:  # noqa: BLE001
        jti_ok = False
        errors.append("access令牌拉黑失败")
    try:
        revoke_refresh_by_user(str(user.get("userId", "")))
        refresh_ok = True
    except AppException as e:
        errors.append(e.message)
    audit.record("登出", method="POST", path="/api/v1/auth/logout",
                 status_code=200, target_type="auth", target_id=user.get("userId", "-"))
    invalidated = bool(jti_ok and refresh_ok)
    if not invalidated:
        return success({
            "loggedOut": True, "tokenInvalidated": False, "partial": True,
            "errors": errors,
        }, message="登出未完全生效，请稍后重试或清除本地令牌")
    return success({"loggedOut": True, "tokenInvalidated": True}, message="已登出，令牌已失效")
