"""Force-set stable E2E passwords via admin reset, matching users by listing all pages."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_graduation_accounts import ADMIN, CRED_PATH, TENANT, _req, login  # noqa: E402

E2E_LOGINS = [
    "e2e_academic_admin", "e2e_college_secretary",
    "e2e_advisor_a", "e2e_advisor_b", "e2e_reviewer",
    "e2e_defense_a", "e2e_defense_b",
    "E2E20260001", "E2E20260002", "E2E20260003",
]
STABLE_PWD = "E2eTest@2026"


def _list_all(token: str) -> dict[str, dict]:
    out = {}
    page = 1
    while True:
        url = f"http://127.0.0.1:8000/api/v1/system/users?page={page}&page_size=50"
        raw = json.loads(urllib.request.urlopen(urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"},
        )).read())
        items = (raw.get("data") or {}).get("list") or []
        for u in items:
            ln = str(u.get("loginName") or u.get("userNo") or "")
            if ln:
                out[ln] = u
        total = int((raw.get("data") or {}).get("total") or 0)
        if page * 50 >= total or not items:
            break
        page += 1
    return out


def main() -> int:
    token = login()
    by = _list_all(token)
    print("known", sorted(k for k in by if k.startswith("e2e") or k.startswith("E2E")))
    pwd_map = {"admin2": ADMIN[1]}
    results = []
    for i, ln in enumerate(E2E_LOGINS):
        time.sleep(7)
        # refresh admin token periodically
        if i % 3 == 0:
            token = login()
        u = by.get(ln)
        if not u:
            results.append({"loginName": ln, "ok": False, "message": "missing_in_list"})
            continue
        # try stable login first
        lg0 = _req("POST", "/auth/login", body={
            "loginName": ln, "password": STABLE_PWD, "tenantCode": TENANT,
        })
        if lg0.get("code") == 0:
            pwd_map[ln] = STABLE_PWD
            results.append({"loginName": ln, "ok": True, "skipped": True,
                            "role": (lg0["data"].get("currentRole") or {}).get("roleCode")})
            continue
        reset = _req("POST", f"/system/users/{u['id']}/reset-password", token=token, body={})
        temp = (reset.get("data") or {}).get("tempPassword")
        if not temp:
            results.append({"loginName": ln, "ok": False, "message": "no_temp", "reset": reset})
            continue
        time.sleep(1)
        lg = _req("POST", "/auth/login", body={"loginName": ln, "password": temp, "tenantCode": TENANT})
        if lg.get("code") != 0:
            results.append({"loginName": ln, "ok": False, "message": lg.get("message")})
            time.sleep(60)
            token = login()
            continue
        ch = _req("POST", "/auth/change-password", token=lg["data"]["accessToken"], body={
            "oldPassword": temp, "newPassword": STABLE_PWD,
        })
        if ch.get("code") != 0:
            results.append({"loginName": ln, "ok": False, "message": ch.get("message")})
            continue
        time.sleep(1)
        lg2 = _req("POST", "/auth/login", body={"loginName": ln, "password": STABLE_PWD, "tenantCode": TENANT})
        ok = lg2.get("code") == 0
        if ok:
            pwd_map[ln] = STABLE_PWD
        results.append({
            "loginName": ln, "ok": ok,
            "role": ((lg2.get("data") or {}).get("currentRole") or {}).get("roleCode") if ok else None,
            "message": None if ok else lg2.get("message"),
        })
    CRED_PATH.write_text(json.dumps({
        "tenantCode": TENANT, "passwords": pwd_map, "loginResults": results,
        "note": "local only; do not commit",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok_n = sum(1 for ln in E2E_LOGINS if pwd_map.get(ln) == STABLE_PWD)
    print(f"stable_ok={ok_n}/{len(E2E_LOGINS)}")
    return 0 if ok_n == len(E2E_LOGINS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
