"""Activate E2E academic-affairs account passwords with rate-limit backoff."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
TENANT = "sandbox-school"
STABLE = "E2eTest@2026"
OUT = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_affairs_credentials.local.json"
STATE = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_affairs_state.local.json"


def req(method, path, token=None, body=None):
    data = None
    hdrs = {}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {"code": 0}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(detail)
        except json.JSONDecodeError:
            return {"code": exc.code, "message": detail}


def login_with_backoff(login_name, password, tries=8):
    for i in range(tries):
        r = req("POST", "/auth/login", body={
            "loginName": login_name, "password": password, "tenantCode": TENANT,
        })
        if r.get("code") == 0:
            return r
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            wait = 65
            print(f"rate-limited on {login_name}, sleep {wait}s ({i+1}/{tries})")
            time.sleep(wait)
            continue
        return r
    return r


def login_admin():
    r = login_with_backoff("admin2", "123456")
    if r.get("code") != 0:
        raise SystemExit(f"admin2 login failed: {r}")
    return r["data"]["accessToken"]


def list_e2e_users(token):
    users = {}
    page = 1
    while True:
        r = req("GET", f"/system/users?page={page}&page_size=50", token)
        items = (r.get("data") or {}).get("list") or []
        for u in items:
            ln = str(u.get("loginName") or "")
            if ln.startswith("e2e_aa_") or ln.startswith("E2EAA"):
                users[ln] = u
        total = int((r.get("data") or {}).get("total") or 0)
        if page * 50 >= total or not items:
            break
        page += 1
    return users


def main():
    token = login_admin()
    users = list_e2e_users(token)
    print("found", len(users), sorted(users.keys()))
    pwds = {"admin2": "123456"}
    results = []
    for i, ln in enumerate(sorted(users.keys())):
        lg = login_with_backoff(ln, STABLE, tries=3)
        if lg.get("code") == 0:
            pwds[ln] = STABLE
            results.append({
                "loginName": ln, "ok": True, "skipped": True,
                "role": (lg["data"].get("currentRole") or {}).get("roleCode"),
            })
            continue
        if i % 3 == 0:
            token = login_admin()
        reset = req("POST", f"/system/users/{users[ln]['id']}/reset-password", token, {})
        temp = (reset.get("data") or {}).get("tempPassword")
        if not temp:
            results.append({"loginName": ln, "ok": False, "message": "no_temp", "reset": reset})
            time.sleep(2)
            continue
        time.sleep(2)
        lg = login_with_backoff(ln, temp, tries=5)
        if lg.get("code") != 0:
            results.append({"loginName": ln, "ok": False, "message": lg.get("message")})
            continue
        ch = req("POST", "/auth/change-password", lg["data"]["accessToken"], {
            "oldPassword": temp, "newPassword": STABLE, "confirmPassword": STABLE,
        })
        if ch.get("code") != 0:
            ch = req("POST", "/auth/password/change", lg["data"]["accessToken"], {
                "oldPassword": temp, "newPassword": STABLE,
            })
        lg2 = login_with_backoff(ln, STABLE, tries=5)
        ok = lg2.get("code") == 0
        if ok:
            pwds[ln] = STABLE
        results.append({
            "loginName": ln, "ok": ok,
            "role": ((lg2.get("data") or {}).get("currentRole") or {}).get("roleCode") if ok else None,
            "message": None if ok else lg2.get("message"),
            "change": ch.get("code"),
        })
        time.sleep(2)

    OUT.write_text(json.dumps({
        "tenantCode": TENANT,
        "stablePassword": STABLE,
        "passwords": pwds,
        "loginResults": results,
        "note": "E2E系统管理员=admin2；SCHOOL_ADMIN不可经师生导入",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ensure state file exists with org ids
    if not STATE.exists():
        # minimal: re-fetch org tree names
        token = login_admin()
        tree = req("GET", "/system/org-tree", token)
        # leave empty org — live flow can still use admin
        STATE.write_text(json.dumps({"tenantCode": TENANT, "org": {}, "loginOk": sorted(pwds.keys())},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        state["loginOk"] = sorted(pwds.keys())
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    ok_n = sum(1 for r in results if r.get("ok"))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"ok {ok_n}/{len(results)} -> {OUT}")
    return 0 if ok_n >= 6 else 1


if __name__ == "__main__":
    sys.exit(main())
