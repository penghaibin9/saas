from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, got {count}: {pattern[:120]!r}")
    write(path, updated)


# Verification-code SMS is a frozen business boundary: it may only be introduced
# later for password recovery. Legacy guardian OTP login must not be reopenable by env.
guardian = "backend/app/student_portal/services/guardian_service.py"
for old in (
    "import hashlib\n",
    "import secrets\n",
    "from datetime import datetime, timedelta\n",
    "from app.core.config import settings\n",
    "from app.services.notification import sms_service\n",
    "from app.student_portal.services.parent_link_service import _phone_hash\n",
):
    text = read(guardian)
    if old in text:
        write(guardian, text.replace(old, "", 1))
replace_once(
    guardian,
    "from app.services.db_service import _mask_phone, _org_names, _tid\n",
    "from app.services.db_service import _org_names, _tid\n",
)
regex_once(
    guardian,
    r"OTP_TTL_MIN = 10.*?(?=def _require_guardian\()",
    '''_GUARDIAN_SMS_DISABLED = "家长短信验证码登录已停用；验证短信仅允许用于找回密码"


def request_otp(body: dict) -> dict:
    """Compatibility endpoint kept fail-closed; verification SMS is password-reset only."""
    del body
    raise AppException("NO_PERMISSION", _GUARDIAN_SMS_DISABLED)


def login(body: dict) -> dict:
    """Reject legacy or already-issued guardian OTPs as well as new login attempts."""
    del body
    raise AppException("NO_PERMISSION", _GUARDIAN_SMS_DISABLED)


''',
)

# Keep legacy HTTP paths returning the explicit policy error, but remove them from OpenAPI.
router = "backend/app/student_portal/router.py"
replace_once(
    router,
    '@router.post("/guardian/otp", summary="家长登录·请求验证码（公开）")\n',
    '@router.post("/guardian/otp", summary="家长短信验证码登录已停用", include_in_schema=False)\n',
)
replace_once(
    router,
    '@router.post("/guardian/login", summary="家长登录·手机号+验证码（公开，签发GUARDIAN令牌）")\n',
    '@router.post("/guardian/login", summary="家长短信验证码登录已停用", include_in_schema=False)\n',
)

# Remove the environment escape hatch: nobody can accidentally turn verification SMS login back on.
replace_once(
    "backend/app/core/config.py",
    "    GUARDIAN_SMS_LOGIN_ENABLED: bool = False  # 验证短信仅允许找回密码；家长短信登录默认永久关闭\n",
    "",
)

# Do not leave a dead public OTP form in the student portal; preserve old links with a safe redirect.
replace_once(
    "student-portal/src/router/index.js",
    "  { path: '/guardian', name: 'guardian', meta: { public: true }, component: () => import('../views/guardian/GuardianView.vue') },\n",
    "  { path: '/guardian', redirect: '/login' },\n",
)

# Regression proof: both issuing and consuming a legacy verification code remain blocked.
test_path = "backend/tests/test_auth_challenge_service.py"
test_text = read(test_path)
addition = '''\n\ndef test_guardian_verification_sms_login_is_permanently_disabled():\n    from app.student_portal.services import guardian_service\n\n    with pytest.raises(AppException) as issue_exc:\n        guardian_service.request_otp({"phone": "13800138000"})\n    assert issue_exc.value.code == "NO_PERMISSION"\n\n    with pytest.raises(AppException) as consume_exc:\n        guardian_service.login({"phone": "13800138000", "code": "123456"})\n    assert consume_exc.value.code == "NO_PERMISSION"\n    assert "找回密码" in consume_exc.value.message\n'''
if "test_guardian_verification_sms_login_is_permanently_disabled" in test_text:
    raise RuntimeError("guardian SMS regression test already present")
write(test_path, test_text.rstrip() + addition + "\n")

print("verification SMS policy hardened")
