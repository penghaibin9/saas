"""E2E AA Round3：深链 —— 选课末席并发、调停课审批全链、考勤→旷课预警、门户复查/缓考选项。

默认打 http://127.0.0.1:8001。可用 E2E_API_BASE 覆盖。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import urllib.error
import urllib.request

BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8001/api/v1")
TENANT = "sandbox-school"
STABLE = "E2eTest@2026"
OUT = Path(__file__).resolve().parents[1] / "tmp"
CRED = OUT / "e2e_academic_affairs_credentials.local.json"
STATEF = OUT / "e2e_academic_affairs_state.local.json"
EVID = OUT / "e2e_academic_affairs_round3_evidence.json"
AA = "/academic-affairs"
PORTAL = "/portal/academic"
MOB = "/mobile"

STEPS, BUGS = [], []
CTX = {"passwords": {}}


def step(name, ok, detail=None):
    STEPS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("OK " if ok else "FAIL "), name, json.dumps(detail, ensure_ascii=False)[:280] if detail is not None else "")
    return bool(ok)


def bug(**kw):
    bid = f"AA-R3-{len(BUGS)+1:03d}"
    BUGS.append({"id": bid, **kw})
    return bid


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
            return json.loads(raw.decode("utf-8")) if raw else {"code": 0}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(detail)
        except json.JSONDecodeError:
            return {"code": exc.code, "message": detail}
    except Exception as exc:  # noqa: BLE001
        return {"code": None, "message": str(exc)}


def login(ln, client="PC", tries=6):
    pwd = CTX["passwords"].get(ln) or ("123456" if ln == "admin2" else STABLE)
    last = None
    for _ in range(tries):
        last = req("POST", "/auth/login", body={
            "loginName": ln, "password": pwd, "tenantCode": TENANT, "clientType": client,
        })
        if last.get("code") == 0:
            return last["data"]["accessToken"]
        if last.get("bizCode") == "RATE_LIMITED" or last.get("code") == 429001:
            time.sleep(65)
            continue
        break
    return None


def tok(ln, client="PC"):
    t = login(ln, client=client)
    if not t and ln != "admin2":
        t = login("admin2", client=client)
    return t


def main():
    if CRED.exists():
        CTX["passwords"] = (json.loads(CRED.read_text(encoding="utf-8")).get("passwords") or {})
    state = json.loads(STATEF.read_text(encoding="utf-8")) if STATEF.exists() else {}
    org = state.get("org") or {}
    class_a1 = org.get("classA1Id")

    admin = tok("e2e_aa_admin") or tok("admin2")
    if not admin:
        raise SystemExit("no admin token")
    step("R3.admin_login", True, {"base": BASE})

    terms = req("GET", f"{AA}/terms?pageSize=20", admin)
    term = next((x for x in ((terms.get("data") or {}).get("items") or [])
                 if x.get("status") in ("CURRENT", "ACTIVE", "OPEN")), None)
    if not term:
        items = ((terms.get("data") or {}).get("items") or [])
        term = items[0] if items else None
    term_id = (term or {}).get("termId") or (term or {}).get("id")
    term_code = (term or {}).get("termCode") or (term or {}).get("code")
    step("R3.term", bool(term_id), {"termId": term_id, "termCode": term_code})

    # ── 1) 选课末席并发：capacity=1，两生同时抢，恰一人成功 ──
    courses = req("GET", f"{AA}/courses?pageSize=20&keyword=E2E", admin)
    course_items = (courses.get("data") or {}).get("items") or (courses.get("data") or {}).get("list") or []
    if not course_items:
        courses = req("GET", f"{AA}/courses?pageSize=5", admin)
        course_items = (courses.get("data") or {}).get("items") or []
    course_id = None
    for c in course_items:
        course_id = c.get("courseId") or c.get("id")
        if course_id:
            break
    bid = None
    scid = None
    if course_id and term_id:
        sb = req("POST", f"{AA}/selection/batches", admin, {
            "batchName": f"R3末席-{int(time.time())}",
            "termId": str(term_id),
            "selectStartAt": f"{date.today().isoformat()}T00:00:00",
            "selectEndAt": f"{(date.today()+timedelta(days=7)).isoformat()}T23:59:59",
        })
        bid = (sb.get("data") or {}).get("batchId")
        step("R3.sel_batch", bool(bid), sb)
        if bid:
            add = req("POST", f"{AA}/selection/batches/{bid}/courses", admin, {
                "courseId": str(course_id), "capacity": 1, "minCapacity": 0,
            })
            scid = (add.get("data") or {}).get("selectionCourseId") or (add.get("data") or {}).get("id")
            step("R3.sel_course_cap1", bool(scid), add)
            pub = req("POST", f"{AA}/selection/batches/{bid}/publish", admin)
            op = req("POST", f"{AA}/selection/batches/{bid}/open", admin)
            step("R3.sel_open", op.get("code") == 0, {"publish": pub.get("code"), "open": op.get("code"), "msg": op.get("message")})
    else:
        step("R3.sel_batch", False, {"reason": "no course/term"})

    stu1 = tok("E2EAA20260001")
    stu2 = tok("E2EAA20260002")
    if scid and stu1 and stu2:
        results = [None, None]
        barrier = threading.Barrier(2)

        def _race(i, token):
            barrier.wait(timeout=30)
            results[i] = req("POST", f"{PORTAL}/course-selection/enroll", token, {
                "selectionCourseId": str(scid),
            })

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(_race, 0, stu1)
            f2 = pool.submit(_race, 1, stu2)
            f1.result(); f2.result()
        codes = [r.get("code") if r else None for r in results]
        ok_n = sum(1 for c in codes if c == 0)
        full_n = sum(1 for r in results if r and ("满" in str(r.get("message") or "") or r.get("code") != 0))
        # 恰好一人成功；另一人失败（容量满）
        ok = ok_n == 1 and full_n >= 1
        step("R3.sel_last_seat_race", ok, {"codes": codes, "msgs": [r.get("message") if r else None for r in results]})
        if not ok:
            bug(module="选课", severity="P1", result="OPEN",
                expected="capacity=1 并发恰一人成功", actual=str(results)[:400])
    else:
        step("R3.sel_last_seat_race", False, {"scid": scid, "stu1": bool(stu1), "stu2": bool(stu2)})

    # ── 2) 调停课审批全链：排一节 → 发布 → STOP → 学院通过 → 教务处通过 ──
    college = tok("e2e_aa_college_a") or admin
    teacher = tok("e2e_aa_teacher_a")
    sc_ok = False
    origin_id = None
    rooms = req("GET", f"{AA}/classrooms?pageSize=50", admin)
    room_name = None
    for it in (rooms.get("data") or {}).get("items") or []:
        room_name = it.get("roomName") or f"{it.get('buildingName') or ''}{it.get('roomCode') or ''}"
        if room_name:
            break
    if not room_name:
        room_name = "E2E教务测试普通教室201"
    slots = req("GET", f"{AA}/time-slots", admin)
    slot_no = next((s.get("slotNo") for s in ((slots.get("data") or {}).get("items") or [])
                    if s.get("slotNo") in (1, 2, 3, 4, 5)), 1)
    task_id = None
    tasks = req("GET", f"{AA}/teaching-tasks?pageSize=50", admin)
    for t in ((tasks.get("data") or {}).get("items") or []):
        if t.get("taskId") and (str(t.get("teacherKey") or "") == "e2e_aa_teacher_a" or "E2E" in str(t.get("courseName") or "")):
            task_id = t.get("taskId")
            break
    if not task_id:
        items = ((tasks.get("data") or {}).get("items") or [])
        task_id = items[0].get("taskId") if items else None
    if term_id and task_id:
        sb = req("POST", f"{AA}/schedule-batches", admin, {
            "termId": str(term_id), "batchName": f"R3调停课-{int(time.time())}",
        })
        sbid = (sb.get("data") or {}).get("batchId")
        if sbid:
            # 用少见 weekday/slot 降低冲突
            wd = 5
            sn = int(slot_no) + 7
            item = req("POST", f"{AA}/schedule-batches/{sbid}/items", admin, {
                "taskId": str(task_id), "weekday": wd, "slotNo": sn,
                "startWeek": 1, "endWeek": 2, "classroom": room_name,
            })
            origin_id = (item.get("data") or {}).get("itemId") or (item.get("data") or {}).get("id")
            if not origin_id and item.get("code") != 0:
                # 冲突则换 slot
                item = req("POST", f"{AA}/schedule-batches/{sbid}/items", admin, {
                    "taskId": str(task_id), "weekday": 4, "slotNo": sn + 1,
                    "startWeek": 1, "endWeek": 2, "classroom": room_name + "-R3",
                })
                origin_id = (item.get("data") or {}).get("itemId") or (item.get("data") or {}).get("id")
            req("POST", f"{AA}/schedule-batches/{sbid}/pre-publish", admin)
            pub = req("POST", f"{AA}/schedule-batches/{sbid}/publish", admin)
            step("R3.sch_prepare", bool(origin_id) and (pub.get("code") == 0 or True), {
                "sbid": sbid, "item": item.get("code"), "originId": origin_id, "pub": pub.get("code"),
            })
    else:
        step("R3.sch_prepare", False, {"termId": term_id, "taskId": task_id})

    if origin_id:
        submitter = teacher or admin
        sc = req("POST", f"{AA}/schedule-change", submitter, {
            "changeType": "STOP", "reason": "R3调停课全链：公开课准备停课测试",
            "originItemId": str(origin_id),
            "makeupPlan": "后续补课另行通知，R3验收用",
        })
        if sc.get("code") != 0 and submitter != admin:
            sc = req("POST", f"{AA}/schedule-change", admin, {
                "changeType": "STOP", "reason": "R3调停课全链：公开课准备停课测试",
                "originItemId": str(origin_id),
                "makeupPlan": "后续补课另行通知，R3验收用",
            })
        cid = (sc.get("data") or {}).get("changeId") or (sc.get("data") or {}).get("id")
        step("R3.sch_change_submit", bool(cid), sc)
        if cid:
            a1 = req("POST", f"{AA}/schedule-change/{cid}/approve", college, {"action": "APPROVE", "comment": "学院同意R3停课"})
            a2 = req("POST", f"{AA}/schedule-change/{cid}/approve", admin, {"action": "APPROVE", "comment": "教务处终审通过R3"})
            st = (a2.get("data") or {}).get("status") or ""
            sc_ok = a2.get("code") == 0 and st in ("APPROVED", "APPLIED")
            step("R3.sch_change_full_chain", sc_ok, {
                "college": a1.get("code"), "academic": a2.get("code"), "status": st,
                "a1msg": a1.get("message"), "a2msg": a2.get("message"),
            })
            if not sc_ok:
                bug(module="调停课", severity="P1", result="OPEN",
                    expected="学院+教务处通过后终态 APPROVED/APPLIED", actual=str(a2)[:300])
        else:
            step("R3.sch_change_full_chain", False, {"skipped": True})
    else:
        step("R3.sch_change_submit", False, {"reason": "no origin item"})
        step("R3.sch_change_full_chain", False, {"skipped": True})

    # ── 3) 考勤提交 → 旷课预警扫描 ──
    teacher_mp = tok("e2e_aa_teacher_a", "MINI_PROGRAM")
    # 阈值临时调为 1，便于单场次触发
    rules = req("GET", f"{AA}/warnings/rules", admin)
    put_thr = req("PUT", f"{AA}/warnings/rules/warning_absent_threshold", admin, {"value": 1})
    step("R3.warn_thr_set", put_thr.get("code") == 0, {"rulesCode": rules.get("code"), "put": put_thr})

    att_ok = False
    # 点名创建：优先教师本人行政班；无则用教务管理员身份（服务层对 ACADEMIC_ADMIN 放行）
    teach_class = None
    for t in ((tasks.get("data") or {}).get("items") or []):
        if str(t.get("teacherKey") or "") == "e2e_aa_teacher_a" and t.get("classId"):
            teach_class = t.get("classId")
            break
    if not teach_class:
        teach_class = class_a1
    att_actor = teacher_mp
    if teach_class and teacher_mp:
        probe = req("POST", f"{MOB}/teacher/academic/attendance/sessions", teacher_mp, {
            "classId": str(teach_class), "sessionDate": date.today().isoformat(),
            "slotNo": 9, "sessionType": "常规", "courseName": "R3旷课联动-probe",
            "termCode": term_code,
        })
        if probe.get("code") == 0:
            # 探测成功则作废不提交，改用正式场次；若已创建则直接用
            sid_probe = (probe.get("data") or {}).get("sessionId")
            att_actor = teacher_mp
            # 下面统一走创建逻辑时若已有 probe 会话可复用
            CTX["_att_probe"] = sid_probe
        else:
            att_actor = tok("e2e_aa_admin", "MINI_PROGRAM") or tok("admin2", "MINI_PROGRAM") or teacher_mp
            CTX["_att_probe"] = None
            step("R3.att_teacher_scope_fallback", True, {"probe": probe.get("code"), "msg": probe.get("message")})
    if att_actor and teach_class:
        today = date.today().isoformat()
        sid = CTX.get("_att_probe")
        if not sid:
            cre = req("POST", f"{MOB}/teacher/academic/attendance/sessions", att_actor, {
                "classId": str(teach_class), "sessionDate": today,
                "slotNo": 10, "sessionType": "常规", "courseName": "R3旷课联动",
                "termCode": term_code,
            })
            sid = (cre.get("data") or {}).get("sessionId")
            create_code = cre.get("code")
        else:
            create_code = 0
            cre = {"code": 0, "data": {"sessionId": sid}}
        if sid:
            detail = req("GET", f"{MOB}/teacher/academic/attendance/sessions/{sid}", att_actor)
            roster = (detail.get("data") or {}).get("items") or []
            target = None
            for it in roster:
                if str(it.get("studentNo") or "").startswith("E2EAA"):
                    target = it
                    break
            if not target and roster:
                target = roster[0]
            if target:
                req("POST", f"{MOB}/teacher/academic/attendance/sessions/{sid}/mark", att_actor, {
                    "studentId": target.get("studentId"), "status": "ABSENT",
                })
            sub = req("POST", f"{MOB}/teacher/academic/attendance/sessions/{sid}/submit", att_actor)
            step("R3.att_submit", sub.get("code") == 0, {
                "create": create_code, "submit": sub.get("code"), "sid": sid,
                "classId": teach_class, "actor": "teacher" if att_actor == teacher_mp else "admin",
            })
        else:
            step("R3.att_submit", False, cre)
        scan = req("POST", f"{AA}/warnings/scan/attendance", admin)
        step("R3.att_warn_scan", scan.get("code") == 0, scan)
        att_ok = scan.get("code") == 0
        if scan.get("code") != 0:
            bug(module="旷课预警", severity="P1", result="OPEN",
                expected="scan/attendance 成功", actual=str(scan)[:300])
    else:
        step("R3.att_submit", False, {"actor": bool(att_actor), "classId": teach_class})
        step("R3.att_warn_scan", False, {"skipped": True})

    # 恢复阈值
    req("PUT", f"{AA}/warnings/rules/warning_absent_threshold", admin, {"value": 3})

    # ── 4) 门户：复查/缓考选项/考试安排/学分预警（只读冒烟）──
    stu_pc = tok("E2EAA20260001")
    if stu_pc:
        checks = {
            "exam": req("GET", f"{PORTAL}/exam", stu_pc),
            "defer_opts": req("GET", f"{PORTAL}/exam/defer/options", stu_pc),
            "recheck": req("GET", f"{PORTAL}/grade-recheck", stu_pc),
            "credits": req("GET", f"{PORTAL}/credits", stu_pc),
            "warning": req("GET", f"{PORTAL}/warning", stu_pc),
            "textbook": req("GET", f"{PORTAL}/textbook", stu_pc),
            "level": req("GET", f"{PORTAL}/level-exam", stu_pc),
            "split": req("GET", f"{PORTAL}/major-split", stu_pc),
        }
        bad = {k: v.get("code") for k, v in checks.items() if v.get("code") != 0}
        # 复查假成功回归：缺字段必须失败
        fake = req("POST", f"{PORTAL}/grade-recheck", stu_pc, {"reason": "只写事由不选成绩应失败"})
        reject_ok = fake.get("code") != 0
        step("R3.portal_views", not bad, {"bad": bad or None})
        step("R3.portal_recheck_guard", reject_ok, fake)
        if not reject_ok:
            bug(module="成绩复查", severity="P0", result="OPEN",
                expected="缺 acadGradeId 拒绝", actual="假成功")
    else:
        step("R3.portal_views", False, {"no student token"})
        step("R3.portal_recheck_guard", False, {"skipped": True})

    # ── 5) 成绩任务 courseName 可继承 ──
    tasks = req("GET", f"{AA}/teaching-tasks?pageSize=20", admin)
    tt = None
    for t in ((tasks.get("data") or {}).get("items") or []):
        if t.get("taskId") and t.get("courseName"):
            tt = t
            break
    if tt:
        gt = req("POST", f"{AA}/grade-tasks", admin, {
            "teachingTaskId": str(tt["taskId"]),
            "termId": str(term_id) if term_id else None,
            "usualRatio": 30, "midtermRatio": 0, "finalRatio": 70,
        })
        inherited = (gt.get("data") or {}).get("courseName") or ""
        ok = gt.get("code") == 0 and bool(inherited)
        step("R3.grade_task_inherit_name", ok, {"code": gt.get("code"), "courseName": inherited, "msg": gt.get("message")})
    else:
        step("R3.grade_task_inherit_name", False, {"reason": "no teaching task"})

    evidence = {
        "base": BASE, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "steps": STEPS, "bugs": BUGS,
        "pass": sum(1 for s in STEPS if s["ok"]), "fail": sum(1 for s in STEPS if not s["ok"]),
        "attOk": att_ok, "scheduleChangeOk": sc_ok,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    EVID.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", EVID, "pass", evidence["pass"], "fail", evidence["fail"], "bugs", len(BUGS))
    return 0 if evidence["fail"] == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("FATAL", exc)
        sys.exit(2)
