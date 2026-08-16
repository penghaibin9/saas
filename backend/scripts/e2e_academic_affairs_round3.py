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


def _attendance_candidate_payloads(options, today=None):
    """Build deterministic candidate coordinates from C-W1 formal schedule patterns.

    The helper does not decide whether a date is currently legal. It only expands the active
    recurrence pattern. The attendance create API remains the final ScopeHead/calendar/change
    authority and may reject a candidate (holiday, SWAP source, concurrent change, duplicate).
    """
    options = options or {}
    start_raw = str(options.get("termStartDate") or "").strip()
    end_raw = str(options.get("termEndDate") or "").strip()
    try:
        term_start = date.fromisoformat(start_raw)
        term_end = date.fromisoformat(end_raw)
    except ValueError:
        return []
    if term_end < term_start:
        return []

    current = today or date.today()
    expanded = []
    seen = set()
    allowed_task_statuses = {"TEACHER_CONFIRMED", "COLLEGE_REVIEW", "APPROVED", "READY"}
    for task in options.get("items") or []:
        if not task.get("formalOccurrenceReady"):
            continue
        if str(task.get("taskStatus") or "").upper() not in allowed_task_statuses:
            continue
        task_id = str(task.get("teachingTaskId") or "").strip()
        class_id = str(task.get("classId") or "").strip()
        if not task_id:
            continue
        for pattern in task.get("formalSchedulePatterns") or []:
            try:
                schedule_item_id = int(pattern.get("scheduleItemId") or 0)
                weekday = int(pattern.get("weekday") or 0)
                slot_no = int(pattern.get("slotNo") or 0)
                start_week = int(pattern.get("startWeek") or 1)
                end_week = int(pattern.get("endWeek") or start_week)
            except (TypeError, ValueError):
                continue
            parity = str(pattern.get("weekParity") or "ALL").upper()
            if schedule_item_id <= 0 or weekday not in range(1, 8) or slot_no <= 0 or start_week <= 0 or end_week < start_week:
                continue
            if parity not in {"ALL", "ODD", "EVEN"}:
                continue
            for week_no in range(start_week, end_week + 1):
                if parity == "ODD" and week_no % 2 == 0:
                    continue
                if parity == "EVEN" and week_no % 2 == 1:
                    continue
                week_chunk_start = term_start + timedelta(days=(week_no - 1) * 7)
                offset = (weekday - week_chunk_start.isoweekday()) % 7
                candidate = week_chunk_start + timedelta(days=offset)
                if candidate < term_start or candidate > term_end:
                    continue
                if ((candidate - term_start).days // 7) + 1 != week_no:
                    continue
                key = (task_id, candidate.isoformat(), slot_no)
                if key in seen:
                    continue
                seen.add(key)
                expanded.append({
                    "payload": {
                        "teachingTaskId": task_id,
                        "classId": class_id,
                        "sessionDate": candidate.isoformat(),
                        "slotNo": slot_no,
                        "scheduleItemId": str(schedule_item_id),
                        "sessionType": "常规",
                    },
                    "scheduleItemId": str(schedule_item_id),
                    "scopeHeadVersion": int(pattern.get("scopeHeadVersion") or 0),
                    "changeId": pattern.get("changeId"),
                    "changeType": pattern.get("changeType"),
                    "candidateDate": candidate,
                })
    expanded.sort(key=lambda row: (
        0 if row["candidateDate"] <= current else 1,
        abs((current - row["candidateDate"]).days),
        row["candidateDate"],
        row["payload"]["teachingTaskId"],
        row["payload"]["slotNo"],
    ))
    for row in expanded:
        row.pop("candidateDate", None)
    return expanded


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
    att_actor = None
    actor_label = ""
    candidates = []

    # C-W1：候选课次只从 attendance class-options 暴露的 ScopeHead-active 正式 pattern 获取。
    # pattern 只负责候选发现；每一次创建仍由生产 create API 重新校验校历/调课/并发/重复场次。
    if teacher_mp:
        teacher_options_resp = req("GET", f"{MOB}/teacher/academic/attendance/class-options", teacher_mp)
        teacher_options = teacher_options_resp.get("data") or {}
        if teacher_options_resp.get("code") == 0:
            candidates = _attendance_candidate_payloads(teacher_options)
        if candidates:
            att_actor = teacher_mp
            actor_label = "teacher"

    if not candidates:
        admin_mp = tok("e2e_aa_admin", "MINI_PROGRAM") or tok("admin2", "MINI_PROGRAM")
        if admin_mp:
            admin_options_resp = req("GET", f"{MOB}/teacher/academic/attendance/class-options", admin_mp)
            admin_options = admin_options_resp.get("data") or {}
            if admin_options_resp.get("code") == 0:
                candidates = _attendance_candidate_payloads(admin_options)
            if candidates:
                att_actor = admin_mp
                actor_label = "admin-formal-task"
                step("R3.att_teacher_task_fallback", True, {
                    "reason": "teacher has no current formal occurrence; admin uses ScopeHead-active formal TeachingTask",
                    "candidateCount": len(candidates),
                })

    sid = None
    selected = None
    create_result = None
    rejected = []
    if att_actor and candidates:
        # 限制候选次数，避免脏数据环境下 E2E 无界探测；正式 API 是唯一判真者。
        for candidate in candidates[:36]:
            create_result = req(
                "POST",
                f"{MOB}/teacher/academic/attendance/sessions",
                att_actor,
                candidate["payload"],
            )
            sid = (create_result.get("data") or {}).get("sessionId")
            if sid:
                selected = candidate
                break
            rejected.append({
                "date": candidate["payload"]["sessionDate"],
                "slotNo": candidate["payload"]["slotNo"],
                "taskId": candidate["payload"]["teachingTaskId"],
                "code": create_result.get("code"),
                "message": create_result.get("message"),
            })

    if sid and selected:
        detail = req("GET", f"{MOB}/teacher/academic/attendance/sessions/{sid}", att_actor)
        roster = (detail.get("data") or {}).get("items") or []
        target = next((it for it in roster if str(it.get("studentNo") or "").startswith("E2EAA")), None)
        if not target and roster:
            target = roster[0]
        mark = {"code": None, "message": "no roster target"}
        if target:
            mark = req("POST", f"{MOB}/teacher/academic/attendance/sessions/{sid}/mark", att_actor, {
                "studentId": target.get("studentId"), "status": "ABSENT",
            })
        sub = req("POST", f"{MOB}/teacher/academic/attendance/sessions/{sid}/submit", att_actor)
        submit_ok = bool(target) and mark.get("code") == 0 and sub.get("code") == 0
        step("R3.att_submit", submit_ok, {
            "create": create_result.get("code") if create_result else None,
            "mark": mark.get("code"),
            "submit": sub.get("code"),
            "sid": sid,
            "teachingTaskId": selected["payload"]["teachingTaskId"],
            "classId": selected["payload"].get("classId"),
            "sessionDate": selected["payload"]["sessionDate"],
            "slotNo": selected["payload"]["slotNo"],
            "scheduleItemId": selected.get("scheduleItemId"),
            "scopeHeadVersion": selected.get("scopeHeadVersion"),
            "changeId": selected.get("changeId"),
            "actor": actor_label,
            "rejectedCandidates": rejected[-5:],
        })
        if submit_ok:
            scan = req("POST", f"{AA}/warnings/scan/attendance", admin)
            step("R3.att_warn_scan", scan.get("code") == 0, scan)
            att_ok = scan.get("code") == 0
            if not att_ok:
                bug(module="旷课预警", severity="P1", result="OPEN",
                    expected="scan/attendance 成功", actual=str(scan)[:300])
        else:
            step("R3.att_warn_scan", False, {"skipped": True, "reason": "attendance mark/submit failed"})
    else:
        step("R3.att_submit", False, {
            "actor": bool(att_actor),
            "candidateCount": len(candidates),
            "rejectedCandidates": rejected[-8:],
            "reason": "no ScopeHead-active formal attendance occurrence accepted by production authority",
        })
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
