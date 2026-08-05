from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


AUTH_CHALLENGE = r'''"""Adaptive graphical captcha for password-bearing authentication flows.

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
_ALLOWED_SCENES = {PASSWORD_LOGIN, PLATFORM_LOGIN, WX_BIND}
_DIGIT_SEGMENTS = {
    "0": "abcedf", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgecd", "7": "abc", "8": "abcdefg", "9": "abfgcd",
}
_MEMORY: dict[str, tuple[float, str]] = {}
_MEMORY_LOCK = threading.Lock()


def _is_strict_env() -> bool:
    return settings.APP_ENV in {"production", "staging"} or settings.DEPLOYMENT_MODE == "production"


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
                raise AppException("AUTH_STORE_UNAVAILABLE", "验证码服务暂时不可用，请稍后重试", http_status=503) from exc
    if _is_strict_env():
        raise AppException("AUTH_STORE_UNAVAILABLE", "验证码服务暂时不可用，请稍后重试", http_status=503)
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
                raw = client.eval("local v=redis.call('GET',KEYS[1]); if v then redis.call('DEL',KEYS[1]) end; return v", 1, key)
            return json.loads(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            if _is_strict_env():
                raise AppException("AUTH_STORE_UNAVAILABLE", "验证码服务暂时不可用，请稍后重试", http_status=503) from exc
    if _is_strict_env():
        raise AppException("AUTH_STORE_UNAVAILABLE", "验证码服务暂时不可用，请稍后重试", http_status=503)
    with _MEMORY_LOCK:
        item = _MEMORY.pop(captcha_id, None)
    if not item or item[0] < time.time():
        return None
    return json.loads(item[1])


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _line(pixels: bytearray, width: int, height: int, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
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
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


def _rect(pixels: bytearray, width: int, height: int, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
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
        _line(pixels, width, height, rnd.randrange(width), rnd.randrange(height), rnd.randrange(width), rnd.randrange(height),
              (rnd.randrange(120, 205), rnd.randrange(130, 210), rnd.randrange(150, 220)))
    seg = {
        "a": (4, 1, 13, 3), "b": (16, 4, 3, 13), "c": (16, 20, 3, 13),
        "d": (4, 33, 13, 3), "e": (1, 20, 3, 13), "f": (1, 4, 3, 13), "g": (4, 17, 13, 3),
    }
    for index, digit in enumerate(code):
        ox = 8 + index * 24 + rnd.randint(-1, 1)
        oy = 7 + rnd.randint(-2, 2)
        color = (rnd.randrange(25, 80), rnd.randrange(55, 110), rnd.randrange(100, 170))
        for name in _DIGIT_SEGMENTS[digit]:
            x, y, w, h = seg[name]
            _rect(pixels, width, height, ox + x, oy + y, w, h, color)
    for _ in range(220):
        x, y = rnd.randrange(width), rnd.randrange(height)
        pos = (y * width + x) * 3
        pixels[pos:pos + 3] = bytes((rnd.randrange(80, 220), rnd.randrange(80, 220), rnd.randrange(80, 220)))
    rows = b"".join(b"\x00" + bytes(pixels[y * width * 3:(y + 1) * width * 3]) for y in range(height))
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + _png_chunk(b"IDAT", zlib.compress(rows, 9)) + _png_chunk(b"IEND", b"")


def issue_captcha(scene: str, tenant_code: str | None = None, login_name: str | None = None,
                  client_nonce: str | None = None, client_type: str | None = None) -> dict[str, Any]:
    scene = (scene or "").strip().upper()
    if scene not in _ALLOWED_SCENES:
        raise AppException("VALIDATION_ERROR", "不支持的验证码场景")
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
        "clientType": (client_type or "").strip().upper(),
        "ip": _ip_hash(),
        "issuedAt": int(time.time()),
    }
    _store(captcha_id, payload, ttl)
    result = {
        "captchaId": captcha_id,
        "imageDataUrl": "data:image/png;base64," + base64.b64encode(_render_png(code)).decode("ascii"),
        "expiresIn": ttl,
    }
    if settings.APP_ENV == "test":
        result["devCode"] = code
    return result


def verify_captcha(captcha_id: str | None, captcha_code: str | None, scene: str,
                   tenant_code: str | None = None, login_name: str | None = None,
                   client_nonce: str | None = None) -> None:
    if not captcha_id or not captcha_code:
        raise AppException("CAPTCHA_REQUIRED", "请输入图形验证码后继续", details={"captchaRequired": True, "scene": scene}, http_status=401)
    payload = _consume(captcha_id)
    if payload is None:
        raise AppException("CAPTCHA_EXPIRED", "验证码已过期，请刷新后重试", details={"captchaRequired": True, "scene": scene}, http_status=401)
    if payload.get("scene") != scene:
        raise AppException("CAPTCHA_INVALID", "验证码无效，请刷新后重试", details={"captchaRequired": True, "scene": scene}, http_status=401)
    expected_subject = payload.get("subject") or ""
    if expected_subject and not hmac.compare_digest(expected_subject, _subject_hash(tenant_code, login_name)):
        raise AppException("CAPTCHA_INVALID", "验证码无效，请刷新后重试", details={"captchaRequired": True, "scene": scene}, http_status=401)
    expected_nonce = payload.get("nonce") or ""
    if expected_nonce and not hmac.compare_digest(expected_nonce, _nonce_hash(client_nonce)):
        raise AppException("CAPTCHA_INVALID", "验证码无效，请刷新后重试", details={"captchaRequired": True, "scene": scene}, http_status=401)
    actual = _digest(f"answer\n{captcha_id}\n{str(captcha_code).strip()}")
    if not hmac.compare_digest(str(payload.get("answer") or ""), actual):
        raise AppException("CAPTCHA_INVALID", "验证码错误，请重新输入", details={"captchaRequired": True, "scene": scene}, http_status=401)


def captcha_required(scene: str, tenant_code: str | None, login_name: str | None) -> bool:
    if scene == PLATFORM_LOGIN:
        return True
    threshold = max(1, int(getattr(settings, "CAPTCHA_AFTER_FAILURES", 2) or 2))
    return get_login_failure_count(login_guard_key(tenant_code, login_name)) >= threshold


def enforce_login_captcha(scene: str, tenant_code: str | None, login_name: str | None,
                          captcha_id: str | None, captcha_code: str | None,
                          client_nonce: str | None) -> None:
    required = captcha_required(scene, tenant_code, login_name)
    supplied = bool(captcha_id or captcha_code)
    if not required and not supplied:
        return
    verify_captcha(captcha_id, captcha_code, scene, tenant_code, login_name, client_nonce)


def reset_for_tests() -> None:
    with _MEMORY_LOCK:
        _MEMORY.clear()
'''

