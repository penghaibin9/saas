"""Activate/reset E2E student-affairs account passwords after rate-limit cool-down."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import (  # noqa: E402
    ALL_LOGINS, CRED_PATH, STABLE_PWD, STATE_PATH, TENANT, activate_passwords,
    ensure_student_org, login_admin, _req,
)


def main() -> int:
    print("waiting 70s for login rate-limit...")
    time.sleep(70)
    token = login_admin()
    org_stu = ensure_student_org(token)
    print("student_org:", org_stu)
    pwds = activate_passwords(token)
    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state["studentOrg"] = org_stu
    state["loginOk"] = sorted(pwds.keys())
    state["passwordFile"] = str(CRED_PATH)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for ln in ALL_LOGINS if ln in pwds)
    print(f"login_ok={ok}/{len(ALL_LOGINS)}")
    # verify matrix briefly
    matrix = []
    for ln in ALL_LOGINS:
        pwd = pwds.get(ln)
        if not pwd:
            matrix.append({"loginName": ln, "ok": False})
            continue
        time.sleep(2)
        r = _req("POST", "/auth/login", body={"loginName": ln, "password": pwd, "tenantCode": TENANT})
        matrix.append({
            "loginName": ln,
            "ok": r.get("code") == 0,
            "role": ((r.get("data") or {}).get("currentRole") or {}).get("roleCode"),
            "message": r.get("message") if r.get("code") != 0 else None,
        })
    print(json.dumps(matrix, ensure_ascii=False, indent=2))
    return 0 if ok >= 10 else 1


if __name__ == "__main__":
    sys.exit(main())
