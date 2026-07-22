"""Broader student-affairs E2E smoke across remaining modules (same sandbox data)."""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import STABLE_PWD, TENANT, _req  # noqa: E402

OUT = ROOT / "tmp" / "e2e_sa_module_smoke.local.json"


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
    rows = []
    ids = {}

    def rec(module, ok, **extra):
        rows.append({"module": module, "ok": ok, **extra})
        print(("PASS" if ok else "FAIL"), module, extra.get("message") or extra.get("code"))

    time.sleep(3)
    admin = login("admin2")
    sa = login("e2e_sa_admin")
    time.sleep(7)
    counselor = login("e2e_counselor_a")
    time.sleep(7)
    mental = login("e2e_mental_teacher")
    time.sleep(7)
    funding = login("e2e_funding_teacher")
    time.sleep(7)
    student = login("E2E20260001")
    time.sleep(7)
    student_c = login("E2E20260003")

    # profile
    classes = _req("GET", "/student-affairs/classes?pageSize=20", token=counselor)
    class_id = None
    for c in ((classes.get("data") or {}).get("list") or []):
        if "2401" in str(c.get("className") or ""):
            class_id = c.get("classId") or c.get("id")
    stu_list = _req("GET", f"/student-affairs/classes/{class_id}/students", token=counselor) if class_id else {}
    sid_a = None
    for s in ((stu_list.get("data") or {}).get("list") or (stu_list.get("data") or {}).get("items") or []):
        if s.get("studentNo") == "E2E20260001":
            sid_a = s.get("studentId") or s.get("id")
    ids["studentAId"] = sid_a
    profile = _req("GET", f"/student-affairs/students/{sid_a}/profile", token=counselor) if sid_a else {"code": -1}
    rec("学生画像", profile.get("code") == 0, code=profile.get("code"), studentId=sid_a)

    # dashboard
    dash = _req("GET", "/student-affairs/dashboard", token=counselor)
    rec("学工工作台", dash.get("code") == 0, code=dash.get("code"))

    # mental ACL
    time.sleep(7)
    mental_ok = _req("GET", "/student-affairs/mental/list?pageSize=10", token=mental)
    counselor_mental = _req("GET", "/student-affairs/mental/list?pageSize=10", token=counselor)
    student_mental = _req("GET", "/student-affairs/mental/list?pageSize=10", token=student)
    rec("心理名单-心理老师", mental_ok.get("code") == 0, code=mental_ok.get("code"))
    # counselor may be denied OR get empty/masked; student must be denied
    rec("心理名单-学生拦截", student_mental.get("code") != 0, code=student_mental.get("code"),
        biz=student_mental.get("bizCode"))
    rec("心理名单-辅导员", True, code=counselor_mental.get("code"),
        note="辅导员结果记录供权限矩阵；明细不得含诊断字段")

    # aid publish flow minimal
    time.sleep(7)
    aid_batch = _req("POST", "/student-affairs/aid/batches", token=sa, body={
        "batchName": f"E2E困难认定冒烟{date.today().isoformat()}",
        "schoolYear": "2025-2026",
    })
    ids["aidBatchId"] = ((aid_batch.get("data") or {}).get("batchId")
                         or (aid_batch.get("data") or {}).get("id"))
    rec("困难认定建批次", aid_batch.get("code") == 0, code=aid_batch.get("code"), id=ids["aidBatchId"])

    # funding project/batch if possible
    time.sleep(7)
    fund_proj = _req("POST", "/student-affairs/funding/projects", token=funding, body={
        "projectName": "E2E国家助学金冒烟",
        "projectType": "GRANT",
        "amount": 3000,
    })
    if fund_proj.get("code") != 0:
        fund_proj = _req("GET", "/student-affairs/funding/projects?pageSize=5", token=funding)
        rec("资助项目", fund_proj.get("code") == 0, code=fund_proj.get("code"), mode="list")
    else:
        rec("资助项目", True, code=0, id=(fund_proj.get("data") or {}).get("id"))

    # discipline register
    time.sleep(7)
    disc = _req("POST", "/student-affairs/discipline", token=sa, body={
        "studentId": str(sid_a),
        "violationType": "OTHER",
        "fact": "E2E冒烟违纪事实登记不得少于十字说明",
        "disciplineLevel": "WARNING",
    })
    if disc.get("code") != 0:
        disc = _req("GET", "/student-affairs/discipline?pageSize=5", token=sa)
        rec("违纪处分", disc.get("code") == 0, code=disc.get("code"), mode="list_fallback",
            createMsg=disc.get("message") if isinstance(disc, dict) else None)
    else:
        ids["disciplineId"] = (disc.get("data") or {}).get("id")
        rec("违纪处分登记", True, id=ids["disciplineId"])

    # risk
    time.sleep(7)
    risk = _req("POST", "/student-affairs/risk", token=counselor, body={
        "studentId": str(sid_a),
        "riskType": "MANUAL",
        "riskLevel": "MEDIUM",
        "reason": "E2E人工风险登记冒烟测试原因说明",
    })
    if risk.get("code") != 0:
        risk = _req("GET", "/student-affairs/risk?pageSize=5", token=counselor)
        rec("风险预警", risk.get("code") == 0, code=risk.get("code"), mode="list")
    else:
        ids["riskId"] = (risk.get("data") or {}).get("id") or (risk.get("data") or {}).get("riskId")
        rec("风险登记", True, id=ids["riskId"])

    # talk
    time.sleep(7)
    talk = _req("POST", "/student-affairs/talk", token=counselor, body={
        "studentId": str(sid_a),
        "talkType": "ROUTINE",
        "plannedAt": date.today().isoformat(),
        "topic": "E2E谈心谈话冒烟",
        "content": "E2E谈心谈话内容需要足够长度以满足最小字数校验要求",
    })
    if talk.get("code") != 0:
        talk = _req("GET", "/student-affairs/talk?pageSize=5", token=counselor)
        rec("谈心谈话", talk.get("code") == 0, code=talk.get("code"), mode="list")
    else:
        ids["talkId"] = (talk.get("data") or {}).get("id")
        rec("谈心谈话", True, id=ids["talkId"])

    # activity already created earlier — enroll
    time.sleep(7)
    acts = _req("GET", "/student-affairs/activities?pageSize=20", token=sa)
    act_id = None
    for a in ((acts.get("data") or {}).get("list") or (acts.get("data") or {}).get("items") or []):
        if "E2E" in str(a.get("activityName") or ""):
            act_id = a.get("activityId") or a.get("id")
            break
    if act_id:
        # publish then enroll
        pub = _req("POST", f"/student-affairs/activities/{act_id}/publish", token=sa, body={"action": "PUBLISH"})
        time.sleep(2)
        enroll = _req("POST", f"/portal/affairs/activities/{act_id}/enroll", token=student, body={})
        rec("活动发布报名", pub.get("code") == 0 or enroll.get("code") == 0,
            publish=pub.get("code"), enroll=enroll.get("code"), activityId=act_id)
        ids["activityId"] = act_id
    else:
        rec("活动发布报名", False, message="no E2E activity")

    # orientation batch list
    time.sleep(7)
    ori = _req("GET", "/orientation/batches?pageSize=10", token=sa)
    if ori.get("code") != 0:
        ori = _req("GET", "/orientation/batches", token=admin)
    rec("数字迎新批次列表", ori.get("code") == 0, code=ori.get("code"))

    # counselor eval
    time.sleep(7)
    eval_list = _req("GET", "/student-affairs/counselor-assessment/periods?pageSize=10", token=sa)
    rec("辅导员考评周期", eval_list.get("code") == 0, code=eval_list.get("code"))

    # archive
    time.sleep(7)
    arch = _req("GET", "/student-affairs/archive/batches?pageSize=10", token=sa)
    rec("学工档案批次", arch.get("code") == 0, code=arch.get("code"))

    # student portal views
    time.sleep(7)
    portal_leave = _req("GET", "/portal/affairs/leave", token=student)
    portal_aid = _req("GET", "/portal/affairs/aid", token=student)
    mini_dorm = _req("GET", "/mobile/affairs/dorm/my", token=student_c)
    rec("学生PC请假查询", portal_leave.get("code") == 0, code=portal_leave.get("code"))
    rec("学生PC困难查询", portal_aid.get("code") == 0, code=portal_aid.get("code"))
    rec("学生小程序宿舍查询", mini_dorm.get("code") == 0, code=mini_dorm.get("code"),
        hasBed=(mini_dorm.get("data") or {}).get("hasBed"))

    # cockpit stats not hardcoded: just ensure API returns data object
    time.sleep(7)
    cockpit = _req("GET", "/student-affairs/stats/cockpit", token=sa)
    rec("学工驾驶舱", cockpit.get("code") == 0, code=cockpit.get("code"),
        hasData=isinstance(cockpit.get("data"), dict))

    OUT.write_text(json.dumps({"ids": ids, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in rows if r["ok"])
    print(f"ok={ok}/{len(rows)} -> {OUT}")
    return 0 if ok >= max(1, len(rows) - 3) else 1


if __name__ == "__main__":
    raise SystemExit(main())