write("backend/app/services/auth_challenge_service.py", AUTH_CHALLENGE)

# Shared failure count getter used by adaptive captcha.
replace_once(
    "backend/app/core/token_store.py",
    "\ndef reset_login_failures(key: str) -> None:\n",
    "\ndef get_login_failure_count(key: str) -> int:\n"
    "    \"\"\"Return the bounded failed-password count shared by the captcha risk gate.\"\"\"\n"
    "    from app.core.redis_client import cache_get\n"
    "    shared = cache_get(f\"auth:login-fail:{key}\")\n"
    "    if shared is not None:\n"
    "        try:\n"
    "            return max(0, int(shared))\n"
    "        except (TypeError, ValueError):\n"
    "            return 0\n"
    "    rec = _fail.get(key)\n"
    "    return max(0, int(rec[0])) if rec else 0\n\n\n"
    "def reset_login_failures(key: str) -> None:\n",
)

# Hash account identifiers in Redis keys and make the platform route non-bypassable.
replace_once(
    "backend/app/services/auth_service_db.py",
    "from app.core.security import create_access_token, hash_password, verify_password\n",
    "from app.core.security import create_access_token, hash_password, verify_password\n"
    "from app.services.auth_challenge_service import login_guard_key\n",
)
replace_once(
    "backend/app/services/auth_service_db.py",
    "    lock_key = f\"pw:{tenant_code or '*'}:{login_name}\"\n",
    "    lock_key = login_guard_key(tenant_code, login_name)\n",
)
replace_once(
    "backend/app/services/auth_service_db.py",
    "        user = _find_login_user(db, login_name, tenant_code)\n        if not user or not verify_password(password, user.password_hash):\n",
    "        user = _find_login_user(db, login_name, tenant_code)\n"
    "        platform_account = bool(user and (user.user_type or '').upper() in {'PLATFORM_OP', 'PLATFORM_SUPER_ADMIN'})\n"
    "        platform_client = (client_type or '').upper() == 'PLATFORM_PC'\n"
    "        if user and platform_account != platform_client:\n"
    "            raise AppException('UNAUTHORIZED', '账号、学校编码或密码不正确')\n"
    "        if not user or not verify_password(password, user.password_hash):\n",
)
replace_once(
    "backend/app/services/auth_service_db.py",
    "            if locked:\n                raise AppException(\"UNAUTHORIZED\", f\"失败次数过多，账号已锁定 {lock_minutes} 分钟\")\n            raise AppException(\"UNAUTHORIZED\", \"账号、学校编码或密码不正确\")\n",
    "            if locked:\n"
    "                raise AppException(\"UNAUTHORIZED\", f\"失败次数过多，账号已锁定 {lock_minutes} 分钟\")\n"
    "            if count >= max(1, int(getattr(settings, 'CAPTCHA_AFTER_FAILURES', 2) or 2)):\n"
    "                raise AppException('CAPTCHA_REQUIRED', '账号、学校编码或密码不正确，请输入验证码后继续',\n"
    "                                   details={'captchaRequired': True, 'scene': 'PASSWORD_LOGIN'}, http_status=401)\n"
    "            raise AppException(\"UNAUTHORIZED\", \"账号、学校编码或密码不正确\")\n",
)

