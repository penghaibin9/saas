"""Create dedicated graduation specialist identities through the production import APIs.

Audit-only helper. It does not insert users or roles directly. The canonical teacher
Data Exchange pipeline creates the identities, then official account APIs normalize
and verify their passwords. No plaintext credential receipt is written to disk.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.identity_import_file_service import build_teacher_template  # noqa: E402
from scripts.e2e_bootstrap_graduation_accounts import (  # noqa: E402
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

PRODUCT_EXACT_HEAD = "63195a6dc9d25fa3805563910fb699ec163b552a"
STABLE_PWD = "E2eTest@2026"
SPECIALISTS = (
    ("e2e_defense_secretary", "E2E答辩秘书", "答辩秘书", "GD_DEFENSE_SECRETARY"),
    ("e2e_grade_admin", "E2E毕设成绩管理员", "成绩管理员", "GD_GRADE_ADMIN"),
)


def _teacher_workbook() -> bytes:
    return _workbook_with_rows(
        build_teacher_template(),
        [[login_name, real_name, COLLEGE, position, role_code, "", ""]
         for login_name, real_name, position, role_code in SPECIALISTS],
    )


def _find_user(token: str, login_name: str) -> dict | None:
    result = _req("GET", f"/system/users?keyword={login_name}&page=1&page_size=20", token=token)
    if result.get("code") != 0:
        return None
    return next((row for row in (result.get("data") or {}).get("list") or []
                 if str(row.get("loginName") or row.get("userNo") or "") == login_name), None)


def _normalize_password(token: str, login_name: str, index: int) -> dict:
    user = _find_user(token, login_name)
    if not user:
        return {"loginName": login_name, "ok": False, "message": "user_not_found"}
    user_id = user.get("id") or user.get("userId")
    reset = _req("POST", f"/system/users/{user_id}/reset-password", token=token, body={})
    if reset.get("code") != 0:
        return {"loginName": login_name, "ok": False, "message": reset.get("message")}
    data = reset.get("data") or {}
    temporary = data.get("tempPassword") or data.get("temporaryPassword") or data.get("password")
    if not temporary:
        return {"loginName": login_name, "ok": False, "message": "no_temp_password"}
    headers = {"X-Forwarded-For": f"10.252.0.{40 + index}"}
    first = _req("POST", "/auth/login", headers=headers, body={
        "loginName": login_name, "password": temporary, "tenantCode": TENANT,
    })
    if first.get("code") != 0:
        return {"loginName": login_name, "ok": False, "message": "temporary_login_failed"}
    changed = _req("POST", "/auth/change-password", token=first["data"]["accessToken"], body={
        "oldPassword": temporary, "newPassword": STABLE_PWD,
    })
    if changed.get("code") != 0:
        return {"loginName": login_name, "ok": False, "message": changed.get("message")}
    verified = _req("POST", "/auth/login", headers=headers, body={
        "loginName": login_name, "password": STABLE_PWD, "tenantCode": TENANT,
    })
    role = (((verified.get("data") or {}).get("currentRole") or {}).get("roleCode"))
    return {"loginName": login_name, "ok": verified.get("code") == 0, "role": role}


def main() -> int:
    expected = str(os.environ.get("E2E_EXPECTED_SHA") or "").strip()
    if expected != PRODUCT_EXACT_HEAD:
        print(json.dumps({
            "ok": False,
            "message": "audit harness exact-head drift",
            "expectedEnv": expected,
            "productExactHead": PRODUCT_EXACT_HEAD,
        }, ensure_ascii=False))
        return 2

    token = login()
    ensure_org(token)
    _canonical_import(
        token,
        kind="teachers",
        content=_teacher_workbook(),
        idempotency_namespace="e2e-graduation-specialists-20260823",
    )
    results = [_normalize_password(token, row[0], i) for i, row in enumerate(SPECIALISTS)]
    expected_roles = {row[0]: row[3] for row in SPECIALISTS}
    ok = all(item.get("ok") and item.get("role") == expected_roles[item["loginName"]] for item in results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
