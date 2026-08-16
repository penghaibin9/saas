"""Bootstrap the single student-affairs counselor needed by Playwright CI.

This fixture intentionally uses only official identity and password APIs. It does not
persist credentials, does not relax login throttling, and avoids the broad student-affairs
acceptance bootstrap which repeatedly authenticates the school admin.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.identity_import_file_service import build_teacher_template  # noqa: E402
from scripts.e2e_bootstrap_graduation_accounts import (  # noqa: E402
    CLASS,
    COLLEGE,
    TENANT,
    _req,
    ensure_org,
    login,
)
from scripts.e2e_bootstrap_graduation_accounts_ci import (  # noqa: E402
    _canonical_import,
    _workbook_with_rows,
)

LOGIN_NAME = "e2e_counselor_a"
DISPLAY_NAME = "E2E辅导员A"
STABLE_PASSWORD = "E2eTest@2026"


def build_counselor_xlsx() -> bytes:
    return _workbook_with_rows(
        build_teacher_template(),
        [[
            LOGIN_NAME,
            DISPLAY_NAME,
            COLLEGE,
            "辅导员",
            "COUNSELOR",
            "CLASS",
            CLASS,
        ]],
    )


def import_counselor(token: str) -> None:
    receipt = _canonical_import(
        token,
        kind="teachers",
        content=build_counselor_xlsx(),
        idempotency_namespace="e2e-affairs-counselor",
    )
    print(
        "[e2e-affairs-counselor] canonical identity import confirmed",
        str(receipt.get("id") or receipt.get("jobId") or "confirmed"),
    )


def find_user(token: str) -> dict:
    page = 1
    while True:
        result = _req("GET", f"/system/users?page={page}&page_size=50", token=token)
        if result.get("code") != 0:
            raise SystemExit("list users failed: " + json.dumps(result, ensure_ascii=False))
        data = result.get("data") or {}
        rows = data.get("list") or []
        for user in rows:
            login_name = str(user.get("loginName") or user.get("userNo") or "")
            if login_name == LOGIN_NAME:
                return user
        total = int(data.get("total") or 0)
        if not rows or page * 50 >= total:
            break
        page += 1
    raise SystemExit(f"{LOGIN_NAME} missing after identity import")


def normalize_password(admin_token: str) -> None:
    user = find_user(admin_token)
    reset = _req("POST", f"/system/users/{user['id']}/reset-password", token=admin_token, body={})
    if reset.get("code") != 0:
        raise SystemExit("counselor reset-password failed: " + json.dumps(reset, ensure_ascii=False))
    temp_password = (reset.get("data") or {}).get("tempPassword")
    if not temp_password:
        raise SystemExit("counselor reset-password returned no temporary password")

    time.sleep(1)
    logged = _req("POST", "/auth/login", body={
        "loginName": LOGIN_NAME,
        "password": temp_password,
        "tenantCode": TENANT,
    })
    if logged.get("code") != 0:
        raise SystemExit("counselor temporary login failed: " + json.dumps(logged, ensure_ascii=False))

    access_token = (logged.get("data") or {}).get("accessToken")
    changed = _req("POST", "/auth/change-password", token=access_token, body={
        "oldPassword": temp_password,
        "newPassword": STABLE_PASSWORD,
        "confirmPassword": STABLE_PASSWORD,
    })
    if changed.get("code") != 0:
        changed = _req("POST", "/auth/password/change", token=access_token, body={
            "oldPassword": temp_password,
            "newPassword": STABLE_PASSWORD,
        })
    if changed.get("code") != 0:
        raise SystemExit("counselor password normalization failed: " + json.dumps(changed, ensure_ascii=False))
    print("[e2e-affairs-counselor] password normalized without credential output")


def main() -> int:
    admin_token = login()
    ensure_org(admin_token)
    import_counselor(admin_token)
    normalize_password(admin_token)
    print(f"[e2e-affairs-counselor] ready: {TENANT}:{LOGIN_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