# Apply the same password failure/lock policy to first-time WeChat binding.
replace_once(
    "backend/app/services/wx_auth_service.py",
    "from app.core.security import create_access_token, decode_token, verify_password\n",
    "from app.core.security import create_access_token, decode_token, verify_password\n"
    "from app.core.token_store import login_locked, record_login_failure, reset_login_failures\n"
    "from app.services.auth_challenge_service import login_guard_key\n",
)
replace_once(
    "backend/app/services/wx_auth_service.py",
    "    db = get_sessionmaker()()\n    try:\n        user = _find_login_user(db, login_name, (tenant_code or \"\").strip() or None)\n        if not user or not verify_password(password, user.password_hash):\n            raise AppException(\"UNAUTHORIZED\", \"账号、学校编码或密码不正确\")\n",
    "    normalized_tenant = (tenant_code or '').strip() or None\n"
    "    lock_key = login_guard_key(normalized_tenant, login_name)\n"
    "    remain = login_locked(lock_key)\n"
    "    if remain > 0:\n"
    "        raise AppException('UNAUTHORIZED', f'失败次数过多，账号已锁定，请 {remain // 60 + 1} 分钟后再试')\n"
    "    db = get_sessionmaker()()\n"
    "    try:\n"
    "        user = _find_login_user(db, login_name, normalized_tenant)\n"
    "        if not user or not verify_password(password, user.password_hash):\n"
    "            from app.services.system_config_service import get_int\n"
    "            lock_minutes = get_int('SEC_LOCK_MINUTES', 15)\n"
    "            count, locked = record_login_failure(lock_key, threshold=get_int('SEC_LOCK_MAX_FAIL', 5),\n"
    "                                                 lock_seconds=lock_minutes * 60)\n"
    "            if locked:\n"
    "                raise AppException('UNAUTHORIZED', f'失败次数过多，账号已锁定 {lock_minutes} 分钟')\n"
    "            if count >= max(1, int(getattr(settings, 'CAPTCHA_AFTER_FAILURES', 2) or 2)):\n"
    "                raise AppException('CAPTCHA_REQUIRED', '账号、学校编码或密码不正确，请输入验证码后继续',\n"
    "                                   details={'captchaRequired': True, 'scene': 'WX_BIND'}, http_status=401)\n"
    "            raise AppException('UNAUTHORIZED', '账号、学校编码或密码不正确')\n",
)
replace_once(
    "backend/app/services/wx_auth_service.py",
    "        db.commit()\n        db.refresh(user)\n        return build_login_result(db, user, client_type=\"MP\")\n",
    "        db.commit()\n        db.refresh(user)\n        reset_login_failures(lock_key)\n        return build_login_result(db, user, client_type=\"MP\")\n",
)

# Public captcha endpoint and enforcement at both password-bearing routes.
replace_once(
    "backend/app/api/v1/auth.py",
    "from app.services import auth_service_db\n",
    "from app.services import auth_service_db\nfrom app.services import auth_challenge_service as captcha_svc\n",
)
replace_once(
    "backend/app/api/v1/auth.py",
    "    clientType: str = Field(\"PC\", description=\"PC / STUDENT_MINI / TEACHER_MINI / MP\")\n",
    "    clientType: str = Field(\"PC\", description=\"PC / PLATFORM_PC / STUDENT_MINI / TEACHER_MINI / MP\")\n"
    "    captchaId: str | None = Field(None, max_length=100)\n"
    "    captchaCode: str | None = Field(None, min_length=4, max_length=12)\n"
    "    clientNonce: str | None = Field(None, max_length=128)\n",
)
replace_once(
    "backend/app/api/v1/auth.py",
    "\n@router.post(\"/login\", summary=\"账号密码登录（真实校验：t_user + pbkdf2 哈希；demo 账号仅访问 demo-school 租户）\")\ndef login(body: PasswordLoginRequest):\n    _login_rate_guard()\n",
    "\nclass CaptchaRequest(BaseModel):\n"
    "    scene: str = Field(..., min_length=1, max_length=40)\n"
    "    tenantCode: str | None = Field(None, max_length=100)\n"
    "    loginName: str | None = Field(None, max_length=100)\n"
    "    clientNonce: str | None = Field(None, max_length=128)\n"
    "    clientType: str | None = Field(None, max_length=40)\n\n\n"
    "@router.post('/captcha', summary='获取登录图形验证码（短时、单次、生产 Redis 原子消费）')\n"
    "def captcha(body: CaptchaRequest):\n"
    "    return success(captcha_svc.issue_captcha(body.scene, body.tenantCode, body.loginName,\n"
    "                                             body.clientNonce, body.clientType))\n\n\n"
    "@router.post(\"/login\", summary=\"账号密码登录（真实校验：t_user + pbkdf2 哈希；demo 账号仅访问 demo-school 租户）\")\n"
    "def login(body: PasswordLoginRequest):\n"
    "    _login_rate_guard()\n"
    "    scene = captcha_svc.PLATFORM_LOGIN if body.clientType.strip().upper() == 'PLATFORM_PC' else captcha_svc.PASSWORD_LOGIN\n"
    "    captcha_svc.enforce_login_captcha(scene, body.tenantCode, body.loginName, body.captchaId,\n"
    "                                      body.captchaCode, body.clientNonce)\n",
)
replace_once(
    "backend/app/api/v1/auth.py",
    "    password: str = Field(..., min_length=1, description=\"校园账号密码\")\n",
    "    password: str = Field(..., min_length=1, description=\"校园账号密码\")\n"
    "    captchaId: str | None = Field(None, max_length=100)\n"
    "    captchaCode: str | None = Field(None, min_length=4, max_length=12)\n"
    "    clientNonce: str | None = Field(None, max_length=128)\n",
)
replace_once(
    "backend/app/api/v1/auth.py",
    "def wx_bind(body: WxBindRequest):\n    _login_rate_guard()\n    from app.services import wx_auth_service\n",
    "def wx_bind(body: WxBindRequest):\n"
    "    _login_rate_guard()\n"
    "    captcha_svc.enforce_login_captcha(captcha_svc.WX_BIND, body.tenantCode, body.loginName,\n"
    "                                      body.captchaId, body.captchaCode, body.clientNonce)\n"
    "    from app.services import wx_auth_service\n",
)

