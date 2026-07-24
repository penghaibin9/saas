# -*- coding: utf-8 -*-
"""Round7 教务能力补齐 Live 冒烟（8001）。只测新增/改造接口，不造破坏性脏数据。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001/api/v1"
TENANT = "sandbox-school"
STABLE = "E2eTest@2026"
OUT = Path(__file__).resolve().parents[1] / "tmp"
OUT.mkdir(exist_ok=True)
EVID = OUT / "e2e_aa_round7_smoke.local.json"

STEPS = []


def step(name, ok, detail=None):
    STEPS.append({"name": name, "ok": bool(ok), "detail": detail})
    tag = "OK " if ok else "FAIL"
    d = ""
    if detail is not None:
        d = " " + json.dumps(detail, ensure_ascii=False)[:320]
    print(f"{tag} {name}{d}")
    return bool(ok)


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
            return json.loads(raw.decode("utf-8") if raw else "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(raw)
            j.setdefault("httpStatus", exc.code)
            return j
        except json.JSONDecodeError:
            return {"code": exc.code, "httpStatus": exc.code, "message": raw[:400]}
    except Exception as exc:  # noqa: BLE001
        return {"code": None, "message": str(exc)}


def login(ln, pwd=None, client="PC"):
    pwd = pwd or ("123456" if ln == "admin2" else STABLE)
    for _ in range(4):
        r = req("POST", "/auth/login", body={
            "loginName": ln, "password": pwd, "tenantCode": TENANT, "clientType": client,
        })
        if r.get("code") == 0:
            return r["data"]["accessToken"]
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            time.sleep(3)
            continue
        return None
    return None


def switch_role(token, role_code):
    # best-effort; some tenants auto-bind
    r = req("POST", "/auth/switch-role", token=token, body={"roleCode": role_code})
    if r.get("code") == 0 and r.get("data", {}).get("accessToken"):
        return r["data"]["accessToken"]
    return token


def main():
    stu = login("E2EAA20260001", client="MINI_PROGRAM") or login("E2EAA20260001", client="PC")
    step("login student", bool(stu))
    tea = login("e2e_aa_teacher_a", client="MINI_PROGRAM") or login("e2e_aa_teacher_a")
    step("login teacher", bool(tea))
    col = login("e2e_aa_college_a", client="MINI_PROGRAM") or login("e2e_aa_college_a")
    step("login college admin", bool(col))
    adm = login("e2e_aa_admin")
    step("login academic admin", bool(adm))
    if not stu:
        print("ABORT no student token")
        return 2

    # ── P0 registration ──
    r = req("GET", "/mobile/academic/registration/my", token=stu)
    step("mobile registration/my", r.get("code") == 0, {
        "batches": len((r.get("data") or {}).get("batches") or []),
        "note": (r.get("data") or {}).get("note"),
        "msg": r.get("message"),
    })
    r2 = req("GET", "/portal/academic/registration", token=stu)
    step("portal registration", r2.get("code") == 0, {
        "batches": len((r2.get("data") or {}).get("batches") or []),
        "msg": r2.get("message"),
    })

    # self-register without open batch should fail cleanly if we invent id
    bad = req("POST", "/mobile/academic/registration/999999999/register", token=stu)
    step("register fake batch blocked", bad.get("code") != 0, {
        "code": bad.get("code"), "bizCode": bad.get("bizCode"), "msg": bad.get("message"),
    })

    # ── P1 makeup options ──
    r = req("GET", "/mobile/academic/makeup/options", token=stu)
    ok = r.get("code") == 0
    data = r.get("data") or {}
    step("mobile makeup/options", ok, {
        "retake": data.get("retakeTotal"),
        "exemption": data.get("exemptionTotal"),
        "msg": r.get("message"),
    })
    # hand-typed course not in options → should fail
    hand = req("POST", "/mobile/academic/makeup/retake-apply", token=stu, body={
        "courseName": "__NOT_A_REAL_FAIL_COURSE__", "reason": "smoke",
    })
    step("retake hand-type blocked", hand.get("code") != 0, {
        "code": hand.get("code"), "msg": hand.get("message"),
    })
    hand2 = req("POST", "/mobile/academic/makeup/exemption-apply", token=stu, body={
        "courseName": "__NOT_A_REAL_COURSE__", "reason": "smoke",
    })
    step("exemption hand-type blocked", hand2.get("code") != 0, {
        "code": hand2.get("code"), "msg": hand2.get("message"),
    })
    pr = req("GET", "/portal/academic/makeup/options", token=stu)
    step("portal makeup/options", pr.get("code") == 0, {"msg": pr.get("message")})

    # ── P1 teacher schedule-change / status-change pending ──
    for who, tok, label in [
        ("college", col, "college"),
        ("teacher", tea, "teacher"),
        ("admin", adm, "admin"),
    ]:
        if not tok:
            step(f"schedule-change pending ({label})", False, "no token")
            continue
        r = req("GET", "/mobile/teacher/academic/schedule-changes/pending", token=tok)
        step(f"schedule-change pending ({label})", r.get("code") == 0, {
            "total": (r.get("data") or {}).get("total"),
            "note": (r.get("data") or {}).get("note"),
            "msg": r.get("message"),
        })
        r = req("GET", "/mobile/teacher/academic/status-changes/pending", token=tok)
        step(f"status-change pending ({label})", r.get("code") == 0, {
            "total": (r.get("data") or {}).get("total"),
            "note": (r.get("data") or {}).get("note"),
            "msg": r.get("message"),
        })

    # fake review should 404/403/conflict not 500
    if col:
        rr = req("POST", "/mobile/teacher/academic/schedule-changes/999999/review",
                 token=col, body={"action": "APPROVE"})
        step("schedule review fake id not 500",
             (rr.get("httpStatus") or 0) != 500 and rr.get("code") != 500,
             {"code": rr.get("code"), "biz": rr.get("bizCode"), "msg": rr.get("message")})
        rr = req("POST", "/mobile/teacher/academic/status-changes/999999/review",
                 token=col, body={"action": "APPROVE"})
        step("status review fake id not 500",
             (rr.get("httpStatus") or 0) != 500 and rr.get("code") != 500,
             {"code": rr.get("code"), "biz": rr.get("bizCode"), "msg": rr.get("message")})

    # ── P1 attendance ──
    r = req("GET", "/mobile/academic/attendance/my", token=stu)
    step("mobile attendance/my", r.get("code") == 0, {
        "total": (r.get("data") or {}).get("total"),
        "policy": (r.get("data") or {}).get("policy"),
        "msg": r.get("message"),
    })
    r = req("GET", "/portal/academic/attendance", token=stu)
    step("portal attendance", r.get("code") == 0, {
        "policy": (r.get("data") or {}).get("policy"),
        "msg": r.get("message"),
    })

    # ── P1/P2 fee mark endpoint exists (admin) ──
    if adm:
        # list batches
        b = req("GET", "/academic-affairs/graduation-audit-batches?pageSize=5", token=adm)
        batches = ((b.get("data") or {}).get("list") or []) if b.get("code") == 0 else []
        step("list grad batches", b.get("code") == 0, {"n": len(batches), "msg": b.get("message")})
        if batches:
            bid = batches[0].get("batchId")
            m = req("POST", f"/academic-affairs/graduation-audit-batches/{bid}/fee-clearance/mark",
                    token=adm, body={"studentNo": "E2EAA20260001", "status": "CLEARED",
                                     "evidence": "Round7 smoke 人工勾选"})
            # may skip if student not in batch — still should not 500
            step("fee mark one (no 500)", (m.get("httpStatus") or 0) != 500 and m.get("code") != 500, {
                "code": m.get("code"), "data": m.get("data"), "msg": m.get("message"),
            })
            # invalid status
            bad = req("POST", f"/academic-affairs/graduation-audit-batches/{bid}/fee-clearance/mark",
                      token=adm, body={"studentNo": "E2EAA20260001", "status": "PASS"})
            step("fee mark PASS rejected", bad.get("code") != 0, {
                "code": bad.get("code"), "msg": bad.get("message"),
            })
        else:
            step("fee mark one (no 500)", True, "no batch — skipped write")
            step("fee mark PASS rejected", True, "no batch — skipped")

    # ── P2 print + calendar + clearance ──
    r = req("POST", "/mobile/academic/exam/ticket/print", token=stu, body={"reason": "smoke"})
    step("exam ticket print", r.get("code") == 0, {
        "doc": (r.get("data") or {}).get("docName"),
        "msg": r.get("message"),
    })
    r = req("POST", "/mobile/academic/status-change/print", token=stu,
            body={"changeType": "SUSPEND", "reason": "smoke print"})
    step("status-change print", r.get("code") == 0, {
        "doc": (r.get("data") or {}).get("docName"),
        "msg": r.get("message"),
    })
    r = req("POST", "/portal/academic/exam/ticket/print", token=stu, body={"reason": "smoke"})
    step("portal exam ticket print", r.get("code") == 0, {"msg": r.get("message")})

    r = req("GET", "/mobile/academic/calendar/my", token=stu)
    step("mobile calendar/my", r.get("code") == 0, {
        "hasTerm": (r.get("data") or {}).get("hasTerm"),
        "events": len((r.get("data") or {}).get("events") or []),
        "msg": r.get("message"),
    })
    r = req("GET", "/portal/academic/calendar", token=stu)
    step("portal calendar", r.get("code") == 0, {"msg": r.get("message")})

    r = req("GET", "/mobile/academic/clearance/my", token=stu)
    step("mobile clearance/my", r.get("code") == 0, {
        "total": (r.get("data") or {}).get("total"),
        "msg": r.get("message"),
    })
    r = req("GET", "/portal/academic/clearance", token=stu)
    step("portal clearance", r.get("code") == 0, {"msg": r.get("message")})

    # student must not call teacher pending
    deny = req("GET", "/mobile/teacher/academic/schedule-changes/pending", token=stu)
    step("student denied teacher pending", deny.get("code") != 0, {
        "code": deny.get("code"), "biz": deny.get("bizCode"), "msg": deny.get("message"),
    })

    passed = sum(1 for s in STEPS if s["ok"])
    failed = [s for s in STEPS if not s["ok"]]
    summary = {"passed": passed, "total": len(STEPS), "failed": failed}
    EVID.write_text(json.dumps({"steps": STEPS, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSUMMARY", json.dumps(summary, ensure_ascii=False))
    print("EVIDENCE", EVID)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
