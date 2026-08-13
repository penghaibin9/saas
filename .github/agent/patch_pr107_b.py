from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old, new, 1)


def replace_between(text, start, end, new, label):
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"{label}: start anchor missing")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"{label}: end anchor missing")
    return text[:a] + new + text[b:]


# backend/app/api/v1/auth_browser.py
p = "backend/app/api/v1/auth_browser.py"
t = read(p)
t = replace_once(t, "import secrets\nfrom contextvars import ContextVar\n", "import hashlib\nimport secrets\n", "auth imports")
t = replace_once(t, "from fastapi import APIRouter, Cookie, Depends, Header, Response\n", "from fastapi import APIRouter, Depends, Header, Request, Response\n", "request import")
t = replace_once(
    t,
    "    consume_refresh,\n    issue_refresh,\n    revoke_refresh_by_session,\n",
    "    consume_refresh,\n    consume_refresh_if_matches,\n    issue_refresh,\n",
    "token store imports",
)
t = replace_once(
    t,
    '''_COOKIE_NAMES = {
    "staff": "gx_staff_refresh_v1",
    "platform": "gx_platform_refresh_v1",
    "student": "gx_student_refresh_v1",
}
_BROWSER_REVOKE_SESSION = ContextVar("browser_revoke_session", default="")
''',
    '''_COOKIE_NAMES = {
    "staff": "gx_staff_refresh_v1",
    "platform": "gx_platform_refresh_v1",
    "student": "gx_student_refresh_v1",
}
_COOKIE_PREFIXES = {
    "staff": "gx_staff_refresh_v2_",
    "platform": "gx_platform_refresh_v2_",
    "student": "gx_student_refresh_v2_",
}
''',
    "cookie constants",
)
helpers = '''def _require_browser_session_id(value: str | None) -> str:
    session_id = str(value or "").strip()
    if not session_id or len(session_id) > 256:
        raise unauthorized("浏览器标签页会话无效，请重新登录")
    return session_id


def _browser_session_hash(session_id: str) -> str:
    return hashlib.sha256(_require_browser_session_id(session_id).encode("utf-8")).hexdigest()


def _cookie_name(channel: str, session_id: str) -> str:
    # Never paste caller-controlled header text into a cookie name.
    return f"{_COOKIE_PREFIXES[_normalize_channel(channel)]}{_browser_session_hash(session_id)[:24]}"


def _claims_match_browser_binding(claims: dict, channel: str, session_id: str) -> bool:
    return (
        str(claims.get("browserChannel") or "").strip().lower() == _normalize_channel(channel)
        and str(claims.get("browserSessionIdHash") or "") == _browser_session_hash(session_id)
    )


'''
marker = "def _channel_from_client_type(client_type: str | None) -> str:\n"
i = t.find(marker)
if i < 0:
    raise SystemExit("browser helper insertion marker missing")
t = t[:i] + helpers + t[i:]

cookie_block = '''def _set_refresh_cookie(response: Response, token: str, channel: str, browser_session_id: str) -> None:
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    response.set_cookie(
        key=_cookie_name(channel, tab_id),
        value=token,
        max_age=int(REFRESH_TTL),
        httponly=True,
        secure=bool(settings.is_prod),
        samesite="strict",
        path=_COOKIE_PATH,
    )
    # v1 is a shared surface slot: never guess-bind it to a v2 tab.
    for key in (_COOKIE_NAMES[channel], _LEGACY_COOKIE_NAME):
        response.delete_cookie(
            key=key, path=_COOKIE_PATH, httponly=True,
            secure=bool(settings.is_prod), samesite="strict",
        )


def _clear_refresh_cookie(response: Response, channel: str, browser_session_id: str) -> None:
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    for key in (_cookie_name(channel, tab_id), _COOKIE_NAMES[channel], _LEGACY_COOKIE_NAME):
        response.delete_cookie(
            key=key, path=_COOKIE_PATH, httponly=True,
            secure=bool(settings.is_prod), samesite="strict",
        )


'''
t = replace_between(t, "def _set_refresh_cookie(", "def _sessionize_payload(", cookie_block, "cookie helpers")

sessionize = '''def _sessionize_payload(
    payload: dict,
    *,
    browser_channel: str,
    browser_session_id: str,
    session_id: str | None = None,
) -> dict:
    """Bind a newly issued real DB browser credential pair to one concrete tab."""
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.get("refreshToken") or "")
    access_token = str(data.get("accessToken") or "")
    if not refresh_token or not access_token:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    try:
        access_claims = decode_token(access_token)
    except AppException:
        return payload
    if not str(access_claims.get("userId") or "").startswith("db-"):
        return payload
    claims = consume_refresh(refresh_token)
    if not claims:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    tab_id = _require_browser_session_id(browser_session_id)
    channel = _normalize_channel(browser_channel)
    sid = str(session_id or claims.get("authSessionId") or secrets.token_urlsafe(24))
    claims["authSessionId"] = sid
    claims["browserChannel"] = channel
    claims["browserSessionIdHash"] = _browser_session_hash(tab_id)
    data["accessToken"] = create_access_token(dict(claims))
    data["refreshToken"] = issue_refresh(dict(claims))
    out = dict(payload)
    out["data"] = data
    return out


'''
t = replace_between(t, "def _sessionize_payload(", "def _extract_refresh(", sessionize, "sessionize")