# Configuration: adaptive threshold, strict TTL, and explicit prohibition of guardian SMS login.
replace_once(
    "backend/app/core/config.py",
    "    WX_SECRET: str = \"\"                  # 小程序 AppSecret；仅经 .env/环境变量注入，禁止写进仓库\n",
    "    WX_SECRET: str = \"\"                  # 小程序 AppSecret；仅经 .env/环境变量注入，禁止写进仓库\n"
    "    CAPTCHA_TTL_SECONDS: int = 120\n"
    "    CAPTCHA_AFTER_FAILURES: int = 2\n",
)
replace_once(
    "backend/app/core/config.py",
    "    SMS_MAX_RETRY: int = 2              # 发送失败重试次数\n",
    "    SMS_MAX_RETRY: int = 2              # 发送失败重试次数\n"
    "    GUARDIAN_SMS_LOGIN_ENABLED: bool = False  # 验证短信仅允许找回密码；家长短信登录默认永久关闭\n"
    "    SMS_TEMPLATE_PASSWORD_RESET: str = \"\"  # 找回密码专用模板；不得复用于登录\n",
)
replace_once(
    "backend/app/student_portal/services/guardian_service.py",
    "from app.core.exceptions import AppException\n",
    "from app.core.exceptions import AppException\nfrom app.core.config import settings\n",
)
replace_once(
    "backend/app/student_portal/services/guardian_service.py",
    "def request_otp(body: dict) -> dict:\n    \"\"\"家长请求登录验证码。通用成功响应（不泄露手机号是否被授权）；仅在被授权时真正下发。\"\"\"\n",
    "def request_otp(body: dict) -> dict:\n"
    "    \"\"\"Legacy guardian SMS login is disabled by default; verification SMS is reserved for password reset.\"\"\"\n"
    "    if not settings.GUARDIAN_SMS_LOGIN_ENABLED:\n"
    "        raise AppException('NO_PERMISSION', '家长短信登录已停用，请使用学校统一身份入口')\n",
)

LOGIN_CAPTCHA_VUE = r'''<template>
  <div v-if="visible" class="login-captcha">
    <label :for="inputId">图形验证码</label>
    <div class="login-captcha__row">
      <input :id="inputId" :value="modelValue" inputmode="numeric" maxlength="6" autocomplete="off"
             placeholder="请输入图中 6 位数字" @input="$emit('update:modelValue', $event.target.value.replace(/\D/g, '').slice(0, 6))">
      <button type="button" class="login-captcha__image" :disabled="loading" title="点击换一张" @click="$emit('refresh')">
        <img v-if="image" :src="image" alt="图形验证码，点击刷新"><span v-else>{{ loading ? '加载中…' : '换一张' }}</span>
      </button>
    </div>
    <small>看不清可点击图片刷新；验证码 2 分钟内、单次有效。</small>
  </div>
</template>
<script>
export default {
  name: 'LoginCaptcha',
  props: { visible: Boolean, modelValue: { type: String, default: '' }, image: { type: String, default: '' }, loading: Boolean, inputId: { type: String, default: 'login-captcha' } },
  emits: ['update:modelValue', 'refresh']
}
</script>
<style scoped>
.login-captcha { margin-top: 14px; }.login-captcha label { display: block; margin-bottom: 7px; color: #34465f; font-size: 12px; font-weight: 650; }
.login-captcha__row { display: grid; grid-template-columns: 1fr 154px; gap: 9px; }.login-captcha__row input { width: 100%; height: 44px; box-sizing: border-box; padding: 0 13px; border: 1px solid #dbe3ed; border-radius: 9px; outline: none; }
.login-captcha__image { height: 44px; overflow: hidden; padding: 0; border: 1px solid #dbe3ed; border-radius: 9px; background: #f8fafc; cursor: pointer; }.login-captcha__image img { display: block; width: 100%; height: 100%; object-fit: cover; }.login-captcha__image span { color: #536780; font-size: 12px; }
.login-captcha small { display: block; margin-top: 6px; color: #8290a3; font-size: 11px; }@media (max-width: 420px) { .login-captcha__row { grid-template-columns: 1fr 132px; } }
</style>
'''
write("frontend/src/components/auth/LoginCaptcha.vue", LOGIN_CAPTCHA_VUE)

