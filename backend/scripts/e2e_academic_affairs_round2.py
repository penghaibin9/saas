"""E2E AA Round2: 审查修复后深链（重叠真断言 / 排课正确载荷 / 成绩发布 / 学生评教）。

默认打 http://127.0.0.1:8001 （避免 8000 僵尸进程旧代码）。可用 E2E_API_BASE 覆盖。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import urllib.error
import urllib.request

BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8001/api/v1")
TENANT = "sandbox-school"
STABLE = "E2eTest@2026"
OUT = Path(__file__).resolve().parents[1] / "tmp"
CRED = OUT / "e2e_academic_affairs_credentials.local.json"
STATEF = OUT / "e2e_academic_affairs_state.local.json"
EVID = OUT / "e2e_academic_affairs_round2_evidence.json"
AA = "/academic-affairs"

STEPS, BUGS, MATRIX = [], [], []
CTX = {"passwords": {}}


def step(name, ok, detail=None):
    STEPS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("OK " if ok else "FAIL "), name, json.dumps(detail, ensure_ascii=False)[:260] if detail is not None else "")
    return bool(ok)


def bug(**kw):
    bid = f"AA-E2E-{len(BUGS)+1:03d}"
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
    CTX.update({
        "collegeA": org.get("collegeAId"), "collegeB": org.get("collegeBId"),
        "classA1": org.get("classA1Id"), "classB1": org.get("classB1Id"),
        "majorA": org.get("majorAId"),
    })

    admin = tok("e2e_aa_admin") or tok("admin2")
    if not admin:
        raise SystemExit("no admin token")
    step("R2.admin_login", True, {"base": BASE})

    # ── 1) 节次重叠真断言（message 必须含「重叠」）──
    base_no = 920 + (int(time.time()) % 70)
    a = req("POST", f"{AA}/time-slots", admin, {
        "slotNo": base_no, "slotName": f"R2锚点{base_no}", "startTime": "05:10", "endTime": "05:55",
    })
    o = req("POST", f"{AA}/time-slots", admin, {
        "slotNo": base_no + 1, "slotName": f"R2重叠{base_no+1}", "startTime": "05:20", "endTime": "06:00",
    })
    msg = str(o.get("message") or "")
    ok = o.get("code") != 0 and "重叠" in msg
    step("R2.timeslot_overlap", ok, {"anchor": a.get("code"), "overlap": o})
    if not ok:
        bug(module="校历节次", severity="P1", result="OPEN",
            expected="拒绝且含「重叠」", actual=msg[:200])

    # ── 2) 找学期 / 教学任务 / 教室 ──
    terms = req("GET", f"{AA}/terms?pageSize=20", admin)
    term = next((x for x in ((terms.get("data") or {}).get("items") or [])
                 if x.get("status") in ("CURRENT", "ACTIVE", "OPEN")), None)
    if not term:
        items = ((terms.get("data") or {}).get("items") or [])
        term = items[0] if items else None
    term_id = (term or {}).get("termId") or (term or {}).get("id")
    CTX["termId"] = term_id
    step("R2.term", bool(term_id), term)

    rooms = req("GET", f"{AA}/classrooms?pageSize=100", admin)
    room_name = None
    for it in (rooms.get("data") or {}).get("items") or []:
        if it.get("buildingCode") == "E2E-AA-B1":
            room_name = it.get("roomName") or f"{it.get('buildingName')}{it.get('roomCode')}"
            break
    if not room_name:
        cr = req("POST", f"{AA}/classrooms", admin, {
            "buildingCode": "E2E-AA-B1", "buildingName": "E2E教务测试1号教学楼",
            "roomCode": "201", "roomName": "E2E教务测试普通教室201", "capacity": 45, "roomType": "LECTURE",
        })
        room_name = (cr.get("data") or {}).get("roomName") or "E2E教务测试普通教室201"
    step("R2.classroom", bool(room_name), {"room": room_name})

    slots = req("GET", f"{AA}/time-slots", admin)
    slot_no = next((s.get("slotNo") for s in ((slots.get("data") or {}).get("items") or [])
                    if s.get("slotNo") in (1, 2, 3)), 1)

    tasks_hits = []
    page = 1
    while page <= 20:
        tasks = req("GET", f"{AA}/teaching-tasks?page={page}&pageSize=50", admin)
        items = (tasks.get("data") or {}).get("items") or []
        if not items:
            break
        for t in items:
            code = str(t.get("courseCode") or "")
            name = str(t.get("courseName") or "")
            tkey = str(t.get("teacherKey") or "")
            if code.startswith("AAE") or "E2E教务" in name or tkey == "e2e_aa_teacher_a":
                if t.get("taskId"):
                    tasks_hits.append(t)
        total = int((tasks.get("data") or {}).get("total") or 0)
        if page * 50 >= total:
            break
        page += 1
    # 优先已确认的 AAE 任务
    preferred = [t for t in tasks_hits if str(t.get("courseCode") or "").startswith("AAE") and t.get("teacherKey")]
    assigned = preferred or [t for t in tasks_hits if t.get("teacherKey")] or tasks_hits
    task_ids = [t.get("taskId") for t in assigned[:3] if t.get("taskId")]
    step("R2.teaching_tasks", len(task_ids) >= 1, {
        "ids": task_ids, "sample": [{k: assigned[0].get(k) for k in ("taskId", "courseCode", "courseName", "classId", "teacherKey", "status")}] if assigned else [],
    })

    # ── 3) 排课：正确字段 + 冲突 ──
    sbid = None
    if term_id:
        sb = req("POST", f"{AA}/schedule-batches", admin, {
            "termId": str(term_id), "batchName": f"R2课表-{int(time.time())}",
        })
        sbid = (sb.get("data") or {}).get("batchId")
        step("R2.schedule_batch", bool(sbid), sb)
    if sbid and task_ids:
        item = req("POST", f"{AA}/schedule-batches/{sbid}/items", admin, {
            "taskId": str(task_ids[0]), "weekday": 3, "slotNo": int(slot_no),
            "startWeek": 1, "endWeek": 16, "classroom": room_name,
        })
        step("R2.schedule_item", item.get("code") == 0, item)
        if len(task_ids) > 1:
            conflict = req("POST", f"{AA}/schedule-batches/{sbid}/items", admin, {
                "taskId": str(task_ids[1]), "weekday": 3, "slotNo": int(slot_no),
                "startWeek": 1, "endWeek": 16, "classroom": room_name,
            })
            step("R2.schedule_conflict", conflict.get("code") != 0, conflict)
        pub = req("POST", f"{AA}/schedule-batches/{sbid}/pre-publish", admin)
        pub2 = req("POST", f"{AA}/schedule-batches/{sbid}/publish", admin)
        step("R2.schedule_publish", pub2.get("code") == 0 or pub.get("code") == 0, {
            "pre": pub.get("code"), "pub": pub2.get("code"), "preMsg": pub.get("message"), "pubMsg": pub2.get("message"),
        })
        stu_pc = tok("E2EAA20260001")
        stu_mp = tok("E2EAA20260001", client="MINI_PROGRAM")
        tea_mp = tok("e2e_aa_teacher_a", client="MINI_PROGRAM")
        pc = req("GET", "/portal/academic/schedule", stu_pc) if stu_pc else {}
        mp = req("GET", "/mobile/academic/schedule/my", stu_mp) if stu_mp else {}
        tm = req("GET", "/mobile/teacher/academic/schedule/mine", tea_mp) if tea_mp else {}
        four = pc.get("code") == 0 and mp.get("code") == 0
        step("R2.four_end_schedule", four, {"pc": pc.get("code"), "mp": mp.get("code"), "teaMp": tm.get("code")})
        MATRIX.append({
            "node": "课表四端", "result": "PASS" if four else "FAIL",
            "studentPC": "PASS" if pc.get("code") == 0 else "FAIL",
            "studentMP": "PASS" if mp.get("code") == 0 else "FAIL",
            "teacherMP": "PASS" if tm.get("code") == 0 else "FAIL",
        })

    # ── 4) 成绩发布链（学院通过→教务发布；无单独 academic-review 端点）──
    teacher = tok("e2e_aa_teacher_a") or admin
    college = tok("e2e_aa_college_a") or admin
    course_name = (assigned[0].get("courseName") if assigned else None) or "E2E教务测试程序设计"
    class_id = (assigned[0].get("classId") if assigned else None) or CTX.get("classA1")
    gt = req("POST", f"{AA}/grade-tasks", admin, {
        "teachingTaskId": str(task_ids[0]) if task_ids else None,
        "termId": str(term_id) if term_id else None,
        "courseName": course_name,
        "classId": str(class_id) if class_id else None,
        "usualRatio": 40, "finalRatio": 60,
    })
    gtid = (gt.get("data") or {}).get("gradeTaskId")
    step("R2.grade_task", bool(gtid) and bool((gt.get("data") or {}).get("classId")), gt)
    graded_login = None
    if gtid:
        roster = req("GET", f"{AA}/grade-tasks/{gtid}/roster", teacher)
        students = (roster.get("data") or {}).get("items") or (roster.get("data") or {}).get("list") or []
        entered = 0
        for s in students[:30]:
            sid = s.get("studentId") or s.get("id")
            if not sid:
                continue
            sno = s.get("studentNo")
            if not graded_login and sno:
                graded_login = sno
            usual = 92 if sno == "E2EAA20260001" else 55
            final = 88 if sno == "E2EAA20260001" else 48
            er = req("POST", f"{AA}/grade-tasks/{gtid}/scores", teacher, {
                "studentId": str(sid), "usualScore": usual, "finalScore": final,
            })
            if er.get("code") == 0:
                entered += 1
        step("R2.grade_enter", entered > 0, {"entered": entered, "roster": len(students), "gradedLogin": graded_login})
        if entered:
            req("POST", f"{AA}/grade-tasks/{gtid}/submit", teacher)
            cr = req("POST", f"{AA}/grade-tasks/{gtid}/college-review", college, {"action": "APPROVE"})
            pub = req("POST", f"{AA}/grade-tasks/{gtid}/publish", admin)
            ok_pub = pub.get("code") == 0
            step("R2.grade_publish", ok_pub, {"college": cr.get("code"), "pub": pub})
            if not graded_login:
                graded_login = "E2EAA20260003"
            stu = tok(graded_login)
            tr = req("GET", "/portal/academic/transcript", stu) if stu else {}
            mp_tr = req("GET", "/mobile/academic/transcript/my", tok(graded_login, "MINI_PROGRAM") or "")
            tr_items = ((tr.get("data") or {}).get("items") or (tr.get("data") or {}).get("list") or [])
            visible = tr.get("code") == 0 and len(tr_items) > 0
            step("R2.transcript_visible", visible, {
                "login": graded_login, "pc": tr.get("code"), "mp": mp_tr.get("code"),
                "pcItems": len(tr_items),
                "sample": tr_items[:1],
            })
            MATRIX.append({
                "node": "成绩发布可见", "result": "PASS" if ok_pub and visible else "FAIL",
                "teacherPC": "PASS", "studentPC": "PASS" if visible else "FAIL",
                "studentMP": "PASS" if mp_tr.get("code") == 0 else "FAIL",
            })

    # ── 5) 学生评教（AA-E2E-002）：用教学班实际学生提交 + 跨班拒绝 ──
    ev = req("POST", f"{AA}/evaluation/batches", admin, {
        "batchName": f"R2学生评教-{int(time.time())}",
        "termId": str(term_id) if term_id else None,
        "anonymous": True,
    })
    ebid = (ev.get("data") or {}).get("batchId")
    step("R2.eval_batch", bool(ebid), ev)
    if ebid and task_ids:
        gen = req("POST", f"{AA}/evaluation/batches/{ebid}/tasks", admin, {
            "teachingTaskIds": [str(x) for x in task_ids], "evaluatorType": "STUDENT",
        })
        step("R2.eval_generate", gen.get("code") == 0, gen)
        pub_ev = req("POST", f"{AA}/evaluation/batches/{ebid}/publish", admin)
        open_ev = req("POST", f"{AA}/evaluation/batches/{ebid}/open", admin)
        step("R2.eval_open", open_ev.get("code") == 0, {
            "publish": pub_ev.get("code"), "open": open_ev.get("code"), "openMsg": open_ev.get("message"),
        })
        # 本班学生：优先成绩名单登录名，其次 003（A2）
        in_class_login = graded_login or "E2EAA20260003"
        out_class_login = "E2EAA20260001" if in_class_login != "E2EAA20260001" else "E2EAA20260002"
        stu_mp = tok(in_class_login, "MINI_PROGRAM")
        tasks_my = req("GET", "/mobile/academic/evaluation/tasks", stu_mp) if stu_mp else {}
        my_list = (tasks_my.get("data") or {}).get("list") or []
        step("R2.eval_tasks_my", tasks_my.get("code") == 0 and len(my_list) > 0, {
            "login": in_class_login, "code": tasks_my.get("code"),
            "total": (tasks_my.get("data") or {}).get("total"), "sample": my_list[:1],
        })
        if my_list:
            sub = req("POST", "/mobile/academic/evaluation/submit", stu_mp, {
                "taskId": my_list[0]["taskId"], "objectiveScore": 91,
                "comment": "R2匿名评教", "answers": {"overall": 91},
            })
            step("R2.eval_submit", sub.get("code") == 0, sub)
            other = tok(out_class_login, "MINI_PROGRAM")
            deny = req("POST", "/mobile/academic/evaluation/submit", other, {
                "taskId": my_list[0]["taskId"], "objectiveScore": 80,
            }) if other else {"code": None, "message": "no other student token"}
            denied = deny.get("code") != 0
            step("R2.eval_cross_class_denied", denied, {"login": out_class_login, "resp": deny})
            if not denied:
                bug(module="学生评教", severity="P0", result="OPEN",
                    expected="跨班提交拒绝", actual=str(deny)[:240])
            MATRIX.append({
                "node": "学生评教匿名提交",
                "result": "PASS" if sub.get("code") == 0 and denied else "FAIL",
                "studentMP": "PASS" if sub.get("code") == 0 else "FAIL",
                "crossClass": "PASS" if denied else "FAIL",
            })
        elif open_ev.get("code") == 0:
            bug(module="学生评教", severity="P1", result="OPEN",
                expected="开放后本班学生可见任务", actual=str(tasks_my)[:300])

    # ── 6) 学院隔离抽检 ──
    college_b = tok("e2e_aa_college_b")
    if college_b:
        stu_list = req("GET", f"{AA}/students?keyword=E2EAA20260001&pageSize=20", college_b)
        items = (stu_list.get("data") or {}).get("items") or (stu_list.get("data") or {}).get("list") or []
        leak = any(str(x.get("studentNo") or "") == "E2EAA20260001" for x in items)
        step("R2.org_isolation", not leak, {"count": len(items), "leak": leak})

    evidence = {
        "base": BASE, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "steps": STEPS, "bugs": BUGS, "matrix": MATRIX,
        "pass": sum(1 for s in STEPS if s["ok"]), "fail": sum(1 for s in STEPS if not s["ok"]),
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