extract = '''def _extract_refresh(
    payload: dict,
    response: Response,
    *,
    expected_channel: str,
    browser_session_id: str,
) -> dict:
    """Move refreshToken into this tab's HttpOnly slot; accessToken remains memory-only."""
    data = dict((payload or {}).get("data") or {})
    refresh_token = str(data.pop("refreshToken", "") or "")
    access_token = str(data.get("accessToken") or "")
    if not refresh_token or not access_token:
        raise unauthorized("刷新令牌签发失败，请重新登录")
    channel = _normalize_channel(expected_channel)
    tab_id = _require_browser_session_id(browser_session_id)
    if _channel_from_access_token(access_token) != channel:
        try:
            consume_refresh(refresh_token)
        except Exception:
            pass
        _clear_refresh_cookie(response, channel, tab_id)
        raise unauthorized("该账号不属于当前登录入口，请使用正确入口重新登录")
    _set_refresh_cookie(response, refresh_token, channel, tab_id)
    out = dict(payload)
    out["data"] = data
    return out


'''
t = replace_between(t, "def _extract_refresh(", "def _rotate_browser_refresh(", extract, "extract refresh")

rotate = '''def _rotate_browser_refresh(refresh_token: str, *, channel: str, browser_session_id: str) -> dict:
    """Atomically rotate only a refresh credential bound to this exact browser tab."""
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    claims = consume_refresh_if_matches(
        refresh_token,
        expected_browser_channel=channel,
        expected_browser_session_hash=_browser_session_hash(tab_id),
    )
    if not claims:
        raise unauthorized("浏览器刷新会话无效，请重新登录")
    session_id = str(claims.get("authSessionId") or "")
    if session_id and auth_session_blocked(session_id):
        raise unauthorized("浏览器会话已失效，请重新登录")
    auth_service_db.validate_token_subject(claims)
    claims["authSessionId"] = session_id or secrets.token_urlsafe(24)
    claims["browserChannel"] = channel
    claims["browserSessionIdHash"] = _browser_session_hash(tab_id)
    token = create_access_token(dict(claims))
    new_refresh = issue_refresh(dict(claims))
    audit.record("TOKEN_REFRESH", target_type="auth", target_id=str(claims.get("userId", "-")))
    return success({
        "accessToken": token,
        "refreshToken": new_refresh,
        "tokenType": "Bearer",
        "expiresIn": settings.JWT_EXPIRES_IN,
    }, message="已刷新")


'''
t = replace_between(t, "def _rotate_browser_refresh(", '@router.post("/auth/browser-login"', rotate, "rotate refresh")

endpoints = '''@router.post("/auth/browser-login", summary="浏览器账号密码登录（per-tab HttpOnly refresh Cookie）")
def browser_login(
    body: auth_api.PasswordLoginRequest,
    response: Response,
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    channel = _channel_from_client_type(body.clientType)
    tab_id = _require_browser_session_id(browser_session_id)
    payload = _sessionize_payload(
        auth_api.login(body), browser_channel=channel, browser_session_id=tab_id,
    )
    return _extract_refresh(payload, response, expected_channel=channel, browser_session_id=tab_id)


@router.post("/auth/browser-refresh", summary="浏览器刷新会话（同 surface 多标签页隔离）")
def browser_refresh(
    request: Request,
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    channel = _normalize_channel(browser_session)
    tab_id = _require_browser_session_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(channel, tab_id))
    if not refresh_token:
        raise unauthorized("浏览器刷新会话不存在，请重新登录")
    payload = _rotate_browser_refresh(refresh_token, channel=channel, browser_session_id=tab_id)
    return _extract_refresh(payload, response, expected_channel=channel, browser_session_id=tab_id)


@router.post("/auth/browser-switch-role", summary="浏览器切换身份并轮换当前标签页 refreshToken")
def browser_switch_role(
    body: SwitchRoleRequest,
    response: Response,
    user=Depends(get_current_user),
    authorization: str | None = Header(default=None),
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
):
    channel = _normalize_channel(browser_session)
    tab_id = _require_browser_session_id(browser_session_id)
    raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
    access_claims = decode_token(raw) if raw else {}
    if str(user.get("userId") or "").startswith("db-") and not _claims_match_browser_binding(access_claims, channel, tab_id):
        raise unauthorized("浏览器标签页会话不匹配，请重新登录")
    session_id = str(access_claims.get("authSessionId") or "")
    if str(user.get("userId") or "").startswith("db-"):
        result = browser_auth_session_service.switch_role(
            user, body.contextId, body.clientType, auth_session_id=session_id,
        )
        audit.record(
            "切换身份", method="POST", path="/api/v1/auth/browser-switch-role",
            status_code=200, target_type="authz", target_id=body.contextId,
        )
        payload = success(result, message="身份切换成功")
    else:
        payload = auth_api.switch_role(body, user)
    payload = _sessionize_payload(payload, browser_channel=channel, browser_session_id=tab_id)
    return _extract_refresh(payload, response, expected_channel=channel, browser_session_id=tab_id)


'''
t = replace_between(t, '@router.post("/auth/browser-login"', "def revoke_refresh_by_user(", endpoints, "browser endpoints")
cut = t.find("def revoke_refresh_by_user(")
if cut < 0:
    raise SystemExit("logout start missing")