# PC HTTP client: preserve structured details and accept a challenge payload/client type.
replace_once(
    "frontend/src/services/http/client.js",
    "      err.bizCode = payload.bizCode           // NO_PERMISSION / NO_DATA_SCOPE：供页面渲染统一无权限/无范围态\n      err.traceId = payload.traceId\n",
    "      err.bizCode = payload.bizCode           // NO_PERMISSION / NO_DATA_SCOPE：供页面渲染统一无权限/无范围态\n"
    "      err.details = payload.details\n"
    "      err.traceId = payload.traceId\n",
)
replace_once(
    "frontend/src/services/http/client.js",
    "/** 账号密码登录（POST /api/v1/auth/login，真实校验）；成功后自动持有 token */\nexport async function loginWithPassword(loginName, password, tenantCode = '') {\n",
    "/** 获取短时、单次图形验证码。 */\n"
    "export async function issueLoginCaptcha(payload) {\n"
    "  return rawRequest('/auth/captcha', { method: 'POST', auth: false, forceProbe: true, body: payload })\n"
    "}\n\n"
    "/** 账号密码登录（POST /api/v1/auth/login，真实校验）；成功后自动持有 token */\n"
    "export async function loginWithPassword(loginName, password, tenantCode = '', challenge = {}) {\n",
)
replace_once(
    "frontend/src/services/http/client.js",
    "    body: { loginName, password, tenantCode: tenantCode || undefined, clientType: 'PC' }\n",
    "    body: { loginName, password, tenantCode: tenantCode || undefined,\n"
    "      clientType: challenge.clientType || 'PC', captchaId: challenge.captchaId || undefined,\n"
    "      captchaCode: challenge.captchaCode || undefined, clientNonce: challenge.clientNonce || undefined }\n",
)

# Teacher/school PC adaptive captcha.
replace_once("frontend/src/views/LoginView.vue", "          </div>\n\n          <label class=\"remember\">", "          </div>\n\n          <LoginCaptcha :visible=\"captcha.required\" v-model=\"captcha.code\" :image=\"captcha.image\" :loading=\"captcha.loading\" @refresh=\"refreshCaptcha\" />\n\n          <label class=\"remember\">")
replace_once(
    "frontend/src/views/LoginView.vue",
    "import { isPlatformSuperAdmin, loginWithPassword } from '@/services/http/client'\n",
    "import { isPlatformSuperAdmin, issueLoginCaptcha, loginWithPassword } from '@/services/http/client'\n"
    "import LoginCaptcha from '@/components/auth/LoginCaptcha.vue'\n",
)
replace_once("frontend/src/views/LoginView.vue", "  name: 'LoginView',\n", "  name: 'LoginView',\n  components: { LoginCaptcha },\n")
replace_once(
    "frontend/src/views/LoginView.vue",
    "      error: '',\n      form: { tenantCode: '', loginName: '', password: '' }\n",
    "      error: '',\n"
    "      captcha: { required: false, id: '', code: '', image: '', loading: false, nonce: `web-${Date.now()}-${Math.random()}` },\n"
    "      form: { tenantCode: '', loginName: '', password: '' }\n",
)
replace_once(
    "frontend/src/views/LoginView.vue",
    "  methods: {\n    async doLogin() {\n",
    "  methods: {\n"
    "    async refreshCaptcha() {\n"
    "      this.captcha.loading = true\n"
    "      try {\n"
    "        const d = await issueLoginCaptcha({ scene: 'PASSWORD_LOGIN', tenantCode: this.form.tenantCode || undefined, loginName: this.form.loginName, clientNonce: this.captcha.nonce, clientType: 'PC' })\n"
    "        this.captcha.id = d.captchaId; this.captcha.image = d.imageDataUrl; this.captcha.code = ''\n"
    "      } catch (e) { this.error = e?.message || '验证码加载失败，请稍后重试' } finally { this.captcha.loading = false }\n"
    "    },\n"
    "    async requireCaptcha(error) {\n"
    "      const code = error?.bizCode || ''\n"
    "      if (!code.startsWith('CAPTCHA_') && !error?.details?.captchaRequired) return false\n"
    "      this.captcha.required = true; await this.refreshCaptcha(); return true\n"
    "    },\n"
    "    async doLogin() {\n",
)
replace_once(
    "frontend/src/views/LoginView.vue",
    "        const data = await loginWithPassword(this.form.loginName, this.form.password, this.form.tenantCode)\n",
    "        if (this.captcha.required && (!this.captcha.id || this.captcha.code.length !== 6)) { this.error = '请输入图中 6 位验证码'; return }\n"
    "        const data = await loginWithPassword(this.form.loginName, this.form.password, this.form.tenantCode, { captchaId: this.captcha.id, captchaCode: this.captcha.code, clientNonce: this.captcha.nonce, clientType: 'PC' })\n",
)
replace_once(
    "frontend/src/views/LoginView.vue",
    "      } catch (e) {\n        this.error = e?.message || '登录失败，请稍后重试'\n",
    "      } catch (e) {\n"
    "        await this.requireCaptcha(e)\n"
    "        this.error = e?.message || '登录失败，请稍后重试'\n",
)

