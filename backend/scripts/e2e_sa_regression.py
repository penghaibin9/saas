"""Regression for SA-BUG-001..005 after fixes. Pace under login rate-limit."""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import CRED_PATH, STABLE_PWD, TENANT, _req  # noqa: E402

OUT = ROOT / "tmp" / "e2e_sa_regression.local.json"


def login(ln: str) -> str:
    pwd = "123456" if ln == "admin2" else STABLE_PWD
    for _ in range(6):
        r = _req("POST", "/auth/login", body={"loginName": ln, "password": pwd, "tenantCode": TENANT})
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            time.sleep(12)
            continue
        assert r.get("code") == 0, r
        return r["data"]["accessToken"]
    raise RuntimeError(f"login failed {ln}")


def main() -> int:
    results = []
    # bind dorm first
    from scripts.e2e_sa_bind_dorm_manager import main as bind_main
    bind_rc = bind_main()
    results.append({"step": "bind_dorm", "ok": bind_rc == 0})

    time.sleep(8)
    # 1) leave: apply(B) -> return -> portal resubmit -> approve
    st = login("E2E20260002")
    start = (date.today() + timedelta(days=10)).isoformat()
    end = (date.today() + timedelta(days=11)).isoformat()
    apply = _req("POST", "/portal/affairs/service-apply", token=st, body={
        "serviceKey": "LEAVE", "leaveType": "PERSONAL",
        "startTime": start, "endTime": end,
        "reason": "E2E回归学生B请假退回重交流程验证",
    })
    leave_id = str((apply.get("data") or {}).get("id") or "")
    results.append({"step": "leave_apply", "ok": apply.get("code") == 0, "leaveId": leave_id, "resp": apply})
    time.sleep(8)
    ct = login("e2e_counselor_a")
    ret = _req("POST", f"/mobile/teacher/affairs/leaves/{leave_id}/return", token=ct, body={
        "reason": "E2E回归退回请补充行程说明材料",
    })
    results.append({"step": "leave_return", "ok": ret.get("code") == 0, "resp": ret})
    time.sleep(8)
    st = login("E2E20260002")
    resub = _req("POST", f"/portal/affairs/leave/{leave_id}/resubmit", token=st, body={
        "reason": "E2E回归已补充行程说明请审批",
    })
    results.append({"step": "leave_resubmit_portal", "ok": resub.get("code") == 0, "resp": resub})
    time.sleep(8)
    # also verify mobile resubmit path is reachable (may conflict if already resubmitted)
    ct = login("e2e_counselor_a")
    appr = _req("POST", f"/student-affairs/leave/{leave_id}/approve", token=ct, body={"comment": "E2E回归通过"})
    results.append({"step": "leave_approve", "ok": appr.get("code") == 0, "resp": appr})

    # 2) dorm checkin by dorm manager
    time.sleep(8)
    admin = login("admin2")
    rooms = _req("GET", "/student-affairs/dorm/buildings/7/rooms?pageSize=20", token=admin)
    room_list = ((rooms.get("data") or {}).get("list") or (rooms.get("data") or {}).get("items") or [])
    room_id = (room_list[0].get("roomId") or room_list[0].get("id")) if room_list else None
    beds = _req("GET", f"/student-affairs/dorm/rooms/{room_id}/beds", token=admin) if room_id else {}
    bed_items = ((beds.get("data") or {}).get("items") or [])
    vacant = next((b for b in bed_items if not b.get("studentId")), bed_items[0] if bed_items else None)
    bed_id = (vacant or {}).get("bedId") or (vacant or {}).get("id")
    # student C id
    stu = _req("GET", "/students?keyword=E2E20260003&pageSize=5", token=admin)
    sid = None
    for it in ((stu.get("data") or {}).get("list") or []):
        if it.get("studentNo") == "E2E20260003":
            sid = it.get("id") or it.get("studentId")
    time.sleep(8)
    dm = login("e2e_dorm_manager")
    checkin = _req("POST", f"/student-affairs/dorm/beds/{bed_id}/checkin", token=dm, body={"studentId": str(sid)})
    results.append({"step": "dorm_checkin", "ok": checkin.get("code") == 0, "resp": checkin, "bedId": bed_id, "studentId": sid})

    # 3) mental list path
    time.sleep(8)
    mt = login("e2e_mental_teacher")
    mental = _req("GET", "/student-affairs/mental/list?pageSize=10", token=mt)
    results.append({"step": "mental_list", "ok": mental.get("code") == 0, "resp": {"code": mental.get("code"), "bizCode": mental.get("bizCode"), "message": mental.get("message")}})

    # 4) aid batch correct fields
    time.sleep(8)
    sa = login("e2e_sa_admin")
    aid = _req("POST", "/student-affairs/aid/batches", token=sa, body={
        "batchName": "E2E困难认定批次2026-回归",
        "schoolYear": "2025-2026",
    })
    results.append({"step": "aid_batch", "ok": aid.get("code") == 0, "resp": aid})

    # 5) activity create
    time.sleep(8)
    am = login("e2e_activity_manager")
    act = _req("POST", "/student-affairs/activities", token=am, body={
        "activityName": "E2E志愿服务日活动-回归",
        "startAt": (date.today() + timedelta(days=2)).isoformat() + "T09:00:00",
        "endAt": (date.today() + timedelta(days=2)).isoformat() + "T12:00:00",
        "quota": 30,
        "location": "E2E广场",
    })
    if act.get("code") != 0:
        act = _req("POST", "/student-affairs/activity", token=am, body={
            "activityName": "E2E志愿服务日活动-回归",
            "startAt": (date.today() + timedelta(days=2)).isoformat() + "T09:00:00",
            "endAt": (date.today() + timedelta(days=2)).isoformat() + "T12:00:00",
            "quota": 30,
        })
    results.append({"step": "activity_create", "ok": act.get("code") == 0, "resp": act})

    OUT.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r["ok"])
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"ok={ok}/{len(results)} -> {OUT}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
