"""Adaptive graphical captcha for password-bearing authentication flows.

The answer is never returned in production, never logged and is consumed atomically.
Production/staging require Redis so multiple workers cannot disagree about a challenge.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import secrets
import struct
import threading
import time
import zlib
from typing import Any

from app.core.config import settings
from app.core.context import get_request_meta
from app.core.exceptions import AppException
from app.core.redis_client import _prefix, get_redis
from app.core.token_store import get_login_failure_count, rate_limit

PASSWORD_LOGIN = "PASSWORD_LOGIN"
PLATFORM_LOGIN = "PLATFORM_LOGIN"
WX_BIND = "WX_BIND"
PASSWORD_RESET = "PASSWORD_RESET"
_ALLOWED_SCENES = {PASSWORD_LOGIN, PLATFORM_LOGIN, WX_BIND, PASSWORD_RESET}
_ALLOWED_CLIENT_TYPES = {
    PASSWORD_LOGIN: {"PC", "STUDENT_MINI", "TEACHER_MINI", "MP"},
    PLATFORM_LOGIN: {"PLATFORM_PC"},
    WX_BIND: {"STUDENT_MINI", "TEACHER_MINI", "MP"},
    PASSWORD_RESET: {"PC", "TEACHER_PC", "STUDENT_MINI", "TEACHER_MINI", "MP"},
}
_DIGIT_SEGMENTS = {
    "0": "abcedf", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgecd", "7": "abc", "8": "abcdefg", "9": "abfgcd",
}
_MEMORY: dict[str, tuple[float, str]] = {}
_MEMORY_LOCK = threading.Lock()


def _is_strict_env() -> bool:
    app_env = str(settings.APP_ENV or "").strip().lower()
    deployment_mode = str(settings.DEPLOYMENT_MODE or "").strip().lower()
    return app_env in {"production", "staging"} or deployment_mode in {"production", "staging"}


def _auth_store_unavailable(exc: Exception | None = None) -> AppException:
    error = AppException("AUTH_STORE_UNAVAILABLE", "验证码服务暂时不可用，请稍后重试", http_status=503)
    if exc is not None:
        error.__cause__ = exc
    return error


def _secret() -> bytes:
    return (settings.JWT_SECRET_KEY or settings.JWT_SECRET).encode("utf-8")


def _digest(value: str) -> str:
    return hmac.new(_secret(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def login_guard_key(tenant_code: str | None, login_name: str | None) -> str:
    normalized = f"{(tenant_code or '*').strip().lower()}\n{(login_name or '').strip().lower()}"
    return "pw:" + _digest("login-subject\n" + normalized)[:40]


def _subject_hash(tenant_code: str | None, login_name: str | None) -> str:
    if not (login_name or "").strip():
        return ""
    return _digest(f"subject\n{(tenant_code or '*').strip().lower()}\n{login_name.strip().lower()}")


def _nonce_hash(value: str | None) -> str:
    return _digest("nonce\n" + (value or "")) if value else ""


def _ip_hash() -> str:
    ip = str((get_request_meta() or {}).get("ip") or "unknown")
    return _digest("ip\n" + ip)[:24]


def _validate_issue_binding(
    scene: str,
    login_name: str | None,
    client_nonce: str | None,
    client_type: str | None,
) -> tuple[str, str, str]:
    normalized_login = str(login_name or "").strip()
    normalized_nonce = str(client_nonce or "").strip()
    normalized_client = str(client_type or "").strip().upper()
    if not normalized_login:
        raise AppException("VALIDATION_ERROR", "获取验证码前请先填写登录账号")
    if not normalized_nonce:
        raise AppException("VALIDATION_ERROR", "验证码客户端标识不能为空")
    if normalized_client not in _ALLOWED_CLIENT_TYPES[scene]:
        raise AppException("VALIDATION_ERROR", "验证码场景与客户端类型不匹配")
    return normalized_login, normalized_nonce, normalized_client


def _store_key(captcha_id: str) -> str:
    return f"auth:captcha:{captcha_id}"


def _store(captcha_id: str, payload: dict[str, Any], ttl: int) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    client = get_redis()
    if client is not None:
        try:
            client.set(_prefix(_store_key(captcha_id)), raw, ex=max(1, ttl))
            return
        except Exception as exc:  # noqa: BLE001
            if _is_strict_env():
                raise _auth_store_unavailable(exc)
    if _is_strict_env():
        raise _auth_store_unavailable()
    with _MEMORY_LOCK:
        _MEMORY[captcha_id] = (time.time() + ttl, raw)


def _consume(captcha_id: str) -> dict[str, Any] | None:
    client = get_redis()
    if client is not None:
        key = _prefix(_store_key(captcha_id))
        try:
            try:
                raw = client.execute_command("GETDEL", key)
            except Exception:
                raw = client.eval(
                    "local v=redis.call('GET',KEYS[1]); if v then redis.call('DEL',KEYS[1]) end; return v",
                    1,
                    key,
                )
            return json.loads(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            if _is_strict_env():
                raise _auth_store_unavailable(exc)
    if _is_strict_env():
        raise _auth_store_unavailable()
    with _MEMORY_LOCK:
        item = _MEMORY.pop(captcha_id, None)
    if not item or item[0] < time.time():
        return None
    return json.loads(item[1])


def _strict_login_failure_count(key: str) -> int:
    """生产/预发直接读 Redis；运行时断连时禁止退回单进程内存。"""
    client = get_redis()
    if client is None:
        raise _auth_store_unavailable()
    try:
        raw = client.get(_prefix(f"auth:login-fail:{key}"))
    except Exception as exc:  # noqa: BLE001
        raise _auth_store_unavailable(exc)
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        # 损坏的风控计数不能被解释成“没有失败记录”。
        raise _auth_store_unavailable()


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _line(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
    dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < width and 0 <= y0 < height:
            pos = (y0 * width + x0) * 3
            pixels[pos:pos + 3] = bytes(color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    for yy in range(max(0, y), min(height, y + h)):
        for xx in range(max(0, x), min(width, x + w)):
            pos = (yy * width + xx) * 3
            pixels[pos:pos + 3] = bytes(color)


def _render_png(code: str) -> bytes:
    width, height = 154, 52
    rnd = random.SystemRandom()
    pixels = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            pos = (y * width + x) * 3
            base = rnd.randint(244, 255)
            pixels[pos:pos + 3] = bytes((base, min(255, base + 1), min(255, base + 3)))
    for _ in range(3):
        _line(
            pixels,
            width,
            height,
            rnd.randrange(width),
            rnd.randrange(height),
            rnd.randrange(width),
            rnd.randrange(height),
            (rnd.randrange(120, 205), rnd.randrange(130, 210), rnd.randrange(150, 220)),
        )
    segments = {
        "a": (4, 1, 13, 3), "b": (16, 4, 3, 13), "c": (16, 20, 3, 13),
        "d": (4, 33, 13, 3), "e": (1, 20, 3, 13), "f": (1, 4, 3, 13), "g": (4, 17, 13, 3),
    }
    for index, digit in enumerate(code):
        offset_x = 8 + index * 24 + rnd.randint(-1, 1)
        offset_y = 7 + rnd.randint(-2, 2)
        color = (rnd.randrange(25, 80), rnd.randrange(55, 110), rnd.randrange(100, 170))
        for name in _DIGIT_SEGMENTS[digit]:
            x, y, w, h = segments[name]
            _rect(pixels, width, height, offset_x + x, offset_y + y, w, h, color)
    for _ in range(220):
        x, y = rnd.randrange(width), rnd.randrange(height)
        pos = (y * width + x) * 3
        pixels[pos:pos + 3] = bytes((rnd.randrange(80, 220), rnd.randrange(80, 220), rnd.randrange(80, 220)))
    rows = bytearray()
    row_width = width * 3
    for y in range(height):
        rows.append(0)
        start = y * row_width
        rows.extend(pixels[start:start + row_width])
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _png_chunk(b"IEND", b"")
    )


def issue_captcha(
    scene: str,
    tenant_code: str | None = None,
    login_name: str | None = None,
    client_nonce: str | None = None,
    client_type: str | None = None,
) -> dict[str, Any]:
    scene = (scene or "").strip().upper()
    if scene not in _ALLOWED_SCENES:
        raise AppException("VALIDATION_ERROR", "不支持的验证码场景")
    login_name, client_nonce, client_type = _validate_issue_binding(
        scene, login_name, client_nonce, client_type,
    )
    if not rate_limit(f"captcha-issue:{_ip_hash()}", 12, 60):
        raise AppException("RATE_LIMITED", "验证码获取过于频繁，请稍后再试", http_status=429)
    code = f"{secrets.randbelow(1_000_000):06d}"
    captcha_id = "cp_" + secrets.token_urlsafe(24)
    ttl = max(60, int(getattr(settings, "CAPTCHA_TTL_SECONDS", 120) or 120))
    payload = {
        "answer": _digest(f"answer\n{captcha_id}\n{code}"),
        "scene": scene,
        "subject": _subject_hash(tenant_code, login_name),
        "nonce": _nonce_hash(client_nonce),
        "clientType": client_type,
        "ip": _ip_hash(),
        "issuedAt": int(time.time()),
    }
    _store(captcha_id, payload, ttl)
    result = {
        "captchaId": captcha_id,
        "imageDataUrl": "data:image/png;base64," + base64.b64encode(_render_png(code)).decode("ascii"),
        "expiresIn": ttl,
    }
    if str(settings.APP_ENV or "").strip().lower() == "test" and not _is_strict_env():
        result["devCode"] = code
    return result


def verify_captcha(
    captcha_id: str | None,
    captcha_code: str | None,
    scene: str,
    tenant_code: str | None = None,
    login_name: str | None = None,
    client_nonce: str | None = None,
    client_type: str | None = None,
) -> None:
    details = {"captchaRequired": True, "scene": scene}
    if not captcha_id or not captcha_code:
        raise AppException("CAPTCHA_REQUIRED", "请输入图形验证码后继续", details=details, http_status=401)
    payload = _consume(captcha_id)
    if payload is None:
        raise AppException("CAPTCHA_EXPIRED", "验证码已过期，请刷新后重试", details=details, http_status=401)
    if payload.get("scene") != scene:
        raise AppException("CAPTCHA_INVALID", "验证码无效，请刷新后重试", details=details, http_status=401)
    expected_subject = str(payload.get("subject") or "")
    if not hmac.compare_digest(expected_subject, _subject_hash(tenant_code, login_name)):
        raise AppException("CAPTCHA_INVALID", "验证码无效，请刷新后重试", details=details, http_status=401)
    expected_nonce = str(payload.get("nonce") or "")
    if not hmac.compare_digest(expected_nonce, _nonce_hash(client_nonce)):
        raise AppException("CAPTCHA_INVALID", "验证码无效，请刷新后重试", details=details, http_status=401)
    expected_client_type = str(payload.get("clientType") or "").strip().upper()
    actual_client_type = str(client_type or "").strip().upper()
    if not hmac.compare_digest(expected_client_type, actual_client_type):
        raise AppException("CAPTCHA_INVALID", "验证码无效，请刷新后重试", details=details, http_status=401)
    actual = _digest(f"answer\n{captcha_id}\n{str(captcha_code).strip()}")
    if not hmac.compare_digest(str(payload.get("answer") or ""), actual):
        raise AppException("CAPTCHA_INVALID", "验证码错误，请重新输入", details=details, http_status=401)


def captcha_required(scene: str, tenant_code: str | None, login_name: str | None) -> bool:
    if scene == PLATFORM_LOGIN:
        return True
    threshold = max(1, int(getattr(settings, "CAPTCHA_AFTER_FAILURES", 2) or 2))
    key = login_guard_key(tenant_code, login_name)
    count = _strict_login_failure_count(key) if _is_strict_env() else get_login_failure_count(key)
    return count >= threshold


def enforce_login_captcha(
    scene: str,
    tenant_code: str | None,
    login_name: str | None,
    captcha_id: str | None,
    captcha_code: str | None,
    client_nonce: str | None,
    client_type: str | None = None,
) -> None:
    required = captcha_required(scene, tenant_code, login_name)
    supplied = bool(captcha_id or captcha_code)
    if not required and not supplied:
        return
    verify_captcha(captcha_id, captcha_code, scene, tenant_code, login_name, client_nonce, client_type)


def reset_for_tests() -> None:
    with _MEMORY_LOCK:
        _MEMORY.clear()
