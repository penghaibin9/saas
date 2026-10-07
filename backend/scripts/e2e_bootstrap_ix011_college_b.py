"""Provision and normalize the IX-011 cross-college reviewer in isolated E2E."""
from __future__ import annotations

import contextlib
import io
import os
import secrets
import sys
import urllib.parse
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.identity_import_file_service import build_teacher_template  # noqa: E402
from scripts.e2e_bootstrap_graduation_accounts import _req, login  # noqa: E402
from scripts.e2e_bootstrap_graduation_accounts_ci import (  # noqa: E402
    _canonical_import,
    _workbook_with_rows,
)
from scripts.e2e_reset_graduation_passwords import _find_user  # noqa: E402

LOGIN = "e2e_ix_college_b"
COLLEGE = "E2E岗位实习测试信息工程学院"
BASE = os.getenv("E2E_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")


def _require_isolated_target() -> Path:
    if (os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS", "").lower() != "true"
            or os.getenv("APP_ENV", "").lower() != "test"
            or os.getenv("DEPLOYMENT_MODE", "").lower() != "local"
            or os.getenv("MOCK_LOGIN_ENABLED", "").lower() != "false"):
        raise RuntimeError("requires real-login isolated E2E mode")
    database = urlsplit(os.getenv("DATABASE_URL", ""))
    api = urlsplit(BASE)
    in_actions = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
    db_port, api_port = (3306, 8000) if in_actions else (3311, 8002)
    db_name = urllib.parse.unquote(database.path.lstrip("/")).lower()
    if (database.scheme not in {"mysql", "mysql+pymysql"}
            or database.hostname not in {"127.0.0.1", "localhost"}
            or database.port != db_port
            or not ("e2e" in db_name or "test" in db_name)
            or any(x in db_name for x in ("prod", "production", "staging"))):
        raise RuntimeError("database is not the expected isolated E2E target")
    if (api.scheme != "http" or api.hostname not in {"127.0.0.1", "localhost"}
            or api.port != api_port or not api.path.rstrip("/").endswith("/api/v1")):
        raise RuntimeError("API is not the expected local E2E target")
    env_file = os.getenv("GITHUB_ENV")
    if not env_file:
        raise RuntimeError("GITHUB_ENV is required for safe password handoff")
    path = Path(env_file).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8"):
        pass
    return path


def _ensure_college(token: str) -> str:
    result = _req("GET", "/system/org-tree", token=token)
    nodes = result.get("data")
    if result.get("code") != 0 or not isinstance(nodes, list):
        raise RuntimeError("official organization tree read failed")
    matches = [node for node in nodes if node.get("name") == COLLEGE]
    if len(matches) > 1 or (matches and matches[0].get("type") != "COLLEGE"):
        raise RuntimeError("college organization is ambiguous")
    if matches:
        return str(matches[0].get("id") or "")
    result = _req("POST", "/system/org-nodes", token=token, body={
            "type": "COLLEGE", "name": COLLEGE, "code": "E2E-IX-COL-B",
        })
    if result.get("code") != 0:
        raise RuntimeError("official college organization creation failed")
    return str((result.get("data") or {}).get("id") or "")