logout = '''def _browser_logout(
    *,
    response: Response,
    channel: str,
    browser_session_id: str,
    refresh_token: str | None,
    authorization: str | None,
):
    """Terminate one browser tab without revoking another tab/device for the same user."""
    channel = _normalize_channel(channel)
    tab_id = _require_browser_session_id(browser_session_id)
    _clear_refresh_cookie(response, channel, tab_id)
    user_ids: set[str] = set()
    try:
        if refresh_token:
            refresh_claims = consume_refresh_if_matches(
                refresh_token,
                expected_browser_channel=channel,
                expected_browser_session_hash=_browser_session_hash(tab_id),
            )
            if not refresh_claims:
                raise unauthorized("浏览器标签页会话不匹配，请重新登录")
            refresh_user = str(refresh_claims.get("userId") or "")
            refresh_session = str(refresh_claims.get("authSessionId") or "")
            if refresh_user:
                user_ids.add(refresh_user)
            if refresh_session:
                block_auth_session(refresh_session)
        raw = (authorization or "")[7:].strip() if (authorization or "").startswith("Bearer ") else (authorization or "").strip()
        if raw:
            try:
                access_claims = decode_token(raw)
            except AppException:
                access_claims = _decode_signed_token_for_revocation(raw)
            if access_claims:
                if str(access_claims.get("userId") or "").startswith("db-") and not _claims_match_browser_binding(access_claims, channel, tab_id):
                    raise unauthorized("浏览器标签页会话不匹配，请重新登录")
                access_user = str(access_claims.get("userId") or "")
                access_session = str(access_claims.get("authSessionId") or "")
                if access_user:
                    user_ids.add(access_user)
                if access_session:
                    block_auth_session(access_session)
                jti = str(access_claims.get("jti") or "")
                if jti:
                    block_jti(jti, float(access_claims.get("exp") or 0) or None)
    except AppException as exc:
        response.status_code = int(exc.http_status)
        return fail(exc.code, exc.message, exc.details)
    audit.record(
        "登出", method="POST", path="/api/v1/auth/browser-logout", status_code=200,
        target_type="auth", target_id=",".join(sorted(user_ids)) or "-",
    )
    return success({"invalidated": True}, message="已登出")


@router.post("/auth/browser-logout", summary="浏览器登出并清除当前标签页 HttpOnly refreshToken")
def browser_logout(
    request: Request,
    response: Response,
    browser_session: str | None = Header(default=None, alias="X-Browser-Session"),
    browser_session_id: str | None = Header(default=None, alias="X-Browser-Session-Id"),
    authorization: str | None = Header(default=None),
):
    channel = _normalize_channel(browser_session)
    tab_id = _require_browser_session_id(browser_session_id)
    refresh_token = request.cookies.get(_cookie_name(channel, tab_id))
    return _browser_logout(
        response=response, channel=channel, browser_session_id=tab_id,
        refresh_token=refresh_token, authorization=authorization,
    )
'''
t = t[:cut] + logout
write(p, t)

# token_store atomic binding-aware consume
p = "backend/app/core/token_store.py"
t = read(p)
anchor = "\ndef _consume_refresh_memory(token: str) -> dict | None:\n"
if anchor not in t:
    raise SystemExit("token store anchor missing")
