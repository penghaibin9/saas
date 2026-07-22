"""Live sandbox: funding PUBLICITY appeal SUSTAINED/OVERRULED smoke."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import STABLE_PWD, TENANT, _req  # noqa: E402
import scripts.e2e_bootstrap_student_affairs_accounts as _boot  # noqa: E402

# 允许 E2E_API_BASE 指向刚热更的后端（默认仍 8000）
_boot.BASE = os.environ.get("E2E_API_BASE", _boot.BASE).rstrip("/")

OUT = ROOT / "tmp" / "e2e_sa_funding_appeal.local.json"
SA = "/student-affairs"
STU_A = "369"


def login(ln: str) -> str:
    pwd = "123456" if ln == "admin2" else STABLE_PWD
    for _ in range(8):
        r = _req("POST", "/auth/login", body={"loginName": ln, "password": pwd, "tenantCode": TENANT})
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            time.sleep(12)
            continue
        assert r.get("code") == 0, r
        return r["data"]["accessToken"]
    raise RuntimeError(ln)


def main() -> int:
    steps = []
    tag = uuid.uuid4().hex[:6].upper()
    time.sleep(3)
    admin = login("e2e_sa_admin")
    proj = _req("POST", f"{SA}/funding/projects", token=admin, body={
        "projectName": f"E2E申诉奖学金{tag}", "projectType": "SCHOLARSHIP", "amount": 2000, "quota": 5})
    steps.append({"step": "project", "ok": proj.get("code") == 0, "resp": proj})
    pid = str((proj.get("data") or {}).get("projectId") or "")
    time.sleep(7)
    admin = login("e2e_sa_admin")
    batch = _req("POST", f"{SA}/funding/batches", token=admin, body={
        "projectId": pid, "schoolYear": "2025-2026", "publicityDays": 0, "quota": 5, "publish": True})
    steps.append({"step": "batch", "ok": batch.get("code") == 0, "resp": batch})
    bid = str((batch.get("data") or {}).get("batchId") or "")
    time.sleep(7)
    admin = login("e2e_sa_admin")
    app = _req("POST", f"{SA}/funding/applications", token=admin, body={
        "batchId": bid, "studentId": STU_A, "amount": 2000, "statement": "E2E公示申诉联测申请奖学金"})
    steps.append({"step": "apply", "ok": app.get("code") == 0, "resp": app})
    aid = str((app.get("data") or {}).get("applicationId") or "")
    for _ in range(3):
        time.sleep(7)
        admin = login("e2e_sa_admin")
        _req("POST", f"{SA}/funding/applications/{aid}/review", token=admin, body={"action": "APPROVE"})
    time.sleep(7)
    admin = login("e2e_sa_admin")
    det = _req("GET", f"{SA}/funding/applications/{aid}", token=admin)
    steps.append({"step": "publicity", "ok": (det.get("data") or {}).get("status") == "PUBLICITY", "data": det.get("data")})

    # student portal appeal
    time.sleep(7)
    st = login("E2E20260001")
    portal = _req("POST", "/portal/affairs/funding/appeal", token=st,
                  body={"applicationId": aid, "reason": "对公示获奖结果有异议申请复核"})
    steps.append({"step": "portal_appeal", "ok": portal.get("code") == 0, "resp": portal})
    appeal_id = str((portal.get("data") or {}).get("appealId") or "")

    # overruled
    time.sleep(7)
    admin = login("e2e_sa_admin")
    if appeal_id:
        rev = _req("POST", f"{SA}/funding/appeals/{appeal_id}/review", token=admin,
                   body={"result": "OVERRULED", "opinion": "经复核名单无误维持公示结果"})
        steps.append({"step": "overruled", "ok": rev.get("code") == 0 and (rev.get("data") or {}).get("result") == "OVERRULED",
                      "resp": rev})

    # second app for sustained
    time.sleep(7)
    admin = login("e2e_sa_admin")
    app2 = _req("POST", f"{SA}/funding/applications", token=admin, body={
        "batchId": bid, "studentId": "370", "amount": 2000, "statement": "E2E申诉成立联测学生B申请"})
    aid2 = str((app2.get("data") or {}).get("applicationId") or "")
    steps.append({"step": "apply2", "ok": app2.get("code") == 0, "id": aid2})
    for _ in range(3):
        time.sleep(7)
        admin = login("e2e_sa_admin")
        _req("POST", f"{SA}/funding/applications/{aid2}/review", token=admin, body={"action": "APPROVE"})
    time.sleep(7)
    admin = login("e2e_sa_admin")
    a2 = _req("POST", f"{SA}/funding/applications/{aid2}/appeal", token=admin,
              body={"reason": "该生不符合奖学金条件请复核", "appellantName": "评议老师"})
    steps.append({"step": "staff_appeal", "ok": a2.get("code") == 0, "resp": a2})
    oid2 = str((a2.get("data") or {}).get("appealId") or "")
    time.sleep(7)
    admin = login("e2e_sa_admin")
    if oid2:
        r2 = _req("POST", f"{SA}/funding/appeals/{oid2}/review", token=admin,
                  body={"result": "SUSTAINED", "opinion": "核实申诉属实取消其资助资格"})
        steps.append({"step": "sustained", "ok": r2.get("code") == 0, "resp": r2})
        time.sleep(7)
        admin = login("e2e_sa_admin")
        d2 = _req("GET", f"{SA}/funding/applications/{aid2}", token=admin)
        steps.append({"step": "rejected", "ok": (d2.get("data") or {}).get("status") == "REJECTED",
                      "returnReason": (d2.get("data") or {}).get("returnReason"), "data": d2.get("data")})

    passed = sum(1 for s in steps if s.get("ok"))
    out = {"summary": {"passed": passed, "total": len(steps), "ok": passed == len(steps)}, "steps": steps}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"RESULT {passed}/{len(steps)} -> {OUT}")
    return 0 if passed == len(steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