# Platform PC always requires captcha and uses an unambiguous client type.
replace_once("frontend/src/views/PlatformLoginView.vue", "          </label>\n          <p v-if=\"error\"", "          </label>\n          <LoginCaptcha visible v-model=\"captcha.code\" :image=\"captcha.image\" :loading=\"captcha.loading\" input-id=\"platform-captcha\" @refresh=\"refreshCaptcha\" />\n          <p v-if=\"error\"")
replace_once(
    "frontend/src/views/PlatformLoginView.vue",
    "import { clearAuthSession, isPlatformSuperAdmin, loginWithPassword } from '@/services/http/client'\n",
    "import { clearAuthSession, isPlatformSuperAdmin, issueLoginCaptcha, loginWithPassword } from '@/services/http/client'\n"
    "import LoginCaptcha from '@/components/auth/LoginCaptcha.vue'\n",
)
replace_once("frontend/src/views/PlatformLoginView.vue", "  name: 'PlatformLoginView',\n", "  name: 'PlatformLoginView',\n  components: { LoginCaptcha },\n")
replace_once(
    "frontend/src/views/PlatformLoginView.vue",
    "      error: '',\n      form: { tenantCode: 'platform', loginName: '', password: '' }\n",
    "      error: '',\n"
    "      captcha: { id: '', code: '', image: '', loading: false, nonce: `platform-${Date.now()}-${Math.random()}` },\n"
    "      form: { tenantCode: 'platform', loginName: '', password: '' }\n",
)
replace_once("frontend/src/views/PlatformLoginView.vue", "  methods: {\n    async submit() {", "  mounted() { this.refreshCaptcha() },\n  methods: {\n    async refreshCaptcha() {\n      this.captcha.loading = true\n      try { const d = await issueLoginCaptcha({ scene: 'PLATFORM_LOGIN', tenantCode: this.form.tenantCode, loginName: this.form.loginName, clientNonce: this.captcha.nonce, clientType: 'PLATFORM_PC' }); this.captcha.id = d.captchaId; this.captcha.image = d.imageDataUrl; this.captcha.code = '' }\n      catch (e) { this.error = e?.message || '验证码加载失败' } finally { this.captcha.loading = false }\n    },\n    async submit() {")
replace_once(
    "frontend/src/views/PlatformLoginView.vue",
    "        await loginWithPassword(this.form.loginName, this.form.password, this.form.tenantCode || 'platform')\n",
    "        if (!this.captcha.id || this.captcha.code.length !== 6) { this.error = '请输入图中 6 位验证码'; return }\n"
    "        await loginWithPassword(this.form.loginName, this.form.password, this.form.tenantCode || 'platform', { captchaId: this.captcha.id, captchaCode: this.captcha.code, clientNonce: this.captcha.nonce, clientType: 'PLATFORM_PC' })\n",
)
replace_once(
    "frontend/src/views/PlatformLoginView.vue",
    "      } catch (error) {\n        this.error = error?.message || '登录失败，请检查账号、密码和平台编码。'\n",
    "      } catch (error) {\n"
    "        if ((error?.bizCode || '').startsWith('CAPTCHA_') || error?.details?.captchaRequired) await this.refreshCaptcha()\n"
    "        this.error = error?.message || '登录失败，请检查账号、密码和平台编码。'\n",
)

# Student PC portal uses the same contract but keeps its independent session store.
write("student-portal/src/components/auth/LoginCaptcha.vue", LOGIN_CAPTCHA_VUE)
replace_once(
    "student-portal/src/services/request.js",
    "    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e\n",
    "    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; e.bizCode = payload.bizCode; e.details = payload.details; e.traceId = payload.traceId; throw e\n",
)
replace_once(
    "student-portal/src/services/portalApi.js",
    "  login: (loginName, password, tenantCode) =>\n    request('/auth/login', { method: 'POST', auth: false, body: { loginName, password, ...(tenantCode ? { tenantCode } : {}), clientType: 'PC' } }),\n",
    "  captcha: (body) => request('/auth/captcha', { method: 'POST', auth: false, body }),\n"
    "  login: (loginName, password, tenantCode, challenge = {}) =>\n"
    "    request('/auth/login', { method: 'POST', auth: false, body: { loginName, password, ...(tenantCode ? { tenantCode } : {}), clientType: 'PC', captchaId: challenge.captchaId || undefined, captchaCode: challenge.captchaCode || undefined, clientNonce: challenge.clientNonce || undefined } }),\n",
)
replace_once("student-portal/src/stores/session.js", "    async login(loginName, password, tenantCode) {\n      const data = await portalApi.login(loginName, password, tenantCode)\n", "    async login(loginName, password, tenantCode, challenge = {}) {\n      const data = await portalApi.login(loginName, password, tenantCode, challenge)\n")
replace_once("student-portal/src/views/login/LoginView.vue", "          </div>\n          <label class=\"remember\">", "          </div>\n          <LoginCaptcha :visible=\"captcha.required\" v-model=\"captcha.code\" :image=\"captcha.image\" :loading=\"captcha.loading\" input-id=\"student-login-captcha\" @refresh=\"refreshCaptcha\" />\n          <label class=\"remember\">")
replace_once("student-portal/src/views/login/LoginView.vue", "import { useUiStore } from '../../stores/ui'\n", "import { useUiStore } from '../../stores/ui'\nimport LoginCaptcha from '../../components/auth/LoginCaptcha.vue'\nimport { portalApi } from '../../services/portalApi'\n")
replace_once("student-portal/src/views/login/LoginView.vue", "const agree = ref(false)\n", "const agree = ref(false)\nconst captcha = ref({ required: false, id: '', code: '', image: '', loading: false, nonce: `student-${Date.now()}-${Math.random()}` })\n")
replace_once(
    "student-portal/src/views/login/LoginView.vue",
    "function forgotPassword() {\n  ui.notify('请联系辅导员或学校管理员重置密码')\n}\n\nasync function doLogin() {\n",
    "function forgotPassword() {\n  ui.notify('找回密码短信仅用于身份验证；功能开通前请联系学校管理员重置')\n}\n\n"
    "async function refreshCaptcha() {\n"
    "  captcha.value.loading = true\n"
    "  try { const d = await portalApi.captcha({ scene: 'PASSWORD_LOGIN', tenantCode: tenantCode.value || undefined, loginName: loginName.value, clientNonce: captcha.value.nonce, clientType: 'PC' }); captcha.value.id = d.captchaId; captcha.value.image = d.imageDataUrl; captcha.value.code = '' }\n"
    "  catch (e) { error.value = e?.message || '验证码加载失败，请稍后重试' } finally { captcha.value.loading = false }\n"
    "}\n\n"
    "async function doLogin() {\n",
)
replace_once(
    "student-portal/src/views/login/LoginView.vue",
    "    await session.login(loginName.value, password.value, tenantCode.value || undefined)\n",
    "    if (captcha.value.required && (!captcha.value.id || captcha.value.code.length !== 6)) { error.value = '请输入图中 6 位验证码'; return }\n"
    "    await session.login(loginName.value, password.value, tenantCode.value || undefined, { captchaId: captcha.value.id, captchaCode: captcha.value.code, clientNonce: captcha.value.nonce })\n",
)
replace_once(
    "student-portal/src/views/login/LoginView.vue",
    "  } catch (e) {\n    error.value = e?.notStudent ? '该账号不是学生账号，请使用教师端入口' : (e?.message || '登录失败，请稍后重试')\n",
    "  } catch (e) {\n"
    "    if ((e?.bizCode || '').startsWith('CAPTCHA_') || e?.details?.captchaRequired) { captcha.value.required = true; await refreshCaptcha() }\n"
    "    error.value = e?.notStudent ? '该账号不是学生账号，请使用教师端入口' : (e?.message || '登录失败，请稍后重试')\n",
)

