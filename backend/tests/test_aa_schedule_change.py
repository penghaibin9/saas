"""13B-R2 调停课 · 端到端（SM-08 调课/停课/补课）。

C1 调课全链路：提交→学院审→教务处审→APPLIED，原课位 CHANGED + 生成新项(回链)；
C2 提交即目标冲突预检 → 409 单据不落库；C3 停课未填补课安排 → 400；
C4 撤销仅限终审前(SUBMITTED/COLLEGE_REVIEW)，APPLIED 后撤销 → 409；
C5 越权：学生令牌 → 403；C6 数据范围(COURSE)：非本人课位发起 → 403 NO_DATA_SCOPE；
C7 驳回需原因≥5 字 → REJECTED。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="SC001", real_name="课表甲", class_id=a.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"class": a.id, "student": s.id}
    db.commit(); db.close()
    return ids


def _batch(client, hdr):
    return client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": "1"}).json()["data"]["batchId"]


def _item(client, hdr, bid, class_id, **kw):
    body = {"weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
            "teacherKey": "academic01", "teacherName": "赵敏", "classId": str(class_id),
            "className": "软件2601", "classroom": "A101", "courseName": "高等数学", **kw}
    return client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body).json()["data"]["itemId"]


def _published_item(client, hdr, cid, **extra_items):
    """建批次 + 排 1 节课 + 发布，返回 (batchId, originItemId)。extra_items 可再排额外课位占位。"""
    bid = _batch(client, hdr)
    origin = _item(client, hdr, bid, cid)
    for kw in extra_items.get("extra", []):
        _item(client, hdr, bid, cid, **kw)
    client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    return bid, origin


def _submit(client, hdr, origin, **kw):
    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2, **kw}
    return client.post(f"{BASE}/schedule-change", headers=hdr, json=body)


# ── C1 调课全链路 → APPLIED ──
def test_c1_adjust_full_chain_applied(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    r = _submit(client, admin, origin)
    assert r.status_code == 200
    cid = r.json()["data"]["changeId"]
    assert r.json()["data"]["status"] == "SUBMITTED"
    # 学院审通过 → COLLEGE_REVIEW（待教务处审）
    r1 = client.post(f"{BASE}/schedule-change/{cid}/approve", headers=admin, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "COLLEGE_REVIEW"
    # 教务处终审通过 → 系统改写课表 → APPLIED
    r2 = client.post(f"{BASE}/schedule-change/{cid}/approve", headers=admin, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "APPLIED"
    assert r2["data"]["newItemId"] and r2["data"]["applied"]["notified"]["channel"] == "STATUS_CHANGED"
    # 原课位 CHANGED（原周1第1节不再出现在生效课表），新项落到目标周3第2节
    cv = client.get(f"{BASE}/schedule-batches/{r2['data']['batchId']}/class-view?classId={ids['class']}",
                    headers=admin).json()["data"]["items"]
    slots = {(i["weekday"], i["slotNo"]) for i in cv}
    assert (3, 2) in slots and (1, 1) not in slots


# ── C2 提交即目标冲突预检 → 409，单据不落库 ──
def test_c2_conflict_precheck_rejected(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 额外占位：周3第2节已被同教师占用
    _, origin = _published_item(client, admin, ids["class"],
                                extra=[{"weekday": 3, "slotNo": 2}])
    r = _submit(client, admin, origin, targetWeekday=3, targetSlotNo=2)
    assert r.status_code == 409 and "冲突" in r.json()["message"]
    # 台账中无该单据（未落库）
    lst = client.get(f"{BASE}/schedule-change", headers=admin).json()["data"]
    assert lst["total"] == 0


# ── C3 停课未填补课安排 → 400 ──
def test_c3_stop_requires_makeup(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    r = client.post(f"{BASE}/schedule-change", headers=admin,
                    json={"originItemId": str(origin), "changeType": "STOP", "reason": "教室设备故障停课"})
    assert r.status_code == 400
    # 补齐补课安排后可提交
    r2 = client.post(f"{BASE}/schedule-change", headers=admin,
                     json={"originItemId": str(origin), "changeType": "STOP",
                           "reason": "教室设备故障停课", "makeupPlan": "顺延至第10周补齐"})
    assert r2.status_code == 200 and r2.json()["data"]["changeType"] == "STOP"


# ── C4 撤销仅限终审前；APPLIED 后 409 ──
def test_c4_cancel_window(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    cid = _submit(client, admin, origin).json()["data"]["changeId"]
    # SUBMITTED 可撤销
    rc = client.post(f"{BASE}/schedule-change/{cid}/cancel", headers=admin, json={"reason": "自行取消"}).json()
    assert rc["data"]["status"] == "CANCELLED"
    # 另一单走到 APPLIED 后撤销 → 409
    cid2 = _submit(client, admin, origin).json()["data"]["changeId"]
    client.post(f"{BASE}/schedule-change/{cid2}/approve", headers=admin, json={"action": "APPROVE"})
    client.post(f"{BASE}/schedule-change/{cid2}/approve", headers=admin, json={"action": "APPROVE"})
    r409 = client.post(f"{BASE}/schedule-change/{cid2}/cancel", headers=admin, json={"reason": "晚了"})
    assert r409.status_code == 409


# ── C5 越权：学生令牌 → 403 ──
def test_c5_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    stu = _hdr(client, "student01")
    r = _submit(client, stu, origin)
    assert r.status_code == 403
    assert client.get(f"{BASE}/schedule-change", headers=stu).status_code == 403


# ── C6 数据范围(COURSE)：非本人课位发起 → 403 NO_DATA_SCOPE ──
def test_c6_course_scope_denied(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    # 课位教师为 other_teacher，非 academic01
    origin = _item(client, admin, bid, ids["class"], teacherKey="other_teacher", teacherName="他人")
    client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=admin)
    teacher = _hdr(client, "academic01")   # ACADEMIC_TEACHER：COURSE 范围，仅本人课位
    r = _submit(client, teacher, origin)
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


# ── C7 驳回需原因≥5 字 → REJECTED ──
def test_c7_reject_requires_reason(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    cid = _submit(client, admin, origin).json()["data"]["changeId"]
    short = client.post(f"{BASE}/schedule-change/{cid}/reject", headers=admin, json={"action": "REJECT", "comment": "不行"})
    assert short.status_code == 400
    ok = client.post(f"{BASE}/schedule-change/{cid}/reject", headers=admin,
                     json={"action": "REJECT", "comment": "目标时段与全校统考冲突，不予调整"}).json()
    assert ok["data"]["status"] == "REJECTED"
