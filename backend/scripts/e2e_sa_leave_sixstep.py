"""Clean leave six-step using unique dates + dorm list shape fix."""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import STABLE_PWD, TENANT, _req  # noqa: E402

OUT = ROOT / "tmp" / "e2e_sa_leave_sixstep.local.json"


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
    # unique far-future window to avoid overlap with leave 31/32
    start = (date.today() + timedelta(days=40)).isoformat()
    end = (date.today() + timedelta(days=41)).isoformat()

    time.sleep(3)
    st = login("E2E20260002")
    apply = _req("POST", "/portal/affairs/service-apply", token=st, body={
        "serviceKey": "LEAVE", "leaveType": "PERSONAL",
        "startTime": start, "endTime": end,
        "reason": "E2E六步联测学生B请假回家办事补充材料",
    })
    leave_id = str((apply.get("data") or {}).get("id") or "")
    steps.append({"step": "1_portal_apply", "ok": apply.get("code") == 0, "leaveId": leave_id, "resp": apply})
    if not leave_id:
        OUT.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    time.sleep(7)
    st_m = login("E2E20260002")
    mine = _req("GET", "/mobile/affairs/leave/my", token=st_m)
    found = any(str(x.get("leaveId")) == leave_id for x in ((mine.get("data") or {}).get("items") or []))
    steps.append({"step": "2_mini_list_sync", "ok": found, "resp": mine.get("code")})

    time.sleep(7)
    ct = login("e2e_counselor_a")
    pending_pc = _req("GET", "/student-affairs/leave/pending", token=ct)
    pc_items = ((pending_pc.get("data") or {}).get("list")
                or (pending_pc.get("data") or {}).get("items") or [])
    in_pc = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in pc_items)
    steps.append({"step": "3_counselor_pc_pending", "ok": in_pc, "count": len(pc_items)})

    time.sleep(7)
    ct_m = login("e2e_counselor_a")
    pending_m = _req("GET", "/mobile/teacher/affairs/leaves/pending", token=ct_m)
    m_items = ((pending_m.get("data") or {}).get("items")
               or (pending_m.get("data") or {}).get("list") or [])
    in_mini = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in m_items)
    steps.append({"step": "4_counselor_mini_pending", "ok": in_mini, "count": len(m_items)})

    # counselor B must not see
    time.sleep(7)
    ct_b = login("e2e_counselor_b")
    pending_b = _req("GET", "/student-affairs/leave/pending", token=ct_b)
    b_items = ((pending_b.get("data") or {}).get("list")
               or (pending_b.get("data") or {}).get("items") or [])
    leaked = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in b_items)
    steps.append({"step": "5_scope_no_leak_b", "ok": not leaked})

    # return via mini
    ret = _req("POST", f"/mobile/teacher/affairs/leaves/{leave_id}/return", token=ct_m, body={
        "reason": "E2E六步退回请补充行程说明材料",
    })
    steps.append({"step": "6_mini_return", "ok": ret.get("code") == 0, "status": (ret.get("data") or {}).get("affairsStatus")})

    time.sleep(7)
    st2 = login("E2E20260002")
    mine2 = _req("GET", "/mobile/affairs/leave/my", token=st2)
    item = next((x for x in ((mine2.get("data") or {}).get("items") or []) if str(x.get("leaveId")) == leave_id), {})
    steps.append({"step": "7_student_sees_return", "ok": item.get("status") == "RETURNED",
                  "returnReason": item.get("returnReason"), "status": item.get("status")})

    resub = _req("POST", f"/portal/affairs/leave/{leave_id}/resubmit", token=st2, body={
        "reason": "E2E六步已补充行程说明请重新审批",
    })
    steps.append({"step": "8_portal_resubmit", "ok": resub.get("code") == 0,
                  "status": (resub.get("data") or {}).get("affairsStatus"), "resp": resub})

    time.sleep(7)
    ct2 = login("e2e_counselor_a")
    pending2 = _req("GET", "/mobile/teacher/affairs/leaves/pending", token=ct2)
    p2 = ((pending2.get("data") or {}).get("items") or (pending2.get("data") or {}).get("list") or [])
    back = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in p2)
    appr = _req("POST", f"/student-affairs/leave/{leave_id}/approve", token=ct2, body={"comment": "E2E六步同意"})
    steps.append({"step": "9_approve_after_resubmit", "ok": appr.get("code") == 0 and back,
                  "backInPending": back, "status": (appr.get("data") or {}).get("affairsStatus")})

    # student cannot approve
    time.sleep(7)
    st3 = login("E2E20260002")
    hijack = _req("POST", f"/student-affairs/leave/{leave_id}/approve", token=st3, body={"comment": "冒充"})
    steps.append({"step": "10_student_hijack_blocked", "ok": hijack.get("code") in (403001, 403002)
                  or str(hijack.get("bizCode", "")).startswith("NO_")})

    OUT.write_text(json.dumps({"leaveId": leave_id, "steps": steps}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for s in steps if s["ok"])
    print(json.dumps(steps, ensure_ascii=False, indent=2))
    print(f"ok={ok}/{len(steps)} leaveId={leave_id}")
    return 0 if ok == len(steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