matcher = r'''
def consume_refresh_if_matches(
    token: str,
    *,
    expected_browser_channel: str,
    expected_browser_session_hash: str,
) -> dict | None:
    """Consume only after browser-tab binding matches; mismatch leaves the credential untouched."""
    from app.core.config import settings
    from app.core.exceptions import AppException
    from app.db.session import db_enabled
    channel = str(expected_browser_channel or "").strip().lower()
    session_hash = str(expected_browser_session_hash or "").strip()
    if not channel or not session_hash:
        return None
    must_persist = settings.is_prod or db_enabled()
    db = _db(required=must_persist)
    if db is not None:
        try:
            from sqlalchemy import delete, select
            from app.models import AuthRefreshToken
            h = _tok_hash(token or "")
            row = db.scalars(
                select(AuthRefreshToken).where(AuthRefreshToken.token_hash == h).with_for_update()
            ).first()
            if row is None:
                if not must_persist:
                    return _consume_refresh_memory_if_matches(
                        token,
                        expected_browser_channel=channel,
                        expected_browser_session_hash=session_hash,
                    )
                return None
            claims = dict(row.claims_json or {})
            if (
                str(claims.get("browserChannel") or "").strip().lower() != channel
                or str(claims.get("browserSessionIdHash") or "") != session_hash
            ):
                db.rollback()
                return None
            expired = row.expires_at < datetime.utcnow()
            res = db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.token_hash == h))
            db.commit()
            if expired or (res.rowcount or 0) == 0:
                return None
            return claims
        except AppException:
            raise
        except Exception as e:  # noqa: BLE001
            try:
                db.rollback()
            except Exception:
                pass
            if must_persist:
                raise AppException("AUTH_STORE_UNAVAILABLE", "认证存储暂时不可用", http_status=503) from e
            return _consume_refresh_memory_if_matches(
                token,
                expected_browser_channel=channel,
                expected_browser_session_hash=session_hash,
            )
        finally:
            db.close()
    return _consume_refresh_memory_if_matches(
        token,
        expected_browser_channel=channel,
        expected_browser_session_hash=session_hash,
    )


def _consume_refresh_memory_if_matches(
    token: str,
    *,
    expected_browser_channel: str,
    expected_browser_session_hash: str,
) -> dict | None:
    item = _refresh.get(token or "")
    if not item:
        return None
    if item["exp"] < _now():
        _refresh.pop(token or "", None)
        return None
    claims = dict(item["claims"] or {})
    if (
        str(claims.get("browserChannel") or "").strip().lower() != str(expected_browser_channel or "").strip().lower()
        or str(claims.get("browserSessionIdHash") or "") != str(expected_browser_session_hash or "")
    ):
        return None
    _refresh.pop(token or "", None)
    return claims

'''
t = t.replace(anchor, "\n" + matcher + anchor.lstrip("\n"), 1)
write(p, t)

# teacher PC per-tab nonsecret browser session id
p = "frontend/src/services/http/client.js"
t = read(p)
t = replace_once(
    t,
    "const LEGACY_TOKEN_KEYS = ['gx_pc_token_v1', 'gx_pc_refresh_v1']\n",
    "const LEGACY_TOKEN_KEYS = ['gx_pc_token_v1', 'gx_pc_refresh_v1']\nconst BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'\nlet volatileBrowserSessionId = ''\n",
    "teacher sid constant",
)
helper = '''function getOrCreateBrowserSessionId() {
  try {
    const existing = String(sessionStorage.getItem(BROWSER_SESSION_ID_KEY) || '').trim()
    if (existing) return existing
    const generated = globalThis.crypto?.randomUUID?.()
    if (!generated) throw new Error('secure random UUID unavailable')
    sessionStorage.setItem(BROWSER_SESSION_ID_KEY, generated)
    return generated
  } catch {
    if (!volatileBrowserSessionId) volatileBrowserSessionId = globalThis.crypto?.randomUUID?.() || `tab-${Date.now()}-${Math.random()}`
    return volatileBrowserSessionId
  }
}

'''
i = t.find("function browserSessionChannel() {\n")
if i < 0:
    raise SystemExit("teacher helper marker missing")
t = t[:i] + helper + t[i:]
t = replace_once(
    t,
    "function browserSessionHeaders() {\n  return { 'X-Browser-Session': browserSessionChannel() }\n}\n",
    "function browserSessionHeaders() {\n  return {\n    'X-Browser-Session': browserSessionChannel(),\n    'X-Browser-Session-Id': getOrCreateBrowserSessionId()\n  }\n}\n",
    "teacher headers",
)
t = replace_once(t, "      method: 'POST',\n      body: { contextId, clientType }\n", "      method: 'POST',\n      body: { contextId, clientType },\n      headers: browserSessionHeaders()\n", "teacher switch headers")
t = replace_once(t, "    forceProbe: true,\n    body: { loginName, password, tenantCode: tenantCode || undefined,\n", "    forceProbe: true,\n    headers: browserSessionHeaders(),\n    body: { loginName, password, tenantCode: tenantCode || undefined,\n", "teacher login headers")
write(p, t)

# student PC per-tab browser session id
p = "student-portal/src/services/request.js"
t = read(p)
t = replace_once(t, "const API_PREFIX = '/api/v1'\nconst BROWSER_SESSION_HEADERS = { 'X-Browser-Session': 'student' }\n", "const API_PREFIX = '/api/v1'\nconst BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'\nlet volatileBrowserSessionId = ''\n", "student sid constant")
helper = '''function getOrCreateBrowserSessionId() {
  try {
    const existing = String(sessionStorage.getItem(BROWSER_SESSION_ID_KEY) || '').trim()
    if (existing) return existing
    const generated = globalThis.crypto?.randomUUID?.()
    if (!generated) throw new Error('secure random UUID unavailable')
    sessionStorage.setItem(BROWSER_SESSION_ID_KEY, generated)
    return generated
  } catch {
    if (!volatileBrowserSessionId) volatileBrowserSessionId = globalThis.crypto?.randomUUID?.() || `tab-${Date.now()}-${Math.random()}`
    return volatileBrowserSessionId
  }
}

function browserSessionHeaders() {
  return {
    'X-Browser-Session': 'student',
    'X-Browser-Session-Id': getOrCreateBrowserSessionId()
  }
}

'''
i = t.find("function _replaceAccessToken(token) {\n")
if i < 0:
    raise SystemExit("student helper marker missing")
