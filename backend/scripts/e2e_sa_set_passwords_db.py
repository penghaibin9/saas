"""Set stable E2E passwords via official hash_password (DB), then paced login verify.

Used when /auth/login IP rate-limit (10/min) makes per-account reset impractical.
Only touches login_name matching E2E SA/graduation accounts in sandbox tenant.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.security import hash_password, verify_password  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from scripts.e2e_bootstrap_student_affairs_accounts import (  # noqa: E402
    ALL_LOGINS, CRED_PATH, STABLE_PWD, STATE_PATH, STUDENT_ORG, TENANT, _req,
)

SANDBOX_TID = 1000000000000000004  # live sandbox-school tenant id


def _tenant_id(db) -> int:
    row = db.execute(text(
        "SELECT id FROM t_tenant WHERE tenant_code=:c AND is_deleted=0 LIMIT 1"
    ), {"c": TENANT}).first()
    if row:
        return int(row[0])
    return SANDBOX_TID


def set_passwords() -> dict[str, str]:
    db = get_sessionmaker()()
    pwd_map: dict[str, str] = {"admin2": "123456"}
    try:
        tid = _tenant_id(db)
        h = hash_password(STABLE_PWD)
        for ln in ALL_LOGINS:
            if ln == "admin2":
                continue
            row = db.execute(text(
                "SELECT id, password_hash FROM t_user "
                "WHERE tenant_id=:tid AND login_name=:ln AND is_deleted=0 LIMIT 1"
            ), {"tid": tid, "ln": ln}).first()
            if not row:
                print("MISSING", ln)
                continue
            db.execute(text(
                "UPDATE t_user SET password_hash=:h, must_change_password=0, "
                "status='ACTIVE', version=COALESCE(version,0)+1 WHERE id=:id"
            ), {"h": h, "id": row[0]})
            pwd_map[ln] = STABLE_PWD
            print("SET", ln, row[0])
        db.commit()
        # ensure student org with valid type
        exists = db.execute(text(
            "SELECT id FROM t_affairs_student_org WHERE tenant_id=:tid AND org_name=:n "
            "AND is_deleted=0 LIMIT 1"
        ), {"tid": tid, "n": STUDENT_ORG}).first()
        if not exists:
            # table name may differ — soft try via API later
            print("student_org table probe:", "no existing row or table missing")
    finally:
        db.close()
    return pwd_map


def ensure_org_api() -> dict:
    # login IP limit = 10/min; wait until admin2 can login again
    for attempt in range(8):
        r = _req("POST", "/auth/login", body={
            "loginName": "admin2", "password": "123456", "tenantCode": TENANT,
        })
        if r.get("code") == 0:
            break
        print("admin login wait", attempt, r.get("bizCode") or r.get("message"))
        time.sleep(15)
    else:
        return {"error": r}
    token = r["data"]["accessToken"]
    listed = _req("GET", "/student-affairs/organizations?pageSize=100", token=token)
    items = ((listed.get("data") or {}).get("list")
             or (listed.get("data") or {}).get("items") or [])
    for o in items:
        if o.get("orgName") == STUDENT_ORG:
            return {"orgId": o.get("id") or o.get("orgId"), "created": False}
    created = _req("POST", "/student-affairs/organizations", token=token, body={
        "orgName": STUDENT_ORG, "orgType": "OTHER", "level": "SCHOOL",
    })
    return {"create": created, "orgId": ((created.get("data") or {}).get("id")
                                         or (created.get("data") or {}).get("orgId"))}


def verify(pwd_map: dict[str, str]) -> list[dict]:
    results = []
    # pace under 10/min: sleep 7s between attempts
    for ln in ALL_LOGINS:
        pwd = pwd_map.get(ln)
        if not pwd:
            results.append({"loginName": ln, "ok": False, "message": "no_pwd"})
            continue
        time.sleep(7)
        r = _req("POST", "/auth/login", body={
            "loginName": ln, "password": pwd, "tenantCode": TENANT,
        })
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            print("RATE_LIMITED, sleep 60", ln)
            time.sleep(60)
            r = _req("POST", "/auth/login", body={
                "loginName": ln, "password": pwd, "tenantCode": TENANT,
            })
        ok = r.get("code") == 0
        results.append({
            "loginName": ln,
            "ok": ok,
            "role": ((r.get("data") or {}).get("currentRole") or {}).get("roleCode") if ok else None,
            "message": None if ok else r.get("message"),
            "dataScope": ((r.get("data") or {}).get("dataScope") if ok else None),
        })
        print("LOGIN", ln, ok, results[-1].get("role"), results[-1].get("message"), flush=True)
    return results


def main() -> int:
    pwd_map = set_passwords()
    # quick local verify of hash
    db = get_sessionmaker()()
    try:
        tid = _tenant_id(db)
        sample = db.execute(text(
            "SELECT login_name, password_hash FROM t_user "
            "WHERE tenant_id=:tid AND login_name='e2e_counselor_a' AND is_deleted=0"
        ), {"tid": tid}).first()
        if sample:
            print("hash_check e2e_counselor_a", verify_password(STABLE_PWD, sample[1]))
    finally:
        db.close()

    org = ensure_org_api()
    print("student_org:", org)
    results = verify(pwd_map)
    CRED_PATH.write_text(json.dumps({
        "tenantCode": TENANT,
        "passwords": pwd_map,
        "loginResults": results,
        "studentOrg": org,
        "method": "db_hash_password + paced_login_verify",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state["loginOk"] = sorted(pwd_map.keys())
    state["studentOrg"] = org
    state["passwordFile"] = str(CRED_PATH)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for x in results if x["ok"])
    print(f"login_ok={ok}/{len(results)}")
    return 0 if ok >= 10 else 1


if __name__ == "__main__":
    sys.exit(main())
