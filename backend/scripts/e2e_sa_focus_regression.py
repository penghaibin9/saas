"""Focused regression: leave resubmit + dorm checkin after backend restart."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import STABLE_PWD, TENANT, _req  # noqa: E402
from scripts.e2e_sa_bind_dorm_manager import main as bind_dorm  # noqa: E402

OUT = ROOT / "tmp" / "e2e_sa_focus_regression.local.json"


def login(ln: str) -> str:
    pwd = "123456" if ln == "admin2" else STABLE_PWD
    for _ in range(8):
        r = _req("POST", "/auth/login", body={"loginName": ln, "password": pwd, "tenantCode": TENANT})
        if r.get("code") in (429001,) or r.get("bizCode") == "RATE_LIMITED":
            time.sleep(12)
            continue
        assert r.get("code") == 0, r
        return r["data"]["accessToken"]
    raise RuntimeError(ln)


def main() -> int:
    results = []
    bind_dorm()
    time.sleep(5)

    # 1) Student B: resubmit existing RETURNED leave 32 (or find one)
    st = login("E2E20260002")
    mine = _req("GET", "/mobile/affairs/leave/my", token=st)
    items = (mine.get("data") or {}).get("items") or []
    returned = next((x for x in items if x.get("status") == "RETURNED"), None)
    leave_id = str((returned or {}).get("leaveId") or "32")
    resub = _req("POST", f"/portal/affairs/leave/{leave_id}/resubmit", token=st, body={
        "reason": "E2E焦点回归：已补充行程说明请审批",
    })
    if resub.get("code") != 0:
        # fallback mobile campus-service apply with leaveId
        resub = _req("POST", "/mobile/campus-service/apply", token=st, body={
            "serviceKey": "LEAVE", "leaveId": leave_id,
            "reason": "E2E焦点回归：已补充行程说明请审批",
        })
    results.append({"step": "leave_resubmit", "ok": resub.get("code") == 0, "leaveId": leave_id, "resp": resub})

    time.sleep(8)
    ct = login("e2e_counselor_a")
    pending = _req("GET", "/mobile/teacher/affairs/leaves/pending", token=ct)
    pitems = ((pending.get("data") or {}).get("items") or (pending.get("data") or {}).get("list") or [])
    in_pending = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in pitems)
    appr = _req("POST", f"/student-affairs/leave/{leave_id}/approve", token=ct, body={"comment": "E2E焦点回归通过"})
    results.append({"step": "leave_approve", "ok": appr.get("code") == 0, "inPending": in_pending, "resp": appr})

    # 2) dorm checkin as dorm manager for student C
    time.sleep(8)
    admin = login("admin2")
    classes = _req("GET", "/student-affairs/classes?pageSize=50", token=admin)
    class_id = None
    for c in ((classes.get("data") or {}).get("list") or []):
        if "2401" in str(c.get("className") or c.get("name") or ""):
            class_id = c.get("classId") or c.get("id")
            break
    students = _req("GET", f"/student-affairs/classes/{class_id}/students", token=admin) if class_id else {}
    sid = None
    slist = ((students.get("data") or {}).get("list")
             or (students.get("data") or {}).get("items") or [])
    if isinstance(students.get("data"), list):
        slist = students.get("data")
    for s in slist:
        if isinstance(s, dict) and s.get("studentNo") == "E2E20260003":
            sid = s.get("studentId") or s.get("id")
            break
    # DB fallback
    if not sid:
        from sqlalchemy import text
        from app.db.session import get_sessionmaker
        db = get_sessionmaker()()
        try:
            row = db.execute(text(
                "SELECT id FROM t_student_profile WHERE student_no='E2E20260003' AND is_deleted=0 LIMIT 1"
            )).first()
            sid = str(row[0]) if row else None
        finally:
            db.close()

    rooms = _req("GET", "/student-affairs/dorm/buildings/7/rooms?pageSize=20", token=admin)
    room_list = ((rooms.get("data") or {}).get("list") or (rooms.get("data") or {}).get("items") or [])
    room_id = (room_list[-1].get("roomId") or room_list[-1].get("id")) if room_list else None
    beds = _req("GET", f"/student-affairs/dorm/rooms/{room_id}/beds", token=admin) if room_id else {}
    bed_items = ((beds.get("data") or {}).get("items") or [])
    vacant = next((b for b in bed_items if not b.get("studentId")), None)
    bed_id = (vacant or {}).get("bedId") or (vacant or {}).get("id")

    time.sleep(8)
    dm = login("e2e_dorm_manager")
    blist = _req("GET", "/student-affairs/dorm/buildings?pageSize=20", token=dm)
    results.append({
        "step": "dorm_list_as_manager",
        "ok": blist.get("code") == 0 and len(((blist.get("data") or {}).get("list") or [])) > 0,
        "count": len(((blist.get("data") or {}).get("list") or [])),
        "data": blist.get("data"),
    })
    checkin = {"code": -1, "message": "missing"}
    if sid and bed_id:
        checkin = _req("POST", f"/student-affairs/dorm/beds/{bed_id}/checkin", token=dm,
                       body={"studentId": str(sid)})
    results.append({"step": "dorm_checkin", "ok": checkin.get("code") == 0,
                    "bedId": bed_id, "studentId": sid, "resp": checkin})

    # double occupancy blocked
    if checkin.get("code") == 0:
        dup = _req("POST", f"/student-affairs/dorm/beds/{bed_id}/checkin", token=dm,
                   body={"studentId": str(sid)})
        results.append({"step": "dorm_double_blocked", "ok": dup.get("code") != 0, "resp": dup})

    OUT.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r["ok"])
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"ok={ok}/{len(results)} -> {OUT}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
