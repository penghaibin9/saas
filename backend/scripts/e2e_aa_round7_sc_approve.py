# -*- coding: utf-8 -*-
"""补跑：把无 class_id 的在途调停课单挂到学院A班级后，走学院→教务审批。"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8001/api/v1"
TENANT = "sandbox-school"
STABLE = "E2eTest@2026"
CLASS_A1 = 49
OUT = Path(__file__).resolve().parents[1] / "tmp" / "e2e_aa_round7_sc_approve.local.json"
STEPS = []


def step(name, ok, detail=None):
    STEPS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("OK " if ok else "FAIL"), name, json.dumps(detail, ensure_ascii=False)[:400] if detail else "")
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
        with urllib.request.urlopen(r, timeout=90) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8") if raw else "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(raw)
            j["http"] = exc.code
            return j
        except json.JSONDecodeError:
            return {"code": exc.code, "http": exc.code, "message": raw[:400]}
    except Exception as exc:  # noqa: BLE001
        return {"code": None, "message": str(exc)}


def login(ln, client="PC"):
    pwd = "123456" if ln == "admin2" else STABLE
    for _ in range(4):
        r = req("POST", "/auth/login", body={
            "loginName": ln, "password": pwd, "tenantCode": TENANT, "clientType": client,
        })
        if r.get("code") == 0:
            return r["data"]["accessToken"]
        if r.get("code") == 429001:
            time.sleep(2)
            continue
        return None
    return None


def patch_change_class(change_id: int, class_id: int) -> dict:
    import os
    os.environ.setdefault("DB_ENABLED", "true")
    from sqlalchemy import select
    from app.core.context import set_tenant
    from app.models import AaScheduleChange, AaScheduleItem
    from app.services.db_service import session

    tid = 1000000000000000004
    set_tenant({"tenantId": str(tid), "tenantCode": TENANT})
    with session() as db:
        x = db.get(AaScheduleChange, change_id)
        if not x or x.is_deleted or x.tenant_id != tid:
            return {"ok": False, "error": "change not found"}
        x.class_id = class_id
        x.class_name = "E2E教务测试软技2601班"
        if x.origin_item_id:
            it = db.get(AaScheduleItem, int(x.origin_item_id))
            if it and not it.is_deleted:
                it.class_id = class_id
                it.class_name = x.class_name
                # 若已被终审改 CHANGED，则保持；否则确保 EFFECTIVE 供后续新单
                if it.status == "CHANGED" and x.status in ("SUBMITTED", "COLLEGE_REVIEW"):
                    # origin still valid for pending STOP until applied
                    pass
        db.commit()
        return {"ok": True, "changeId": str(x.id), "status": x.status, "node": x.current_node,
                "classId": str(x.class_id)}


def main():
    # prefer existing pending STOP from writepath (changeId=4), else submit fresh
    tea = login("e2e_aa_teacher_a", "MINI_PROGRAM") or login("e2e_aa_teacher_a")
    col = login("e2e_aa_college_a", "MINI_PROGRAM") or login("e2e_aa_college_a")
    adm = login("e2e_aa_admin")
    step("login", all([tea, col, adm]), {"tea": bool(tea), "col": bool(col), "adm": bool(adm)})
    if not all([tea, col, adm]):
        return 2

    # find pending STOP for teacher
    mine = req("GET", "/mobile/teacher/academic/schedule-changes", token=tea)
    rows = (mine.get("data") or {}).get("list") or (mine.get("data") or {}).get("items") or []
    pending = [r for r in rows if (r.get("status") in ("SUBMITTED", "COLLEGE_REVIEW")
                                   and (r.get("changeType") == "STOP"))]
    change_id = str(pending[0]["changeId"]) if pending else None
    if not change_id:
        # create fresh with classed item via writepath seed helpers
        from e2e_aa_round7_writepath import seed_teacher_schedule_item
        course = "Round7调停课审批课程"
        seeded = seed_teacher_schedule_item("e2e_aa_teacher_a", course, CLASS_A1)
        step("seed item", seeded.get("ok"), seeded)
        sub = req("POST", "/mobile/teacher/academic/schedule-changes", token=tea, body={
            "originItemId": seeded["itemId"], "changeType": "STOP",
            "reason": "Round7调停课审批补跑停课测试",
            "makeupPlan": "下周同课位补一次",
        })
        step("submit", sub.get("code") == 0, sub.get("data") or sub)
        change_id = str((sub.get("data") or {}).get("changeId") or "")
    else:
        step("reuse pending change", True, {"changeId": change_id, "pendingN": len(pending)})

    if not change_id:
        step("have changeId", False, None)
        OUT.write_text(json.dumps({"steps": STEPS}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    patched = patch_change_class(int(change_id), CLASS_A1)
    step("patch class_id", patched.get("ok"), patched)

    pend_c = req("GET", "/mobile/teacher/academic/schedule-changes/pending", token=col)
    plist = (pend_c.get("data") or {}).get("list") or []
    in_col = any(str(x.get("changeId")) == str(change_id) for x in plist)
    step("college sees pending", in_col, {
        "inList": in_col, "total": (pend_c.get("data") or {}).get("total"),
        "ids": [x.get("changeId") for x in plist[:8]],
    })

    rev1 = req("POST", f"/mobile/teacher/academic/schedule-changes/{change_id}/review",
               token=col, body={"action": "APPROVE", "comment": "学院通过 Round7 补跑"})
    step("college APPROVE", rev1.get("code") == 0, {
        "code": rev1.get("code"), "data": rev1.get("data"), "msg": rev1.get("message"),
    })
    if rev1.get("code") != 0:
        OUT.write_text(json.dumps({"steps": STEPS}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    pend_a = req("GET", "/mobile/teacher/academic/schedule-changes/pending", token=adm)
    alist = (pend_a.get("data") or {}).get("list") or []
    in_adm = any(str(x.get("changeId")) == str(change_id) for x in alist)
    step("admin sees pending", in_adm, {
        "total": (pend_a.get("data") or {}).get("total"),
        "ids": [x.get("changeId") for x in alist[:8]],
    })

    rev2 = req("POST", f"/mobile/teacher/academic/schedule-changes/{change_id}/review",
               token=adm, body={"action": "APPROVE", "comment": "教务处终审 Round7 补跑"})
    step("academic APPROVE", rev2.get("code") == 0, {
        "code": rev2.get("code"), "status": (rev2.get("data") or {}).get("status"),
        "applied": (rev2.get("data") or {}).get("applied"), "msg": rev2.get("message"),
    })

    passed = sum(1 for s in STEPS if s["ok"])
    summary = {"passed": passed, "total": len(STEPS),
               "failed": [s for s in STEPS if not s["ok"]]}
    OUT.write_text(json.dumps({"steps": STEPS, "summary": summary}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("SUMMARY", json.dumps(summary, ensure_ascii=False))
    print("EVIDENCE", OUT)
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
