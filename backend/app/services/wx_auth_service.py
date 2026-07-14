"""微信小程序一键登录：jscode2session 换 openid → openid 绑定/登录。

设计：
- openid 全局唯一绑定到一个 t_user（t_user.wx_openid）。返回用户"一键登录"时 openid 直接
  解析到用户+租户，无需登录页预先知道租户。
- 首次未绑定：wx_login 返回 {needBind, wxToken}；wxToken 是短时签名令牌，携带 openid，
  供 wx_bind 使用——避免把 openid 明文在前端往返，也绕开 wx.login 的 code 单次失效限制。
- 未配置 WX_APPID/WX_SECRET 时端点返回清晰"未配置"错误，绝不影响账号密码登录。
- 发 token 复用 auth_service_db.build_login_result，两条登录路径签发的令牌/响应完全一致。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import create_access_token, decode_token, verify_password
from app.db.session import db_enabled, get_sessionmaker
from app.services.auth_service_db import build_login_result

WX_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


def _require_wx_configured():
    if not settings.WX_APPID or not settings.WX_SECRET:
        raise AppException("VALIDATION_ERROR",
                           "微信登录未配置（WX_APPID/WX_SECRET），请先配置或使用账号密码登录")


def code2session(js_code: str) -> str:
    """用 wx.login 的 code 换 openid。返回 openid；失败抛 AppException。
    测试通过 monkeypatch 本函数注入 openid，不触发真实 httpx。"""
    _require_wx_configured()
    if not js_code:
        raise AppException("VALIDATION_ERROR", "缺少微信登录 code")
    import httpx
    params = {"appid": settings.WX_APPID, "secret": settings.WX_SECRET,
              "js_code": js_code, "grant_type": "authorization_code"}
    try:
        data = httpx.get(WX_CODE2SESSION_URL, params=params, timeout=8.0).json()
    except Exception:  # noqa: BLE001 — 上游/网络异常统一转业务错误
        raise AppException("UPSTREAM_ERROR", "微信登录服务暂时不可用，请稍后重试或用账号密码登录")
    if data.get("errcode"):
        raise AppException("UNAUTHORIZED", f"微信登录失败（{data.get('errcode')}），请重试")
    openid = data.get("openid")
    if not openid:
        raise AppException("UNAUTHORIZED", "微信未返回 openid，请重试")
    return openid


def _find_user_by_openid(db, openid: str):
    from app.models import User
    return db.scalars(select(User).where(User.wx_openid == openid,
                                         User.is_deleted.is_(False),
                                         User.status == "ACTIVE")).first()


def wx_login(js_code: str) -> dict:
    """一键登录：code→openid→查绑定。已绑定返回完整登录结果；未绑定返回 {needBind, wxToken}。"""
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "微信登录需启用数据库（DB_ENABLED=true）")
    openid = code2session(js_code)
    db = get_sessionmaker()()
    try:
        user = _find_user_by_openid(db, openid)
        if user:
            return build_login_result(db, user, client_type="MP")
    finally:
        db.close()
    # 未绑定：签发短时 wxToken 携带 openid（purpose=wx_bind），前端拿去做首次绑定
    wx_token = create_access_token({"wxOpenid": openid, "purpose": "wx_bind"})
    return {"needBind": True, "wxToken": wx_token}


def wx_bind(wx_token: str, login_name: str, password: str) -> dict:
    """首次绑定：用 wx_login 返回的 wxToken(携带 openid) + 学号/工号+密码，校验后绑定 openid 并登录。"""
    if not db_enabled():
        raise AppException("UNAUTHORIZED", "微信登录需启用数据库（DB_ENABLED=true）")
    try:
        claims = decode_token(wx_token)
    except Exception:  # noqa: BLE001
        raise AppException("UNAUTHORIZED", "微信绑定令牌无效或已过期，请重新发起微信登录")
    if claims.get("purpose") != "wx_bind" or not claims.get("wxOpenid"):
        raise AppException("UNAUTHORIZED", "微信绑定令牌无效")
    openid = claims["wxOpenid"]
    login_name = (login_name or "").strip()
    if not login_name or not password:
        raise AppException("VALIDATION_ERROR", "请输入学号/工号与密码")
    from app.models import User
    db = get_sessionmaker()()
    try:
        # openid 已被其他账号绑定 → 拒绝（一个 openid 只绑一个账号）
        if _find_user_by_openid(db, openid):
            raise AppException("DATA_CONFLICT", "该微信已绑定其他校园账号，请直接用微信登录或账号密码登录")
        user = db.scalars(select(User).where(User.login_name == login_name,
                                             User.is_deleted.is_(False),
                                             User.status == "ACTIVE")).first()
        if not user or not verify_password(password, user.password_hash):
            raise AppException("UNAUTHORIZED", "账号或密码不正确")
        user.wx_openid = openid
        db.commit()
        db.refresh(user)
        return build_login_result(db, user, client_type="MP")
    finally:
        db.close()
