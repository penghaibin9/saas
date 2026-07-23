"""Reset E2E account passwords via official systemAdmin reset-password API, then change to stable E2E password."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.e2e_bootstrap_graduation_accounts import (  # noqa: E402
    ADMIN, CRED_PATH, TENANT, _req, login,
)

E2E_LOGINS = [
    "e2e_academic_admin", "e2e_college_secretary",
    "e2e_advisor_a", "e2e_advisor_b", "e2e_reviewer",
    "e2e_defense_a", "e2e_defense_b",
    "E2E20260001", "E2E20260002", "E2E20260003",
]
STABLE_PWD = "E2eTest@2026"


def main() -> int:
    token = login()
    users = _req("GET", "/system/users", token=token, body=None)
    # GET with query
    users = _req("GET", "/system/users?keyword=E2E&page=1&page_size=100", token=token)
    # urllib helper doesn't support query-only GET well when body=None — use path with query
    if users.get("code") != 0:
        # fallback list all
        users = json.loads(__import__("urllib.request").request.urlopen(
            __import__("urllib.request").request.Request(
                f"http://127.0.0.1:8000/api/v1/system/users?page=1&page_size=100",
                headers={"Authorization": f"Bearer {token}"},
            )
        ).read())
    items = (users.get("data") or {}).get("list") or []
    by_login = {str(u.get("loginName") or u.get("userNo") or ""): u for u in items}
    print("found users:", sorted(by_login.keys()))

    pwd_map = {"admin2": ADMIN[1]}
    results = []
    for ln in E2E_LOGINS:
        u = by_login.get(ln)
        if not u:
            # try keyword search
            r = json.loads(__import__("urllib.request").request.urlopen(
                __import__("urllib.request").request.Request(
                    f"http://127.0.0.1:8000/api/v1/system/users?keyword={ln}&page=1&page_size=20",
                    headers={"Authorization": f"Bearer {token}"},
                )
            ).read())
            for row in (r.get("data") or {}).get("list") or []:
                if str(row.get("loginName") or row.get("userNo")) == ln:
                    u = row
                    break
        if not u:
            results.append({"loginName": ln, "ok": False, "message": "user_not_found"})
            continue
        uid = u.get("id") or u.get("userId")
        reset = _req("POST", f"/system/users/{uid}/reset-password", token=token, body={})
        if reset.get("code") != 0:
            results.append({"loginName": ln, "ok": False, "message": reset.get("message"), "reset": reset})
            continue
        temp = ((reset.get("data") or {}).get("tempPassword")
                or (reset.get("data") or {}).get("temporaryPassword")
                or (reset.get("data") or {}).get("password"))
        if not temp:
            results.append({"loginName": ln, "ok": False, "message": "no_temp_password", "reset": reset.get("data")})
            continue
        # login with temp
        lg = _req("POST", "/auth/login", body={"loginName": ln, "password": temp, "tenantCode": TENANT})
        if lg.get("code") != 0:
            results.append({"loginName": ln, "ok": False, "message": f"temp_login_fail:{lg.get('message')}"})
            continue
        at = lg["data"]["accessToken"]
        ch = _req("POST", "/auth/change-password", token=at, body={
            "oldPassword": temp, "newPassword": STABLE_PWD,
        })
        if ch.get("code") != 0:
            results.append({"loginName": ln, "ok": False, "message": f"change_fail:{ch.get('message')}"})
            continue
        lg2 = _req("POST", "/auth/login", body={"loginName": ln, "password": STABLE_PWD, "tenantCode": TENANT})
        ok = lg2.get("code") == 0
        role = ((lg2.get("data") or {}).get("currentRole") or {}).get("roleCode") if ok else None
        pwd_map[ln] = STABLE_PWD
        results.append({"loginName": ln, "ok": ok, "role": role, "message": None if ok else lg2.get("message")})

    CRED_PATH.write_text(json.dumps({
        "tenantCode": TENANT,
        "note": "passwords set via official reset-password + change-password; do not commit",
        "passwords": pwd_map,
        "loginResults": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok_n = sum(1 for x in results if x.get("ok"))
    print(f"ok={ok_n}/{len(results)}")
    return 0 if ok_n == len(E2E_LOGINS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
