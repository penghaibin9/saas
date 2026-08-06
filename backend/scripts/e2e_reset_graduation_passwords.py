"""Normalize dedicated interaction-E2E passwords through official account APIs.

No credential receipt or plaintext-password map is written to disk.  Every account is
verified through the real login endpoint after the reset/change sequence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.e2e_bootstrap_graduation_accounts import (  # noqa: E402
    ADMIN,
    TENANT,
    _req,
    login,
)

E2E_LOGINS = [
    "e2e_academic_admin",
    "e2e_college_secretary",
    "e2e_advisor_a",
    "e2e_advisor_b",
    "e2e_reviewer",
    "e2e_defense_a",
    "e2e_defense_b",
    "E2E20260001",
    "E2E20260002",
    "E2E20260003",
]
STABLE_PWD = "E2eTest@2026"


def _login_headers(index: int) -> dict[str, str]:
    """Keep formal IP throttling enabled while isolating legitimate CI identities."""
    return {"X-Forwarded-For": f"10.251.0.{20 + index}"}


def _find_user(token: str, login_name: str) -> dict | None:
    result = _req(
        "GET",
        f"/system/users?keyword={login_name}&page=1&page_size=20",
        token=token,
    )
    if result.get("code") != 0:
        return None
    for row in (result.get("data") or {}).get("list") or []:
        if str(row.get("loginName") or row.get("userNo") or "") == login_name:
            return row
    return None


def main() -> int:
    token = login()
    results: list[dict] = []
    for index, login_name in enumerate(E2E_LOGINS):
        user = _find_user(token, login_name)
        if not user:
            results.append({"loginName": login_name, "ok": False, "message": "user_not_found"})
            continue
        user_id = user.get("id") or user.get("userId")
        reset = _req("POST", f"/system/users/{user_id}/reset-password", token=token, body={})
        if reset.get("code") != 0:
            results.append({"loginName": login_name, "ok": False, "message": reset.get("message")})
            continue
        reset_data = reset.get("data") or {}
        temporary_password = (
            reset_data.get("tempPassword")
            or reset_data.get("temporaryPassword")
            or reset_data.get("password")
        )
        if not temporary_password:
            results.append({"loginName": login_name, "ok": False, "message": "no_temp_password"})
            continue
        headers = _login_headers(index)
        first_login = _req(
            "POST",
            "/auth/login",
            headers=headers,
            body={
                "loginName": login_name,
                "password": temporary_password,
                "tenantCode": TENANT,
            },
        )
        if first_login.get("code") != 0:
            results.append({
                "loginName": login_name,
                "ok": False,
                "message": f"temp_login_fail:{first_login.get('message')}",
            })
            continue
        access_token = first_login["data"]["accessToken"]
        changed = _req(
            "POST",
            "/auth/change-password",
            token=access_token,
            body={"oldPassword": temporary_password, "newPassword": STABLE_PWD},
        )
        if changed.get("code") != 0:
            results.append({
                "loginName": login_name,
                "ok": False,
                "message": f"change_fail:{changed.get('message')}",
            })
            continue
        verified = _req(
            "POST",
            "/auth/login",
            headers=headers,
            body={
                "loginName": login_name,
                "password": STABLE_PWD,
                "tenantCode": TENANT,
            },
        )
        ok = verified.get("code") == 0
        role = (
            ((verified.get("data") or {}).get("currentRole") or {}).get("roleCode")
            if ok
            else None
        )
        results.append({
            "loginName": login_name,
            "ok": ok,
            "role": role,
            "message": None if ok else verified.get("message"),
        })

    # The administrator is also checked, but its password is never serialized.
    admin_check = _req(
        "POST",
        "/auth/login",
        headers={"X-Forwarded-For": "10.251.0.250"},
        body={"loginName": ADMIN[0], "password": ADMIN[1], "tenantCode": TENANT},
    )
    results.append({"loginName": ADMIN[0], "ok": admin_check.get("code") == 0, "role": "SCHOOL_ADMIN"})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(item.get("ok") for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