t = t[:i] + helper + t[i:]
t = replace_once(
    t,
    '''function addBrowserSessionHeader(headers, path) {
  if (String(path || '').startsWith('/auth/browser-')) {
    headers['X-Browser-Session'] = BROWSER_SESSION_HEADERS['X-Browser-Session']
  }
}
''',
    '''function addBrowserSessionHeader(headers, path) {
  const value = String(path || '')
  if (value === '/auth/login' || value.startsWith('/auth/browser-')) {
    Object.assign(headers, browserSessionHeaders())
  }
}
''',
    "student browser header helper",
)
t = replace_once(t, "        headers: { 'Content-Type': 'application/json', ...BROWSER_SESSION_HEADERS },\n", "        headers: { 'Content-Type': 'application/json', ...browserSessionHeaders() },\n", "student refresh headers")
write(p, t)

# Adjust existing production truth contracts to v2 semantics.
p = "backend/tests/test_production_truth_hardening.py"
t = read(p)
start = "def test_browser_session_cookie_names_are_isolated_per_pc_surface():\n"
end = "def test_python_freeze_contract_is_self_consistent():\n"
adapted = '''def test_browser_session_cookie_names_are_isolated_per_pc_surface():
    assert auth_browser._COOKIE_PREFIXES == {
        "staff": "gx_staff_refresh_v2_",
        "platform": "gx_platform_refresh_v2_",
        "student": "gx_student_refresh_v2_",
    }
    assert len(set(auth_browser._COOKIE_PREFIXES.values())) == 3
    assert auth_browser._cookie_name("staff", "tab-a") != auth_browser._cookie_name("staff", "tab-b")


def test_browser_login_moves_refresh_token_to_tab_specific_httponly_cookie(monkeypatch):
    monkeypatch.setattr(auth_browser.auth_api, "login", lambda body: {
        "code": 0, "message": "ok",
        "data": {"accessToken": "access-visible", "refreshToken": "refresh-secret"},
    })
    monkeypatch.setattr(auth_browser, "_sessionize_payload", lambda payload, **kwargs: payload)
    monkeypatch.setattr(auth_browser, "_channel_from_access_token", lambda token: "student")
    response = Response()
    payload = auth_browser.browser_login(
        auth_browser.auth_api.PasswordLoginRequest(loginName="student", password="secret", clientType="STUDENT_PC"),
        response, "tab-student-a",
    )
    assert payload["data"] == {"accessToken": "access-visible"}
    cookies = "\\n".join(response.headers.getlist("set-cookie")).lower()
    expected = auth_browser._cookie_name("student", "tab-student-a").lower()
    assert f"{expected}=refresh-secret" in cookies
    assert "gx_student_refresh_v1=refresh-secret" not in cookies
    assert "httponly" in cookies and "samesite=strict" in cookies and "path=/api/v1/auth" in cookies


def test_browser_logout_terminates_only_current_bound_refresh(monkeypatch):
    blocked = []
    monkeypatch.setattr(auth_browser, "consume_refresh_if_matches", lambda token, **kwargs: {
        "userId": "db-student-1", "authSessionId": "auth-session-a",
        "browserChannel": "student", "browserSessionIdHash": auth_browser._browser_session_hash("tab-a"),
    })
    monkeypatch.setattr(auth_browser, "block_auth_session", blocked.append)
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    response = Response()
    payload = auth_browser._browser_logout(
        response=response, channel="student", browser_session_id="tab-a",
        refresh_token="durable-cookie-token", authorization=None,
    )
    assert payload["code"] == 0 and payload["data"]["invalidated"] is True
    assert blocked == ["auth-session-a"]
    cookies = "\\n".join(response.headers.getlist("set-cookie")).lower()
    assert auth_browser._cookie_name("student", "tab-a").lower() in cookies
    assert "max-age=0" in cookies


def test_browser_logout_blacklists_live_access_jti_for_same_tab(monkeypatch):
    blocked_jti, blocked_sessions = [], []
    sid = "tab-a"
    monkeypatch.setattr(auth_browser, "decode_token", lambda token: {
        "userId": "db-student-1", "jti": "access-jti-1", "exp": 4102444800,
        "authSessionId": "auth-session-a", "browserChannel": "student",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid),
    })
    monkeypatch.setattr(auth_browser, "block_jti", lambda jti, exp: blocked_jti.append((jti, exp)) or True)
    monkeypatch.setattr(auth_browser, "block_auth_session", blocked_sessions.append)
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    payload = auth_browser._browser_logout(
        response=Response(), channel="student", browser_session_id=sid,
        refresh_token=None, authorization="Bearer live-access-token",
    )
    assert payload["code"] == 0
    assert blocked_jti == [("access-jti-1", 4102444800.0)]
    assert blocked_sessions == ["auth-session-a"]


def test_pc_browser_clients_persist_only_nonsecret_per_tab_session_id():
    admin = (ROOT / "frontend/src/services/http/client.js").read_text(encoding="utf-8")
    portal = (ROOT / "student-portal/src/services/request.js").read_text(encoding="utf-8")
    portal_session = (ROOT / "student-portal/src/stores/session.js").read_text(encoding="utf-8")
    assert "const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'" in admin
    assert "sessionStorage.setItem(BROWSER_SESSION_ID_KEY" in admin
    assert "'X-Browser-Session-Id': getOrCreateBrowserSessionId()" in admin
    assert "state.refreshToken" not in admin
    assert "_sessionSet(TOKEN_KEY" not in portal and "_sessionSet(REFRESH_KEY" not in portal
    assert "const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'" in portal
    assert "sessionStorage.setItem(BROWSER_SESSION_ID_KEY" in portal
    assert "'X-Browser-Session-Id': getOrCreateBrowserSessionId()" in portal
    assert "let accessToken = ''" in portal and "clientType: 'STUDENT_PC'" in portal
    assert "/auth/browser-refresh" in portal and "/auth/browser-login" in portal
    assert "await request('/auth/browser-logout', { method: 'POST', auth: true })" in portal_session


'''
t = replace_between(t, start, end, adapted, "production browser tests")
write(p, t)