def _ensure_scope(token: str, user: dict, college_id: str) -> None:
    user_id = user.get("id") or user.get("userId")
    detail = _req("GET", f"/system/users/{user_id}", token=token)
    if detail.get("code") != 0:
        raise RuntimeError("official account detail read failed")
    data = detail.get("data") or {}
    role_codes = sorted({str(row.get("code") or "").upper() for row in data.get("roles") or []
                         if row.get("code")})
    assignments = data.get("roleAssignments") or []
    matches = [row for row in assignments if row.get("roleCode") == "COLLEGE_ADMIN"]
    if "COLLEGE_ADMIN" not in role_codes or len(matches) != 1:
        raise RuntimeError("account must retain exactly one COLLEGE_ADMIN role")
    current = matches[0]
    items = current.get("scopeItems") or []
    if (current.get("scopeConfigured") is True and current.get("scopeType") == "COLLEGE"
            and current.get("scopeIds") == [college_id]
            and len(items) == 1 and items[0].get("name") == COLLEGE):
        return
    if current.get("scopeConfigured") is not False or current.get("scopeIds") or items:
        raise RuntimeError("existing account has a conflicting configured scope")

    by_code = {row.get("roleCode"): row for row in assignments}
    normalized = []
    for code in role_codes:
        assignment = by_code.get(code)
        if assignment is None:
            raise RuntimeError("an existing role assignment is missing from account detail")
        if code == "COLLEGE_ADMIN":
            normalized.append({"roleCode": code, "scopeType": "COLLEGE", "scopeIds": [college_id]})
            continue
        if assignment.get("scopeConfigured") is False and assignment.get("scopeMode") != "AUTO":
            raise RuntimeError("another role has an unconfigured scope; refusing to change it")
        normalized.append({"roleCode": code, "scopeType": assignment.get("scopeType"),
                           "scopeIds": assignment.get("scopeIds") or []})

    saved = _req("PUT", f"/system/users/{user_id}/roles", token=token,
                 body={"roleCodes": role_codes, "roleAssignments": normalized})
    if saved.get("code") != 0:
        raise RuntimeError("official role-scope assignment failed")
    reread = _req("GET", f"/system/users/{user_id}", token=token)
    if reread.get("code") != 0:
        raise RuntimeError("official role-scope read-back failed")
    verified = (reread.get("data") or {}).get("roleAssignments") or []
    matches = [row for row in verified if row.get("roleCode") == "COLLEGE_ADMIN"]
    if len(matches) != 1 or matches[0].get("scopeConfigured") is not True \
            or matches[0].get("scopeType") != "COLLEGE" \
            or matches[0].get("scopeIds") != [college_id] \
            or len(matches[0].get("scopeItems") or []) != 1 \
            or matches[0]["scopeItems"][0].get("name") != COLLEGE:
        raise RuntimeError("college scope did not match after official role assignment")


def _import_account(token: str) -> None:
    row = [LOGIN, "E2E学院实习负责人B", COLLEGE, "学院实习负责人",
           "COLLEGE_ADMIN", "COLLEGE", COLLEGE]
    content = _workbook_with_rows(build_teacher_template(), [row])
    namespace = f"ix011-college-b-{os.getenv('GITHUB_RUN_ID', 'local')}"
    try:
        # The shared helper's receipt logging is suppressed; its success result may
        # contain a one-time credential receipt, which this script never needs.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _canonical_import(
                token, kind="teachers", content=content,
                idempotency_namespace=namespace,
            )
    except SystemExit:
        raise RuntimeError("canonical teacher import failed") from None


def main() -> int:
    try:
        env_file = _require_isolated_target()
        try:
            token = str(login() or "")
        except SystemExit:
            raise RuntimeError("school administrator login failed") from None
        if not token:
            raise RuntimeError("school administrator login failed")

        college_id = _ensure_college(token)
        if not college_id:
            raise RuntimeError("official college lookup returned no identifier")
        user = _find_user(token, LOGIN)
        if user is None:
            _import_account(token)
            user = _find_user(token, LOGIN)
        if user is None:
            raise RuntimeError("cross-college account is absent after canonical import")
        _ensure_scope(token, user, college_id)

        user_id = user.get("id") or user.get("userId")
        reset = _req("POST", f"/system/users/{user_id}/reset-password", token=token, body={})
        if reset.get("code") != 0:
            raise RuntimeError("official password reset failed")
        temporary = str((reset.get("data") or {}).get("tempPassword") or "")
        if not temporary:
            raise RuntimeError("official password reset returned no temporary password")
        first = _req("POST", "/auth/login",
                     body={"loginName": LOGIN, "password": temporary,
                           "tenantCode": os.getenv("E2E_SANDBOX_ADMIN_TENANT", "sandbox-school")})
        if first.get("code") != 0:
            raise RuntimeError("temporary account login failed")
        password = "E2e!9" + secrets.token_urlsafe(24)
        changed = _req("POST", "/auth/change-password",
                       token=(first.get("data") or {}).get("accessToken"),
                       body={"oldPassword": temporary, "newPassword": password})
        if changed.get("code") != 0:
            raise RuntimeError("official password change failed")
        verified = _req("POST", "/auth/login",
                        body={"loginName": LOGIN, "password": password,
                              "tenantCode": os.getenv("E2E_SANDBOX_ADMIN_TENANT", "sandbox-school")})
        if verified.get("code") != 0:
            raise RuntimeError("final account login failed")
        if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
            print(f"::add-mask::{password}", flush=True)
        with env_file.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"E2E_IX_COLLEGE_B_PASSWORD={password}\n")
        print("[ix-011] cross-college account and official password flow verified")
        return 0
    except RuntimeError as exc:
        print(f"[ix-011] bootstrap blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
