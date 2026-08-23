"""微信公众号官网 JS-SDK 签名。

仅用于 hnyueke.com 微官网在微信内置浏览器里的分享卡片配置：
- 公众号 AppID/AppSecret 与小程序 WX_APPID/WX_SECRET 完全分离；
- AppSecret 只留在服务端，浏览器只拿短时签名；
- 仅给显式允许的 HTTPS 官网域名签名，避免公开签名接口被外站滥用；
- access_token / jsapi_ticket 优先 Redis 缓存，Redis 不可用时退化为进程内短缓存；
- 未启用公众号 JS-SDK 时由 API 返回 enabled=false，不影响普通 PC/手机官网。
"""
from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time
from urllib.parse import urlsplit, urlunsplit

from app.core.redis_client import cache_get_json, cache_set_json

ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
JSAPI_TICKET_URL = "https://api.weixin.qq.com/cgi-bin/ticket/getticket"
_CACHE_LOCK = threading.RLock()
_LOCAL_CACHE: dict[str, tuple[float, dict]] = {}


class OfficialWechatUpstreamError(RuntimeError):
    """微信上游不可用或公众号配置不完整。"""


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def official_wechat_enabled() -> bool:
    return _enabled(_env("WECHAT_OFFICIAL_JS_SDK_ENABLED", "false"))


def _allowed_hosts() -> set[str]:
    raw = _env("WECHAT_OFFICIAL_ALLOWED_HOSTS", "hnyueke.com,www.hnyueke.com")
    return {item.strip().lower().rstrip(".") for item in raw.split(",") if item.strip()}


def normalize_signable_url(raw_url: str) -> str:
    """返回参与 JSSDK 签名的 URL（去 fragment），并限制为正式官网 HTTPS 域名。"""
    raw = (raw_url or "").strip()
    if not raw or len(raw) > 2048:
        raise ValueError("微信签名 URL 无效")
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https" or not host or host not in _allowed_hosts():
        raise ValueError("微信签名仅允许已配置的 HTTPS 官网域名")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("微信签名 URL 端口无效") from exc
    if port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError("微信签名 URL 无效")
    path = parsed.path or "/"
    return urlunsplit(("https", parsed.netloc, path, parsed.query, ""))


def _cache_get(key: str) -> dict | None:
    now = time.time()
    cached = _LOCAL_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]
    shared = cache_get_json(f"official-wechat:{key}")
    if isinstance(shared, dict) and shared.get("value") and float(shared.get("expiresAt") or 0) > now + 5:
        ttl = max(1, int(float(shared["expiresAt"]) - now))
        _LOCAL_CACHE[key] = (now + ttl, shared)
        return shared
    return None


def _cache_put(key: str, value: str, expires_in: int) -> str:
    ttl = max(60, int(expires_in or 7200) - 300)
    expires_at = time.time() + ttl
    payload = {"value": value, "expiresAt": expires_at}
    _LOCAL_CACHE[key] = (expires_at, payload)
    cache_set_json(f"official-wechat:{key}", payload, ttl)
    return value


def _fetch_json(url: str, *, params: dict) -> dict:
    import httpx

    timeout = max(1.0, min(float(_env("WECHAT_OFFICIAL_HTTP_TIMEOUT_SECONDS", "5") or 5), 15.0))
    try:
        response = httpx.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 — 上游网络异常统一转安全错误
        raise OfficialWechatUpstreamError("微信公众号服务暂时不可用") from exc
    if not isinstance(data, dict):
        raise OfficialWechatUpstreamError("微信公众号服务返回异常")
    errcode = data.get("errcode")
    if errcode not in (None, 0, "0"):
        raise OfficialWechatUpstreamError(f"微信公众号服务返回错误 {errcode}")
    return data


def _require_credentials() -> tuple[str, str]:
    app_id = _env("WECHAT_OFFICIAL_APP_ID")
    secret = _env("WECHAT_OFFICIAL_APP_SECRET")
    if not app_id or not secret:
        raise OfficialWechatUpstreamError("微信公众号 JS-SDK 已启用但缺少 AppID/AppSecret")
    return app_id, secret


def get_access_token() -> str:
    cached = _cache_get("access-token")
    if cached:
        return str(cached["value"])
    with _CACHE_LOCK:
        cached = _cache_get("access-token")
        if cached:
            return str(cached["value"])
        app_id, secret = _require_credentials()
        data = _fetch_json(
            ACCESS_TOKEN_URL,
            params={"grant_type": "client_credential", "appid": app_id, "secret": secret},
        )
        token = str(data.get("access_token") or "")
        if not token:
            raise OfficialWechatUpstreamError("微信公众号未返回 access_token")
        return _cache_put("access-token", token, int(data.get("expires_in") or 7200))


def get_jsapi_ticket() -> str:
    cached = _cache_get("jsapi-ticket")
    if cached:
        return str(cached["value"])
    with _CACHE_LOCK:
        cached = _cache_get("jsapi-ticket")
        if cached:
            return str(cached["value"])
        data = _fetch_json(
            JSAPI_TICKET_URL,
            params={"access_token": get_access_token(), "type": "jsapi"},
        )
        ticket = str(data.get("ticket") or "")
        if not ticket:
            raise OfficialWechatUpstreamError("微信公众号未返回 jsapi_ticket")
        return _cache_put("jsapi-ticket", ticket, int(data.get("expires_in") or 7200))


def build_js_sdk_signature(
    raw_url: str,
    *,
    timestamp: int | None = None,
    nonce_str: str | None = None,
) -> dict:
    """按微信 JS-SDK 规则生成 config 所需四元组。"""
    app_id, _ = _require_credentials()
    url = normalize_signable_url(raw_url)
    ticket = get_jsapi_ticket()
    ts = int(timestamp or time.time())
    nonce = nonce_str or secrets.token_urlsafe(12)
    source = f"jsapi_ticket={ticket}&noncestr={nonce}&timestamp={ts}&url={url}"
    signature = hashlib.sha1(source.encode("utf-8")).hexdigest()  # noqa: S324 — 微信协议指定 SHA-1
    return {
        "appId": app_id,
        "timestamp": ts,
        "nonceStr": nonce,
        "signature": signature,
        "url": url,
    }


def _reset_local_cache_for_tests() -> None:
    _LOCAL_CACHE.clear()