# Extend static PC contracts.
p = "frontend/tests/auth-session-race-contract.test.mjs"
t = read(p) + r'''

test('browser refresh is bound to a nonsecret per-tab session id', async () => {
  const source = await readFile(clientUrl, 'utf8')
  assert.match(source, /const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'/)
  assert.match(source, /sessionStorage\.getItem\(BROWSER_SESSION_ID_KEY\)/)
  assert.match(source, /sessionStorage\.setItem\(BROWSER_SESSION_ID_KEY, generated\)/)
  assert.doesNotMatch(source, /localStorage\.setItem\(BROWSER_SESSION_ID_KEY/)
  assert.match(source, /'X-Browser-Session-Id': getOrCreateBrowserSessionId\(\)/)
  assert.match(source, /loginWithPassword[\s\S]*?headers: browserSessionHeaders\(\)/)
  assert.match(source, /switchAuthContext[\s\S]*?headers: browserSessionHeaders\(\)/)
  assert.match(source, /logoutRemote[\s\S]*?headers: browserSessionHeaders\(\)/)
})
'''
write(p, t)

p = "frontend/tests/student-portal-auth-session-race-contract.test.mjs"
t = read(p) + r'''

test('student portal browser auth binds HttpOnly refresh to this tab id only', async () => {
  const text = await source()
  assert.match(text, /const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'/)
  assert.match(text, /sessionStorage\.getItem\(BROWSER_SESSION_ID_KEY\)/)
  assert.match(text, /sessionStorage\.setItem\(BROWSER_SESSION_ID_KEY, generated\)/)
  assert.doesNotMatch(text, /localStorage\.setItem\(BROWSER_SESSION_ID_KEY/)
  assert.match(text, /'X-Browser-Session-Id': getOrCreateBrowserSessionId\(\)/)
  assert.match(text, /value === '\/auth\/login' \|\| value\.startsWith\('\/auth\/browser-'\)/)
  assert.match(text, /\.\.\.browserSessionHeaders\(\)/)
})
'''
write(p, t)