# Miniapp: preserve backend error metadata and show captcha only for password login / first binding.
replace_once(
    "miniapp/src/services/request.js",
    "            traceId: body.traceId,\n            httpStatus: res.statusCode\n",
    "            traceId: body.traceId,\n            bizCode: body.bizCode,\n            details: body.details,\n            httpStatus: res.statusCode\n",
)
replace_once("miniapp/src/components/login/MiniLoginAuthPanel.vue", "      <input v-model=\"account.password\" class=\"field\" type=\"password\" password placeholder=\"密码\" placeholder-class=\"field__placeholder\" />\n", "      <input v-model=\"account.password\" class=\"field\" type=\"password\" password placeholder=\"密码\" placeholder-class=\"field__placeholder\" />\n      <view v-if=\"accountCaptcha.required\" class=\"captcha-row\"><input v-model=\"accountCaptcha.code\" class=\"field captcha-row__input\" type=\"number\" maxlength=\"6\" placeholder=\"图形验证码\" /><image class=\"captcha-row__image\" :src=\"accountCaptcha.image\" mode=\"aspectFill\" @click=\"loadCaptcha('account')\" /></view>\n")
replace_once("miniapp/src/components/login/MiniLoginAuthPanel.vue", "        <input v-model=\"bindForm.password\" class=\"field\" type=\"password\" password placeholder=\"密码\" placeholder-class=\"field__placeholder\" />\n", "        <input v-model=\"bindForm.password\" class=\"field\" type=\"password\" password placeholder=\"密码\" placeholder-class=\"field__placeholder\" />\n        <view v-if=\"bindCaptcha.required\" class=\"captcha-row\"><input v-model=\"bindCaptcha.code\" class=\"field captcha-row__input\" type=\"number\" maxlength=\"6\" placeholder=\"图形验证码\" /><image class=\"captcha-row__image\" :src=\"bindCaptcha.image\" mode=\"aspectFill\" @click=\"loadCaptcha('bind')\" /></view>\n")
replace_once(
    "miniapp/src/components/login/MiniLoginAuthPanel.vue",
    "      bindForm: { tenantCode: '', loginName: '', password: '' },\n      bindLoading: false,\n",
    "      bindForm: { tenantCode: '', loginName: '', password: '' },\n"
    "      accountCaptcha: { required: false, id: '', code: '', image: '', nonce: `mini-account-${Date.now()}-${Math.random()}` },\n"
    "      bindCaptcha: { required: false, id: '', code: '', image: '', nonce: `mini-bind-${Date.now()}-${Math.random()}` },\n"
    "      bindLoading: false,\n",
)
replace_once(
    "miniapp/src/components/login/MiniLoginAuthPanel.vue",
    "  methods: {\n    assertEntryRole(data) {\n",
    "  methods: {\n"
    "    loadCaptcha(target) {\n"
    "      const box = target === 'bind' ? this.bindCaptcha : this.accountCaptcha\n"
    "      const form = target === 'bind' ? this.bindForm : this.account\n"
    "      const scene = target === 'bind' ? 'WX_BIND' : 'PASSWORD_LOGIN'\n"
    "      return realRequest('/auth/captcha', { method: 'POST', auth: false, data: { scene, tenantCode: form.tenantCode.trim() || undefined, loginName: form.loginName.trim(), clientNonce: box.nonce, clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI' } })\n"
    "        .then((d) => { box.id = d.captchaId; box.image = d.imageDataUrl; box.code = '' })\n"
    "        .catch((e) => toast(e?.message || '验证码加载失败'))\n"
    "    },\n"
    "    handleCaptchaError(error, target) {\n"
    "      if (!(String(error?.bizCode || '').startsWith('CAPTCHA_') || error?.details?.captchaRequired)) return false\n"
    "      const box = target === 'bind' ? this.bindCaptcha : this.accountCaptcha; box.required = true; this.loadCaptcha(target); return true\n"
    "    },\n"
    "    assertEntryRole(data) {\n",
)
replace_once(
    "miniapp/src/components/login/MiniLoginAuthPanel.vue",
    "          tenantCode: this.account.tenantCode.trim() || undefined\n",
    "          tenantCode: this.account.tenantCode.trim() || undefined,\n"
    "          clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI',\n"
    "          captchaId: this.accountCaptcha.id || undefined, captchaCode: this.accountCaptcha.code || undefined, clientNonce: this.accountCaptcha.nonce\n",
)
replace_once(
    "miniapp/src/components/login/MiniLoginAuthPanel.vue",
    "      }).then(this.completeLogin).catch((error) => toast(error?.message || '登录失败，请稍后重试')).finally(() => { this.accLoading = false })\n",
    "      }).then(this.completeLogin).catch((error) => { this.handleCaptchaError(error, 'account'); toast(error?.message || '登录失败，请稍后重试') }).finally(() => { this.accLoading = false })\n",
)
replace_once(
    "miniapp/src/components/login/MiniLoginAuthPanel.vue",
    "          password: this.bindForm.password\n",
    "          password: this.bindForm.password,\n"
    "          captchaId: this.bindCaptcha.id || undefined, captchaCode: this.bindCaptcha.code || undefined, clientNonce: this.bindCaptcha.nonce\n",
)
replace_once(
    "miniapp/src/components/login/MiniLoginAuthPanel.vue",
    "        .catch((error) => toast(error?.message || '绑定失败，请检查账号密码'))\n",
    "        .catch((error) => { this.handleCaptchaError(error, 'bind'); toast(error?.message || '绑定失败，请检查账号密码') })\n",
)
replace_once(
    "miniapp/src/components/login/MiniLoginAuthPanel.vue",
    "</style>\n",
    ".captcha-row { display: flex; align-items: center; gap: 16rpx; margin-top: 16rpx; }.captcha-row__input { flex: 1; margin: 0; }.captcha-row__image { width: 260rpx; height: 88rpx; border: 1rpx solid #dbe3ed; border-radius: 14rpx; background: #f8fafc; }\n</style>\n",
)

