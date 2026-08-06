"""Verify dedicated interaction-E2E accounts without reading credential files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.e2e_bootstrap_graduation_accounts import ADMIN, TENANT, _req  # noqa: E402
from scripts.e2e_reset_graduation_passwords import (  # noqa: E402
    E2E_LOGINS,
    STABLE_PWD,
)


def _login_headers(index: int) -> dict[str, str]:
    return {"X-Forwarded-For": f"10.252.0.{20 + index}"}


def main() -> int:
    identities = [(ADMIN[0], ADMIN[1]), *[(login_name, STABLE_PWD) for login_name in E2E_LOGINS]]
    results: list[dict] = []
    for index, (login_name, password) in enumerate(identities):
        response = _req(
            "POST",
            "/auth/login",
            headers=_login_headers(index),
            body={
                "loginName": login_name,
                "password": password,
                "tenantCode": TENANT,
            },
        )
        ok = response.get("code") == 0
        role = (
            ((response.get("data") or {}).get("currentRole") or {}).get("roleCode")
            if ok
            else None
        )
        contexts = (
            (response.get("data") or {}).get("contexts")
            or (response.get("data") or {}).get("roleContexts")
            or []
        )
        role_codes = sorted({
            str(item.get("roleCode") or "")
            for item in contexts
            if isinstance(item, dict) and item.get("roleCode")
        })
        results.append({
            "loginName": login_name,
            "ok": ok,
            "role": role,
            "roleCodes": role_codes,
            "message": None if ok else response.get("message"),
        })

    advisor = next(item for item in results if item["loginName"] == "e2e_advisor_a")
    if advisor["ok"] and "INTERN_MENTOR" not in advisor["roleCodes"]:
        advisor["ok"] = False
        advisor["message"] = "missing INTERN_MENTOR role context"

    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok_count = sum(1 for item in results if item.get("ok"))
    print(f"ok={ok_count}/{len(results)}")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