# New backend browser tab contract.
write("backend/tests/test_browser_session_tab_isolation.py", r'''from __future__ import annotations

import inspect

from fastapi import Response
from starlette.requests import Request

from app.api.v1 import auth_browser
from app.core import token_store
from app.core.exceptions import AppException


def _request(cookies: dict[str, str] | None = None) -> Request:
    raw = "; ".join(f"{k}={v}" for k, v in (cookies or {}).items()).encode()
    headers = [(b"cookie", raw)] if raw else []
    return Request({
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": "https",
        "path": "/api/v1/auth/browser-refresh", "raw_path": b"/api/v1/auth/browser-refresh",
        "query_string": b"", "headers": headers, "client": ("127.0.0.1", 12345),
        "server": ("example.test", 443),
    })


def test_browser_login_sets_session_specific_cookie_slot(monkeypatch):
    monkeypatch.setattr(auth_browser.auth_api, "login", lambda body: {
        "code": 0, "message": "ok", "data": {"accessToken": "access", "refreshToken": "refresh-a"},
    })
    monkeypatch.setattr(auth_browser, "_sessionize_payload", lambda payload, **kwargs: payload)
    monkeypatch.setattr(auth_browser, "_channel_from_access_token", lambda token: "staff")
    response = Response()
    auth_browser.browser_login(
        auth_browser.auth_api.PasswordLoginRequest(loginName="teacher", password="secret", clientType="PC"),
        response, "tab-a",
    )
    cookies = "\n".join(response.headers.getlist("set-cookie"))
    assert f"{auth_browser._cookie_name('staff', 'tab-a')}=refresh-a" in cookies
    assert auth_browser._cookie_name("staff", "tab-b") not in cookies


def test_browser_refresh_rejects_missing_session_id():
    try:
        auth_browser.browser_refresh(_request(), Response(), browser_session="staff", browser_session_id=None)
    except AppException as exc:
        assert exc.http_status == 401
    else:
        raise AssertionError("missing X-Browser-Session-Id must fail")


def test_browser_refresh_rejects_other_session_cookie_without_consuming_it(monkeypatch):
    called = []
    monkeypatch.setattr(auth_browser, "consume_refresh_if_matches", lambda *args, **kwargs: called.append(1) or None)
    cookies = {auth_browser._cookie_name("staff", "tab-b"): "refresh-b"}
    try:
        auth_browser.browser_refresh(_request(cookies), Response(), browser_session="staff", browser_session_id="tab-a")
    except AppException as exc:
        assert exc.http_status == 401
    else:
        raise AssertionError("other tab cookie must fail")
    assert called == []


def test_atomic_match_mismatch_does_not_burn_refresh_token():
    token_store._refresh.clear()
    claims = {"userId": "db-1", "browserChannel": "staff", "browserSessionIdHash": "hash-a"}
    token = token_store.issue_refresh(dict(claims))
    assert token_store.consume_refresh_if_matches(
        token, expected_browser_channel="staff", expected_browser_session_hash="hash-b",
    ) is None
    assert token in token_store._refresh
    assert token_store.consume_refresh_if_matches(
        token, expected_browser_channel="staff", expected_browser_session_hash="hash-a",
    ) == claims
    assert token not in token_store._refresh


def test_browser_logout_consumes_only_current_session_refresh(monkeypatch):
    token_store._refresh.clear()
    sid_a, sid_b = "tab-a", "tab-b"
    token_a = token_store.issue_refresh({
        "userId": "db-1", "authSessionId": "auth-a", "browserChannel": "staff",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid_a),
    })
    token_b = token_store.issue_refresh({
        "userId": "db-1", "authSessionId": "auth-b", "browserChannel": "staff",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid_b),
    })
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_browser, "block_auth_session", lambda *args, **kwargs: None)
    result = auth_browser._browser_logout(
        response=Response(), channel="staff", browser_session_id=sid_a,
        refresh_token=token_a, authorization=None,
    )
    assert result["code"] == 0
    assert token_a not in token_store._refresh and token_b in token_store._refresh
    assert token_store.consume_refresh_if_matches(
        token_b, expected_browser_channel="staff",
        expected_browser_session_hash=auth_browser._browser_session_hash(sid_b),
    ) is not None


def test_browser_logout_does_not_revoke_other_same_user_session():
    assert not hasattr(auth_browser, "_BROWSER_REVOKE_SESSION")
    assert "revoke_refresh_by_user" not in auth_browser._browser_logout.__code__.co_names


def test_browser_switch_role_rotates_only_current_session_slot(monkeypatch):
    sid = "tab-a"
    monkeypatch.setattr(auth_browser, "decode_token", lambda token: {
        "userId": "db-1", "authSessionId": "old-auth-session", "browserChannel": "staff",
        "browserSessionIdHash": auth_browser._browser_session_hash(sid),
    })
    monkeypatch.setattr(auth_browser.browser_auth_session_service, "switch_role", lambda *args, **kwargs: {
        "accessToken": "new-access", "refreshToken": "new-refresh",
    })
    monkeypatch.setattr(auth_browser, "_sessionize_payload", lambda payload, **kwargs: payload)
    monkeypatch.setattr(auth_browser, "_channel_from_access_token", lambda token: "staff")
    monkeypatch.setattr(auth_browser.audit, "record", lambda *args, **kwargs: None)
    response = Response()
    result = auth_browser.browser_switch_role(
        auth_browser.SwitchRoleRequest(contextId="ctx-2", clientType="PC"), response,
        user={"userId": "db-1"}, authorization="Bearer old-access",
        browser_session="staff", browser_session_id=sid,
    )
    assert result["code"] == 0
    cookies = "\n".join(response.headers.getlist("set-cookie"))
    assert f"{auth_browser._cookie_name('staff', sid)}=new-refresh" in cookies
    assert auth_browser._cookie_name("staff", "tab-b") not in cookies


def test_staff_student_platform_slots_remain_isolated():
    sid = "same-tab-label"
    assert len({
        auth_browser._cookie_name("staff", sid),
        auth_browser._cookie_name("student", sid),
        auth_browser._cookie_name("platform", sid),
    }) == 3


def test_token_store_db_match_uses_row_lock_before_delete():
    source = inspect.getsource(token_store.consume_refresh_if_matches)
    assert ".with_for_update()" in source
    assert source.index("browserSessionIdHash") < source.index("delete(AuthRefreshToken)")
''')

# E2E helper now resolves the tab's dynamic cookie name.
p = "e2e/pages/login.page.mjs"
t = read(p)
t = replace_once(t, "import { expect } from '../lib/observability.mjs'\n", "import { createHash } from 'node:crypto'\nimport { expect } from '../lib/observability.mjs'\n", "e2e crypto import")
t = replace_once(
    t,
    '''async function browserRefreshCookie(page, channel = 'staff') {
  const name = `gx_${channel}_refresh_v1`
  const cookies = await page.context().cookies()
  return String(cookies.find((cookie) => cookie.name === name)?.value || '')
}
''',
    '''async function browserRefreshCookie(page, channel = 'staff') {
  const sessionId = await page.evaluate(() => String(sessionStorage.getItem('gx_browser_session_id_v2') || ''))
  if (!sessionId) return ''
  const suffix = createHash('sha256').update(sessionId).digest('hex').slice(0, 24)
  const name = `gx_${channel}_refresh_v2_${suffix}`
  const cookies = await page.context().cookies()
  return String(cookies.find((cookie) => cookie.name === name)?.value || '')
}
''',
    "e2e cookie helper",
)
write(p, t)

