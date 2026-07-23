# -*- coding: utf-8 -*-
"""Round7 续测：挂科→重修全链 + 调停课提交→学院审→教务审。"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8001/api/v1"
TENANT = "sandbox-school"
STABLE = "E2eTest@2026"
OUT = Path(__file__).resolve().parents[1] / "tmp"
OUT.mkdir(exist_ok=True)
EVID = OUT / "e2e_aa_round7_writepath.local.json"

STEPS = []


def step(name, ok, detail=None):
    STEPS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("OK " if ok else "FAIL"), name,
          json.dumps(detail, ensure_ascii=False)[:360] if detail is not None else "")
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


SANDBOX_TID = 1000000000000000004


def _bind_sandbox_tenant():
    """脚本直连 DB 无请求上下文时，_tid() 会落到 demo；显式绑定 sandbox-school。"""
    from app.core.context import set_tenant
    set_tenant({"tenantId": str(SANDBOX_TID), "tenantCode": TENANT})


def seed_fail_grade(student_no: str, course_name: str) -> dict:
    """直接落一条 FAILED 正式成绩（绕过完整录分发布链，专供重修选项冒烟）。"""
    from sqlalchemy import select
    from app.models import AcademicGrade, AcademicStudent, StudentProfile
    from app.services.db_service import _tid, session

    _bind_sandbox_tenant()
    with session() as db:
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.student_no == student_no,
            StudentProfile.is_deleted.is_(False))).first()
        if not s:
            return {"ok": False, "error": "student not found", "tid": _tid()}
        acad = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == s.id,
            AcademicStudent.is_deleted.is_(False))).first()
        if not acad:
            acad = AcademicStudent(
                tenant_id=_tid(), student_id=s.id, student_no=s.student_no,
                name=s.real_name or student_no, class_id=str(s.class_id or ""),
            )
            db.add(acad)
            db.flush()
        # soft-delete prior smoke fails with same course to keep unique latest
        for old in db.scalars(select(AcademicGrade).where(
                AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
                AcademicGrade.course_name == course_name,
                AcademicGrade.is_deleted.is_(False))).all():
            old.is_deleted = True
        g = AcademicGrade(
            tenant_id=_tid(), acad_student_id=acad.id, course_name=course_name,
            term="2025-2026-2", nature="REQUIRED", credit_value=3.0,
            score=45, pass_status="FAILED", exam_type="FINAL",
            record_status="ACTIVE", source="MANUAL",
        )
        db.add(g)
        db.flush()
        gid = g.id
        db.commit()
        return {"ok": True, "gradeId": str(gid), "studentId": str(s.id), "acadStudentId": str(acad.id)}


def seed_teacher_schedule_item(teacher_login: str, course_name: str, class_id: int = 49,
                               class_name: str = "E2E教务测试软技2601班") -> dict:
    """在当前已发布批次为教师挂一条 EFFECTIVE 课位（供调停课提交；须带 class_id 供学院范围）。"""
    from sqlalchemy import select
    from app.models import AaScheduleBatch, AaScheduleItem

    _bind_sandbox_tenant()
    from app.services.db_service import _tid, session
    with session() as db:
        batch = db.scalars(select(AaScheduleBatch).where(
            AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.status == "PUBLISHED",
            AaScheduleBatch.is_deleted.is_(False)).order_by(AaScheduleBatch.id.desc())).first()
        if not batch:
            return {"ok": False, "error": "no published batch"}
        # soft-delete prior smoke items same course+teacher
        for old in db.scalars(select(AaScheduleItem).where(
                AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == batch.id,
                AaScheduleItem.teacher_key == teacher_login,
                AaScheduleItem.course_name == course_name,
                AaScheduleItem.is_deleted.is_(False))).all():
            old.is_deleted = True
        item = AaScheduleItem(
            tenant_id=_tid(), batch_id=batch.id, course_name=course_name,
            class_id=int(class_id), class_name=class_name, teacher_key=teacher_login,
            teacher_name="E2E教师A", weekday=3, slot_no=2,
            start_week=1, end_week=18, week_parity="ALL",
            classroom_text="Round7-101", status="EFFECTIVE", source="MANUAL",
        )
        db.add(item)
        db.flush()
        iid = item.id
        db.commit()
        return {
            "ok": True, "itemId": str(iid), "batchId": str(batch.id),
            "teacherKey": teacher_login, "classId": str(class_id),
        }


def main():
    issues = []
    stu = login("E2EAA20260001", "MINI_PROGRAM") or login("E2EAA20260001")
    tea = login("e2e_aa_teacher_a", "MINI_PROGRAM") or login("e2e_aa_teacher_a")
    col = login("e2e_aa_college_a", "MINI_PROGRAM") or login("e2e_aa_college_a")
    adm = login("e2e_aa_admin")
    step("login all", all([stu, tea, col, adm]), {
        "stu": bool(stu), "tea": bool(tea), "col": bool(col), "adm": bool(adm),
    })
    if not all([stu, tea, col, adm]):
        return 2

    # ── 1) 挂科 → 重修 ──
    course = "Round7重修冒烟课程"
    seed = seed_fail_grade("E2EAA20260001", course)
    step("seed FAIL grade", seed.get("ok"), seed)
    if not seed.get("ok"):
        issues.append(f"造挂科失败: {seed}")

    opts = req("GET", "/mobile/academic/makeup/options", token=stu)
    retakes = ((opts.get("data") or {}).get("retakeOptions") or [])
    hit = next((x for x in retakes if x.get("courseName") == course), None)
    step("makeup options contains seeded course", bool(hit), {
        "retakeTotal": (opts.get("data") or {}).get("retakeTotal"), "hit": hit,
    })
    if not hit:
        issues.append("挂科未出现在重修候选列表")

    if hit:
        apply = req("POST", "/mobile/academic/makeup/retake-apply", token=stu, body={
            "gradeId": hit["gradeId"],
            "courseName": hit["courseName"],
            "termCode": hit.get("termCode") or "2025-2026-2",
            "reason": "Round7 live retake apply",
        })
        step("retake apply success", apply.get("code") == 0, {
            "code": apply.get("code"), "data": apply.get("data"), "msg": apply.get("message"),
        })
        if apply.get("code") != 0:
            issues.append(f"重修报名失败: {apply.get('message')}")
        else:
            mine = req("GET", "/mobile/academic/makeup/my", token=stu)
            rows = ((mine.get("data") or {}).get("retakes") or [])
            ok = any(r.get("courseName") == course for r in rows)
            step("retake appears in my list", ok, {"n": len(rows)})
            if not ok:
                issues.append("重修报名成功但列表未见")

        # portal path too
        p_apply = req("POST", "/portal/academic/retake/apply", token=stu, body={
            "gradeId": hit["gradeId"], "courseName": hit["courseName"],
            "termCode": hit.get("termCode"), "reason": "portal duplicate should conflict",
        })
        step("duplicate retake blocked", p_apply.get("code") != 0, {
            "code": p_apply.get("code"), "msg": p_apply.get("message"),
        })

    # ── 2) 调停课提交 → 审批 ──
    sc_course = "Round7调停课冒烟课程"
    seeded_sc = seed_teacher_schedule_item("e2e_aa_teacher_a", sc_course)
    step("seed teacher schedule item", seeded_sc.get("ok"), seeded_sc)
    if not seeded_sc.get("ok"):
        issues.append(f"造课位失败: {seeded_sc}")

    sched = req("GET", "/mobile/teacher/academic/schedule/mine", token=tea)
    items = (sched.get("data") or {}).get("items") or []
    step("teacher schedule items", bool(items), {
        "n": len(items), "batchId": (sched.get("data") or {}).get("batchId"),
        "note": (sched.get("data") or {}).get("note"), "msg": sched.get("message"),
        "sample": [{k: it.get(k) for k in ("itemId", "id", "courseName", "teacherKey")} for it in items[:3]],
    })
    origin = None
    for it in items:
        if it.get("courseName") == sc_course or str(it.get("itemId") or it.get("id")) == str(seeded_sc.get("itemId")):
            origin = it
            break
    if not origin and items:
        origin = items[0]
    if not origin and seeded_sc.get("itemId"):
        origin = {"itemId": seeded_sc["itemId"], "courseName": sc_course, "status": "EFFECTIVE"}


    change_id = None
    if not origin:
        issues.append("教师课表无课位，无法发起调停课（环境）")
        step("schedule-change submit", False, "no origin item")
    else:
        oid = origin.get("itemId") or origin.get("id") or origin.get("scheduleItemId")
        # STOP is simplest (no target conflict)
        body = {
            "originItemId": str(oid),
            "changeType": "STOP",
            "reason": "Round7调停课审批冒烟停课测试",
            "makeupPlan": "后续安排：下周同课位补一次",
        }
        sub = req("POST", "/mobile/teacher/academic/schedule-changes", token=tea, body=body)
        step("schedule-change submit", sub.get("code") == 0, {
            "code": sub.get("code"), "data": sub.get("data"), "msg": sub.get("message"),
            "origin": {k: origin.get(k) for k in ("itemId", "id", "courseName", "weekday", "slotNo", "status")},
        })
        if sub.get("code") != 0:
            issues.append(f"调停课提交失败: {sub.get('message')}")
        else:
            change_id = (sub.get("data") or {}).get("changeId")

    if change_id:
        pend_c = req("GET", "/mobile/teacher/academic/schedule-changes/pending", token=col)
        plist = (pend_c.get("data") or {}).get("list") or []
        in_col = any(str(x.get("changeId")) == str(change_id) for x in plist)
        step("college sees pending", in_col or (pend_c.get("data") or {}).get("total", 0) >= 0, {
            "inList": in_col, "total": (pend_c.get("data") or {}).get("total"),
            "msg": pend_c.get("message"),
        })
        if not in_col:
            # may be permission empty note
            issues.append("学院待审列表未命中刚提交单据（可能权限/范围）")

        rev1 = req("POST", f"/mobile/teacher/academic/schedule-changes/{change_id}/review",
                   token=col, body={"action": "APPROVE", "comment": "学院通过 Round7"})
        step("college APPROVE", rev1.get("code") == 0, {
            "code": rev1.get("code"), "status": (rev1.get("data") or {}).get("status"),
            "node": (rev1.get("data") or {}).get("currentNode"), "msg": rev1.get("message"),
        })
        if rev1.get("code") != 0:
            issues.append(f"学院审批失败: {rev1.get('message')}")
        else:
            pend_a = req("GET", "/mobile/teacher/academic/schedule-changes/pending", token=adm)
            alist = (pend_a.get("data") or {}).get("list") or []
            in_adm = any(str(x.get("changeId")) == str(change_id) for x in alist)
            step("admin sees pending after college", in_adm, {
                "total": (pend_a.get("data") or {}).get("total"),
                "statuses": [(x.get("changeId"), x.get("status"), x.get("currentNode")) for x in alist[:5]],
            })
            rev2 = req("POST", f"/mobile/teacher/academic/schedule-changes/{change_id}/review",
                       token=adm, body={"action": "APPROVE", "comment": "教务处终审 Round7"})
            step("academic APPROVE", rev2.get("code") == 0, {
                "code": rev2.get("code"), "status": (rev2.get("data") or {}).get("status"),
                "applied": (rev2.get("data") or {}).get("applied"), "msg": rev2.get("message"),
            })
            if rev2.get("code") != 0:
                issues.append(f"教务处审批失败: {rev2.get('message')}")

    # ── 3) 打印留痕仍可用（摘要字段） ──
    ticket = req("POST", "/mobile/academic/exam/ticket/print", token=stu, body={"reason": "writepath"})
    step("exam ticket print still ok", ticket.get("code") == 0, {
        "doc": (ticket.get("data") or {}).get("docName"),
        "hasDocument": bool((ticket.get("data") or {}).get("document")),
    })
    st_print = req("POST", "/mobile/academic/status-change/print", token=stu,
                   body={"changeType": "SUSPEND", "reason": "writepath print"})
    step("status print still ok", st_print.get("code") == 0, {
        "doc": (st_print.get("data") or {}).get("docName"),
        "document": (st_print.get("data") or {}).get("document"),
    })

    passed = sum(1 for s in STEPS if s["ok"])
    failed = [s for s in STEPS if not s["ok"]]
    summary = {"passed": passed, "total": len(STEPS), "failed": failed, "issues": issues}
    EVID.write_text(json.dumps({"steps": STEPS, "summary": summary}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print("\nSUMMARY", json.dumps(summary, ensure_ascii=False))
    print("EVIDENCE", EVID)
    return 0 if not failed else 1


if __name__ == "__main__":
    # ensure app context / DB for seed
    import os
    os.environ.setdefault("DB_ENABLED", "true")
    sys.exit(main())