TESTS = r'''from __future__ import annotations

import base64

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.token_store import record_login_failure, reset_all_for_tests
from app.services import auth_challenge_service as svc


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "local")
    monkeypatch.setattr(settings, "REDIS_URL", "")
    reset_all_for_tests()
    svc.reset_for_tests()
    yield
    reset_all_for_tests()
    svc.reset_for_tests()


def test_captcha_is_raster_png_single_use():
    data = svc.issue_captcha(svc.PASSWORD_LOGIN, "school", "teacher", "nonce")
    raw = base64.b64decode(data["imageDataUrl"].split(",", 1)[1])
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    svc.verify_captcha(data["captchaId"], data["devCode"], svc.PASSWORD_LOGIN, "school", "teacher", "nonce")
    with pytest.raises(AppException) as replay:
        svc.verify_captcha(data["captchaId"], data["devCode"], svc.PASSWORD_LOGIN, "school", "teacher", "nonce")
    assert replay.value.biz_code == "CAPTCHA_EXPIRED"


def test_wrong_code_consumes_challenge():
    data = svc.issue_captcha(svc.WX_BIND, "school", "student", "nonce")
    with pytest.raises(AppException) as wrong:
        svc.verify_captcha(data["captchaId"], "000000", svc.WX_BIND, "school", "student", "nonce")
    assert wrong.value.biz_code == "CAPTCHA_INVALID"
    with pytest.raises(AppException):
        svc.verify_captcha(data["captchaId"], data["devCode"], svc.WX_BIND, "school", "student", "nonce")


def test_platform_always_requires_captcha():
    with pytest.raises(AppException) as exc:
        svc.enforce_login_captcha(svc.PLATFORM_LOGIN, "platform", "owner", None, None, "n")
    assert exc.value.biz_code == "CAPTCHA_REQUIRED"


def test_regular_login_becomes_adaptive_after_two_failures():
    key = svc.login_guard_key("school", "teacher")
    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")
    record_login_failure(key, threshold=5, lock_seconds=900)
    assert not svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")
    record_login_failure(key, threshold=5, lock_seconds=900)
    assert svc.captcha_required(svc.PASSWORD_LOGIN, "school", "teacher")


def test_guard_key_does_not_contain_account_plaintext():
    key = svc.login_guard_key("school-code", "teacher@example.com")
    assert "school-code" not in key
    assert "teacher@example.com" not in key
'''
write("backend/tests/test_auth_challenge_service.py", TESTS)

print("adaptive login captcha construction applied")