write("e2e/specs/auth-browser-multi-tab-isolation.spec.mjs", r'''import { test, expect, attachObservability } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, decodeJwt } from '../pages/login.page.mjs'

async function tabSessionId(page) {
  return page.evaluate(() => String(sessionStorage.getItem('gx_browser_session_id_v2') || ''))
}

async function reloadAndWaitForRefresh(page) {
  const refresh = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-refresh') && response.request().method() === 'POST'
  )
  await page.reload()
  const response = await refresh
  expect(response.status()).toBe(200)
}

test.describe.serial('same-context browser tab auth isolation', () => {
  test('two staff accounts in one browser context keep independent refresh sessions', async ({ browser }, testInfo) => {
    const context = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '10.254.0.41' } })
    const pageA = await context.newPage()
    const pageB = await context.newPage()
    const finalizeA = await attachObservability(pageA, testInfo, { label: 'same-context-staff-a' })
    const finalizeB = await attachObservability(pageB, testInfo, { label: 'same-context-staff-b' })
    try {
      const loginA = new StaffLoginPage(pageA, config.staffBaseUrl)
      const loginB = new StaffLoginPage(pageB, config.staffBaseUrl)
      await loginA.login(config.sandboxAdmin)
      const tokenA = await loginA.token()
      await loginB.login(config.demoAdmin)
      const tokenB = await loginB.token()
      const claimsA = decodeJwt(tokenA)
      const claimsB = decodeJwt(tokenB)
      expect(String(claimsA.userId || '')).not.toBe(String(claimsB.userId || ''))
      expect(String(claimsA.tenantId || '')).not.toBe(String(claimsB.tenantId || ''))
      const sidA = await tabSessionId(pageA)
      const sidB = await tabSessionId(pageB)
      expect(sidA).toBeTruthy()
      expect(sidB).toBeTruthy()
      expect(sidA).not.toBe(sidB)
      await reloadAndWaitForRefresh(pageA)
      await expect(pageA.locator('body')).toContainText(/体验沙箱|sandbox-school/)
      await reloadAndWaitForRefresh(pageB)
      await expect(pageB.locator('body')).toContainText(/演示职业技术学校|demo-school/)
      const logout = await pageA.evaluate(async ({ apiBaseUrl, sid }) => {
        const response = await fetch(`${apiBaseUrl}/auth/browser-logout`, {
          method: 'POST', credentials: 'include',
          headers: { 'X-Browser-Session': 'staff', 'X-Browser-Session-Id': sid }
        })
        return { status: response.status, body: await response.json() }
      }, { apiBaseUrl: config.apiBaseUrl, sid: sidA })
      expect(logout.status, JSON.stringify(logout.body)).toBe(200)
      expect(logout.body?.code, JSON.stringify(logout.body)).toBe(0)
      await reloadAndWaitForRefresh(pageB)
      await expect(pageB.locator('body')).toContainText(/演示职业技术学校|demo-school/)
    } finally {
      await finalizeA(); await finalizeB(); await context.close()
    }
  })

  test('same user can hold different roles in two tabs without cross-rotation', async ({ browser }, testInfo) => {
    const context = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '10.254.0.42' } })
    const pageA = await context.newPage()
    const pageB = await context.newPage()
    const finalizeA = await attachObservability(pageA, testInfo, { label: 'same-user-role-a' })
    const finalizeB = await attachObservability(pageB, testInfo, { label: 'same-user-role-b' })
    try {
      const loginA = new StaffLoginPage(pageA, config.staffBaseUrl)
      const loginB = new StaffLoginPage(pageB, config.staffBaseUrl)
      await loginA.login(config.multiRole)
      await loginB.login(config.multiRole)
      expect(await tabSessionId(pageA)).not.toBe(await tabSessionId(pageB))
      await loginA.switchRole(/毕设管理员|GRADUATION_ADMIN/)
      await loginB.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
      await expect.poll(() => loginA.currentRoleText()).toMatch(/毕设管理员|GRADUATION_ADMIN/)
      await expect.poll(() => loginB.currentRoleText()).toMatch(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
      await reloadAndWaitForRefresh(pageA)
      await reloadAndWaitForRefresh(pageB)
      await expect.poll(() => loginA.currentRoleText()).toMatch(/毕设管理员|GRADUATION_ADMIN/)
      await expect.poll(() => loginB.currentRoleText()).toMatch(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
    } finally {
      await finalizeA(); await finalizeB(); await context.close()
    }
  })
})
''')

for name, source in (
    ("teacher", read("frontend/src/services/http/client.js")),
    ("student", read("student-portal/src/services/request.js")),
):
    if "localStorage.setItem(BROWSER_SESSION_ID_KEY" in source:
        raise SystemExit(f"{name}: browser tab id must remain sessionStorage-only")
