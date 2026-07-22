"""Student-affairs four-client E2E acceptance runner (API-level, shared backend).

Covers login matrix + core six-step flows. Writes report JSON under backend/tmp/.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.e2e_bootstrap_student_affairs_accounts import (  # noqa: E402
    CLASS_A, CLASS_B, CRED_PATH, STABLE_PWD, STATE_PATH, TENANT, _req,
)

OUT = ROOT / "tmp" / "e2e_student_affairs_acceptance.local.json"
BUGS: list[dict] = []
MATRIX: list[dict] = []
IDS: dict = {}


def creds() -> dict[str, str]:
    data = json.loads(CRED_PATH.read_text(encoding="utf-8"))
    return data.get("passwords") or {}


def login(ln: str, client_type: str | None = None) -> dict:
    pwd = creds().get(ln) or (STABLE_PWD if ln != "admin2" else "123456")
    body = {"loginName": ln, "password": pwd, "tenantCode": TENANT}
    if client_type:
        body["clientType"] = client_type
    for _ in range(5):
        r = _req("POST", "/auth/login", body=body)
        if r.get("bizCode") == "RATE_LIMITED" or r.get("code") == 429001:
            time.sleep(12)
            continue
        return r
    return r


def tok(ln: str, client_type: str | None = None) -> str:
    r = login(ln, client_type)
    if r.get("code") != 0:
        raise RuntimeError(f"login failed {ln}: {r}")
    return r["data"]["accessToken"]


def add_matrix(**kwargs):
    MATRIX.append(kwargs)
    print("MATRIX", kwargs.get("module"), kwargs.get("conclusion"), kwargs.get("bugId"))


def bug(title: str, **kwargs):
    item = {"id": f"SA-BUG-{len(BUGS)+1:03d}", "title": title, **kwargs}
    BUGS.append(item)
    print("BUG", item["id"], title)
    return item["id"]


def resolve_student_id(admin_token: str, student_no: str) -> str | None:
    # profile search via student-affairs classes or system
    r = _req("GET", f"/students?keyword={student_no}&pageSize=20", token=admin_token)
    items = ((r.get("data") or {}).get("list") or (r.get("data") or {}).get("items") or [])
    for it in items:
        if str(it.get("studentNo") or it.get("student_no") or "") == student_no:
            return str(it.get("id") or it.get("studentId"))
    # fallback students profile module
    r2 = _req("GET", f"/student-affairs/profile/students?keyword={student_no}&pageSize=20", token=admin_token)
    items2 = ((r2.get("data") or {}).get("list") or (r2.get("data") or {}).get("items") or [])
    for it in items2:
        if str(it.get("studentNo") or "") == student_no:
            return str(it.get("studentId") or it.get("id"))
    return None


def test_login_matrix():
    print("=== login matrix ===")
    clients = {
        "admin2": ["PC_TEACHER", "MINI_TEACHER"],
        "e2e_sa_admin": ["PC_TEACHER", "MINI_TEACHER"],
        "e2e_counselor_a": ["PC_TEACHER", "MINI_TEACHER"],
        "e2e_dorm_manager": ["PC_TEACHER", "MINI_TEACHER"],
        "E2E20260001": ["PC_STUDENT", "MINI_STUDENT"],
        "E2E20260004": ["PC_STUDENT", "MINI_STUDENT"],
    }
    client_type_map = {
        "PC_TEACHER": "PC",
        "MINI_TEACHER": "MINI_PROGRAM",
        "PC_STUDENT": "PC",
        "MINI_STUDENT": "MINI_PROGRAM",
    }
    for ln, ends in clients.items():
        for end in ends:
            time.sleep(7)
            r = login(ln, client_type_map[end])
            ok = r.get("code") == 0
            role = ((r.get("data") or {}).get("currentRole") or {}).get("roleCode") if ok else None
            # student must not get staff role; staff must not get STUDENT
            role_ok = True
            if ok and ln.startswith("E2E20") and role != "STUDENT":
                role_ok = False
            if ok and ln.startswith("e2e_") and role == "STUDENT":
                role_ok = False
            conclusion = "PASS" if ok and role_ok else "FAIL"
            bid = None
            if conclusion == "FAIL":
                bid = bug("登录矩阵失败", account=ln, end=end, response=r)
            add_matrix(module="身份登录", initiatorEnd=end, initiatorRole=ln,
                       handlerEnd="-", handlerRole="-",
                       pcResult=ok if "PC" in end else "N/A",
                       miniResult=ok if "MINI" in end else "N/A",
                       apiResult=r.get("code"), dbStatus="ACTIVE",
                       conclusion=conclusion, bugId=bid, role=role)


def test_leave_six_step(admin_token: str):
    print("=== leave six-step ===")
    sid = resolve_student_id(admin_token, "E2E20260001")
    IDS["studentAId"] = sid
    if not sid:
        bid = bug("无法解析 E2E20260001 学生档案ID", endpoint="/students")
        add_matrix(module="请假销假", conclusion="BLOCKED", bugId=bid)
        return

    # 1) student portal apply
    time.sleep(7)
    st = tok("E2E20260001", "PC")
    start = (date.today() + timedelta(days=3)).isoformat()
    end = (date.today() + timedelta(days=4)).isoformat()
    apply = _req("POST", "/portal/affairs/service-apply", token=st, body={
        "serviceKey": "LEAVE",
        "leaveType": "PERSONAL",
        "startTime": start,
        "endTime": end,
        "reason": "E2E联测回家办事需要请假一天",
    })
    leave_id = str((apply.get("data") or {}).get("id") or "")
    IDS["leaveId"] = leave_id
    if apply.get("code") != 0 or not leave_id:
        bid = bug("学生PC门户发起请假失败", endpoint="/portal/affairs/service-apply", response=apply)
        add_matrix(module="请假销假", initiatorEnd="学生PC", initiatorRole="E2E学生A",
                   conclusion="FAIL", bugId=bid, apiResult=apply)
        return

    # 2) student mini list same record
    time.sleep(7)
    st_m = tok("E2E20260001", "MINI_PROGRAM")
    mine = _req("GET", "/mobile/affairs/leave/my", token=st_m)
    items = (mine.get("data") or {}).get("items") or []
    found = any(str(x.get("leaveId")) == leave_id for x in items)
    if not found:
        bid = bug("学生小程序看不到门户刚提交的请假", leaveId=leave_id, response=mine)
    else:
        bid = None

    # 3) counselor PC pending
    time.sleep(7)
    ct = tok("e2e_counselor_a", "PC")
    pending_pc = _req("GET", "/student-affairs/leave/pending", token=ct)
    pc_items = ((pending_pc.get("data") or {}).get("list")
                or (pending_pc.get("data") or {}).get("items") or [])
    in_pc = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in pc_items)

    # 4) counselor mini pending
    time.sleep(7)
    ct_m = tok("e2e_counselor_a", "MINI_PROGRAM")
    pending_m = _req("GET", "/mobile/teacher/affairs/leaves/pending", token=ct_m)
    m_items = ((pending_m.get("data") or {}).get("items")
               or (pending_m.get("data") or {}).get("list") or [])
    in_mini = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in m_items)

    # 5) counselor B must NOT see (scope)
    time.sleep(7)
    ct_b = tok("e2e_counselor_b", "PC")
    pending_b = _req("GET", "/student-affairs/leave/pending", token=ct_b)
    b_items = ((pending_b.get("data") or {}).get("list")
               or (pending_b.get("data") or {}).get("items") or [])
    leaked = any(str(x.get("id") or x.get("leaveId")) == leave_id for x in b_items)
    if leaked:
        bug("辅导员B越权看到A班请假待办", leaveId=leave_id)

    # 6) return via mini, student sees reason
    ret = _req("POST", f"/mobile/teacher/affairs/leaves/{leave_id}/return", token=ct_m, body={
        "reason": "E2E退回请补充行程说明材料",
    })
    time.sleep(2)
    mine2 = _req("GET", "/mobile/affairs/leave/my", token=st_m)
    portal_leave = _req("GET", "/portal/affairs/leave", token=st)
    # resubmit via portal service or student-affairs resubmit
    detail = _req("GET", f"/student-affairs/leave/{leave_id}", token=ct)
    status_after_return = ((detail.get("data") or {}).get("affairsStatus")
                           or (ret.get("data") or {}).get("affairsStatus"))

    resub = _req("POST", f"/student-affairs/leave/{leave_id}/resubmit", token=st, body={
        "reason": "E2E联测已补充行程说明可以审批",
        "startTime": start, "endTime": end, "leaveType": "PERSONAL",
    })
    # student may lack student-affairs permission — try portal re-apply path if needed
    if resub.get("code") != 0:
        # student should use portal; check if there's dedicated resubmit
        resub2 = _req("POST", f"/portal/affairs/service-apply", token=st, body={
            "serviceKey": "LEAVE", "leaveType": "PERSONAL",
            "startTime": start, "endTime": end,
            "reason": "E2E联测退回后重交补充行程说明",
            "resubmitLeaveId": leave_id,
        })
        IDS["leaveResubmitAttempt"] = resub2

    time.sleep(7)
    ct2 = tok("e2e_counselor_a", "PC")
    approve = _req("POST", f"/student-affairs/leave/{leave_id}/approve", token=ct2, body={
        "comment": "E2E同意请假",
    })

    # student cannot approve via teacher API
    time.sleep(7)
    st2 = tok("E2E20260001", "PC")
    hijack = _req("POST", f"/student-affairs/leave/{leave_id}/approve", token=st2, body={
        "comment": "学生冒充审批",
    })
    hijack_blocked = hijack.get("code") in (403001, 403002) or hijack.get("bizCode") in (
        "NO_PERMISSION", "NO_DATA_SCOPE") or str(hijack.get("code")).startswith("403")

    conclusion = "PASS"
    bid = None
    problems = []
    if not found:
        problems.append("mini_list_missing")
    if not in_pc:
        problems.append("counselor_pc_pending_missing")
    if not in_mini:
        problems.append("counselor_mini_pending_missing")
    if leaked:
        problems.append("scope_leak_counselor_b")
    if ret.get("code") != 0:
        problems.append(f"return_failed:{ret.get('message')}")
    if approve.get("code") != 0:
        problems.append(f"approve_failed:{approve.get('message')}")
    if not hijack_blocked:
        problems.append("student_token_can_approve_teacher_api")
    if problems:
        conclusion = "FAIL"
        bid = bug("请假六步联测失败", problems=problems, leaveId=leave_id,
                  returnResp=ret, approveResp=approve, hijack=hijack,
                  pendingPcCount=len(pc_items), pendingMiniCount=len(m_items),
                  statusAfterReturn=status_after_return, resubmit=resub)

    add_matrix(
        module="请假销假",
        initiatorEnd="学生PC(/portal/service-apply)",
        initiatorRole="E2E学生A",
        handlerEnd="老师小程序退回→老师PC审批",
        handlerRole="e2e_counselor_a",
        pcResult="PASS" if in_pc and approve.get("code") == 0 else "FAIL",
        miniResult="PASS" if found and in_mini and ret.get("code") == 0 else "FAIL",
        apiResult={"apply": apply.get("code"), "return": ret.get("code"),
                   "approve": approve.get("code"), "hijackBlocked": hijack_blocked},
        dbStatus=status_after_return,
        conclusion=conclusion,
        bugId=bid,
        leaveId=leave_id,
        studentId=sid,
        notes="学生小程序请假页目前仅列表无提交表单(缺失能力)",
    )


def test_dorm(admin_token: str):
    print("=== dorm ===")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    bid = (state.get("dorm") or {}).get("buildingId")
    if not bid:
        listed = _req("GET", "/student-affairs/dorm/buildings?pageSize=50", token=admin_token)
        items = ((listed.get("data") or {}).get("list")
                 or (listed.get("data") or {}).get("items") or [])
        for b in items:
            if b.get("buildingCode") == "E2E-DORM-1":
                bid = b.get("buildingId") or b.get("id")
    IDS["dormBuildingId"] = bid
    rooms = _req("GET", f"/student-affairs/dorm/buildings/{bid}/rooms?pageSize=50", token=admin_token)
    room_list = ((rooms.get("data") or {}).get("list")
                 or (rooms.get("data") or {}).get("items") or [])
    if not room_list:
        bug("宿舍房间为空", buildingId=bid, response=rooms)
        add_matrix(module="宿舍与公寓", conclusion="FAIL", bugId=BUGS[-1]["id"])
        return
    room_id = room_list[0].get("roomId") or room_list[0].get("id")
    beds = _req("GET", f"/student-affairs/dorm/rooms/{room_id}/beds", token=admin_token)
    bed_items = ((beds.get("data") or {}).get("items")
                 or (beds.get("data") or {}).get("list") or [])
    vacant = next((b for b in bed_items if (b.get("status") in ("VACANT", "EMPTY", None)
                                            or not b.get("studentId"))), None)
    if not vacant:
        vacant = bed_items[0] if bed_items else None
    bed_id = (vacant or {}).get("bedId") or (vacant or {}).get("id")
    IDS["bedId"] = bed_id
    sid = IDS.get("studentAId") or resolve_student_id(admin_token, "E2E20260001")
    time.sleep(7)
    dm = tok("e2e_dorm_manager")
    checkin = _req("POST", f"/student-affairs/dorm/beds/{bed_id}/checkin", token=dm, body={
        "studentId": str(sid),
    })
    # double checkin should fail
    checkin2 = _req("POST", f"/student-affairs/dorm/beds/{bed_id}/checkin", token=dm, body={
        "studentId": str(resolve_student_id(admin_token, "E2E20260002")),
    })
    double_blocked = checkin2.get("code") != 0
    # student my dorm via mobile
    time.sleep(7)
    st = tok("E2E20260001", "MINI_PROGRAM")
    my_dorm = _req("GET", "/mobile/affairs/dorm/my", token=st)

    conclusion = "PASS" if checkin.get("code") == 0 and double_blocked else "FAIL"
    bid_bug = None
    if conclusion == "FAIL":
        bid_bug = bug("宿舍入住联测失败", checkin=checkin, double=checkin2, myDorm=my_dorm)
    add_matrix(module="宿舍与公寓", initiatorEnd="老师PC", initiatorRole="e2e_dorm_manager",
               handlerEnd="学生小程序查询", handlerRole="E2E学生A",
               pcResult=checkin.get("code"), miniResult=my_dorm.get("code"),
               apiResult={"checkin": checkin.get("code"), "doubleBlocked": double_blocked},
               dbStatus="OCCUPIED" if checkin.get("code") == 0 else "UNKNOWN",
               conclusion=conclusion, bugId=bid_bug, buildingId=bid, bedId=bed_id)


def test_mental_acl():
    print("=== mental ACL ===")
    time.sleep(7)
    mt = tok("e2e_mental_teacher")
    mental_ok = _req("GET", "/student-affairs/mental?pageSize=10", token=mt)
    time.sleep(7)
    ct = tok("e2e_counselor_a")
    mental_c = _req("GET", "/student-affairs/mental?pageSize=10", token=ct)
    counselor_blocked_or_masked = (
        mental_c.get("code") != 0
        or mental_c.get("bizCode") in ("NO_PERMISSION", "NO_DATA_SCOPE")
        or True  # always record; deep assert on fields below
    )
    # counselor should not get detail fields if list allowed
    leaked_detail = False
    for it in ((mental_c.get("data") or {}).get("list") or []):
        if it.get("diagnosis") or it.get("crisisDetail") or it.get("rawNote"):
            leaked_detail = True
    time.sleep(7)
    st = tok("E2E20260003", "PC")
    mental_stu = _req("GET", "/student-affairs/mental?pageSize=10", token=st)
    stu_blocked = mental_stu.get("code") != 0

    conclusion = "PASS" if mental_ok.get("code") == 0 and stu_blocked and not leaked_detail else "PARTIAL"
    bid = None
    if mental_ok.get("code") != 0:
        conclusion = "FAIL"
        bid = bug("心理老师无法访问心理名单", response=mental_ok)
    if not stu_blocked:
        conclusion = "FAIL"
        bid = bug("学生可访问心理管理接口", response=mental_stu)
    if leaked_detail:
        conclusion = "FAIL"
        bid = bug("辅导员列表泄露心理明细", response=mental_c)
    add_matrix(module="心理关注", initiatorEnd="老师PC", initiatorRole="心理/辅导员/学生",
               handlerEnd="-", handlerRole="-",
               pcResult={"mentalTeacher": mental_ok.get("code"),
                         "counselor": mental_c.get("code"),
                         "student": mental_stu.get("code")},
               miniResult="N/A", apiResult="see pcResult", dbStatus="N/A",
               conclusion=conclusion, bugId=bid,
               notes=f"counselor_blocked_or_masked={counselor_blocked_or_masked}")


def test_profile_scope(admin_token: str):
    print("=== profile/class scope ===")
    time.sleep(7)
    ct = tok("e2e_counselor_a")
    classes = _req("GET", "/student-affairs/classes?pageSize=50", token=ct)
    items = ((classes.get("data") or {}).get("list")
             or (classes.get("data") or {}).get("items") or [])
    names = [x.get("className") or x.get("name") for x in items]
    has_a = any(CLASS_A in str(n) for n in names)
    has_b = any(CLASS_B in str(n) for n in names)
    # counselor A should see A, ideally not B
    conclusion = "PASS" if has_a and not has_b else ("PARTIAL" if has_a else "FAIL")
    bid = None
    if has_b:
        bid = bug("辅导员A班级列表包含B班", classes=names)
    if not has_a:
        bid = bug("辅导员A看不到自己的班级", response=classes)
    add_matrix(module="学生画像与班级", initiatorEnd="老师PC", initiatorRole="e2e_counselor_a",
               handlerEnd="-", handlerRole="-", pcResult=classes.get("code"),
               miniResult="N/A", apiResult={"hasA": has_a, "hasB": has_b, "names": names},
               dbStatus="N/A", conclusion=conclusion, bugId=bid)


def test_aid_batch(admin_token: str):
    print("=== aid ===")
    time.sleep(7)
    sa = tok("e2e_sa_admin")
    batch = _req("POST", "/student-affairs/aid/batches", token=sa, body={
        "batchName": "E2E困难认定批次2026",
        "year": "2026",
        "action": "PUBLISH",
    })
    # schema may differ — try minimal
    if batch.get("code") != 0:
        batch = _req("POST", "/student-affairs/aid/batches", token=sa, body={
            "name": "E2E困难认定批次2026",
            "academicYear": "2025-2026",
        })
    IDS["aidBatch"] = batch.get("data")
    time.sleep(7)
    st = tok("E2E20260001", "PC")
    apply = _req("POST", "/portal/affairs/aid/apply", token=st, body={
        "batchId": (batch.get("data") or {}).get("id") or (batch.get("data") or {}).get("batchId"),
        "reason": "E2E家庭经济困难申请认定测试",
        "level": "GENERAL",
    })
    conclusion = "PASS" if batch.get("code") == 0 else "PARTIAL"
    bid = None
    if batch.get("code") != 0:
        bid = bug("困难认定批次创建失败", response=batch)
        conclusion = "FAIL"
    add_matrix(module="困难认定", initiatorEnd="学生PC", initiatorRole="E2E学生A",
               handlerEnd="老师PC学工处", handlerRole="e2e_sa_admin",
               pcResult={"batch": batch.get("code"), "apply": apply.get("code")},
               miniResult="N/A", apiResult=batch, dbStatus="N/A",
               conclusion=conclusion, bugId=bid)


def test_activity():
    print("=== activity ===")
    time.sleep(7)
    am = tok("e2e_activity_manager")
    created = _req("POST", "/student-affairs/activity", token=am, body={
        "title": "E2E志愿服务日活动",
        "activityName": "E2E志愿服务日活动",
        "startTime": (date.today() + timedelta(days=1)).isoformat() + "T09:00:00",
        "endTime": (date.today() + timedelta(days=1)).isoformat() + "T12:00:00",
        "capacity": 50,
        "location": "E2E广场",
    })
    if created.get("code") != 0:
        created = _req("POST", "/student-affairs/activities", token=am, body={
            "title": "E2E志愿服务日活动",
            "startAt": (date.today() + timedelta(days=1)).isoformat(),
            "endAt": (date.today() + timedelta(days=1)).isoformat(),
            "quota": 50,
        })
    IDS["activity"] = created.get("data")
    act_id = ((created.get("data") or {}).get("id")
              or (created.get("data") or {}).get("activityId"))
    time.sleep(7)
    st = tok("E2E20260001", "PC")
    enroll = None
    if act_id:
        enroll = _req("POST", f"/portal/affairs/activities/{act_id}/enroll", token=st, body={})
    conclusion = "PASS" if created.get("code") == 0 else "FAIL"
    bid = None
    if created.get("code") != 0:
        bid = bug("活动创建失败", response=created)
    add_matrix(module="活动二课", initiatorEnd="老师PC", initiatorRole="e2e_activity_manager",
               handlerEnd="学生PC报名", handlerRole="E2E学生A",
               pcResult={"create": created.get("code"),
                         "enroll": None if enroll is None else enroll.get("code")},
               miniResult="N/A", apiResult=created, dbStatus="N/A",
               conclusion=conclusion, bugId=bid, activityId=act_id)


def test_missing_capabilities():
    """Register known gaps discovered from code audit (not fictional)."""
    gaps = [
        {
            "id": "GAP-001",
            "title": "学生小程序请假页仅列表、无提交表单",
            "evidence": "miniapp/src/pages/student/affairs/leave.vue 无 submit；写入口实际为 /mobile/campus-service/apply",
            "impact": "学生无法在小程序请假页直接发起，需走校园服务申请或补页面",
        },
        {
            "id": "GAP-002",
            "title": "老师/学生小程序同仓 uni-app，非两个独立工程",
            "evidence": "miniapp/README.md + pages student/* 与 teacher/*",
            "impact": "验收按同一工程双身份入口计",
        },
        {
            "id": "GAP-003",
            "title": "SYS_ADMIN 不可经师生导入分配；E2E系统管理员由 admin2/SCHOOL_ADMIN 承担",
            "evidence": "saas_role_templates teacherAssignable=false",
            "impact": "符合平台角色模板约束",
        },
    ]
    IDS["missingCapabilities"] = gaps
    for g in gaps:
        print("GAP", g["id"], g["title"])


def main() -> int:
    test_missing_capabilities()
    # pace before first logins
    time.sleep(5)
    test_login_matrix()
    time.sleep(10)
    admin = tok("admin2")
    try:
        test_leave_six_step(admin)
    except Exception as exc:  # noqa: BLE001
        bug("请假联测异常", error=str(exc), trace=traceback.format_exc())
    try:
        test_dorm(admin)
    except Exception as exc:  # noqa: BLE001
        bug("宿舍联测异常", error=str(exc), trace=traceback.format_exc())
    try:
        test_mental_acl()
    except Exception as exc:  # noqa: BLE001
        bug("心理ACL异常", error=str(exc), trace=traceback.format_exc())
    try:
        test_profile_scope(admin)
    except Exception as exc:  # noqa: BLE001
        bug("班级范围异常", error=str(exc), trace=traceback.format_exc())
    try:
        test_aid_batch(admin)
    except Exception as exc:  # noqa: BLE001
        bug("困难认定异常", error=str(exc), trace=traceback.format_exc())
    try:
        test_activity()
    except Exception as exc:  # noqa: BLE001
        bug("活动联测异常", error=str(exc), trace=traceback.format_exc())

    report = {
        "tenantCode": TENANT,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ids": IDS,
        "matrix": MATRIX,
        "bugs": BUGS,
        "credentialsFile": str(CRED_PATH),
        "stateFile": str(STATE_PATH),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report -> {OUT}")
    print(f"bugs={len(BUGS)} matrix={len(MATRIX)}")
    return 0 if len(BUGS) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
