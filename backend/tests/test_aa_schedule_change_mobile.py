"""教务中心 · 移动端调停课（新聚合 affairs_academic_my_schedule + submit/cancel/conflict-check
包装 + get_change 归属校验补丁）。全部经 HTTP client 走真库(db_mode)。PC 端既有
test_aa_schedule_change.py 已覆盖 submit/cancel/conflict_check 本身的越权拦截；本文件专门覆盖
移动端「我的课表」选课位聚合（此前无测试覆盖）、移动端提交/撤销全链路，以及移动端在
get_change 上新补的归属校验（PC 端 get_change 本身完全没有归属校验，这是移动端主动收紧）。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2801", grade="2028", status="ACTIVE")
    db.add(a); db.flush()
    ids = {"class": a.id}
    db.commit(); db.close()
    return ids


def _batch(client, hdr):
    return client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": "1"}).json()["data"]["batchId"]


def _item(client, hdr, bid, class_id, **kw):
    body = {"weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
            "teacherKey": "academic01", "teacherName": "赵敏", "classId": str(class_id),
            "className": "软件2801", "classroom": "A101", "courseName": "高等数学", **kw}
    return client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body).json()["data"]["itemId"]


def _published_item(client, hdr, cid, teacher_key="academic01", teacher_name="赵敏"):
    bid = _batch(client, hdr)
    origin = _item(client, hdr, bid, cid, teacherKey=teacher_key, teacherName=teacher_name)
    client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    return bid, origin


def test_my_schedule_via_mobile(client, db_mode):
    """「我的课表」聚合（供选原课位，此前完全没有测试经由 mobile 路径覆盖）：academic01
    可见自己的课位，self_key 推导（userId 优先/无则 loginName）与 PC 端「查看本人课表」同口径。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])

    r = client.get(f"{MOB}/teacher/academic/schedule/mine", headers=_hdr(client, "academic01")).json()
    assert r["code"] == 0
    assert any(i["itemId"] == origin for i in r["data"]["items"])


def test_conflict_check_and_submit_flow_via_mobile(client, db_mode):
    """预检无冲突 → 提交成功 → 台账列表可见；预检与提交共用同一归属校验口径。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    hdr = _hdr(client, "academic01")

    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    chk = client.post(f"{MOB}/teacher/academic/schedule-changes/conflict-check", headers=hdr, json=body).json()
    assert chk["code"] == 0 and chk["data"]["conflict"] is None

    sub = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body)
    assert sub.status_code == 200 and sub.json()["data"]["status"] == "SUBMITTED"
    change_id = sub.json()["data"]["changeId"]

    lst = client.get(f"{MOB}/teacher/academic/schedule-changes", headers=hdr).json()["data"]["list"]
    assert any(c["changeId"] == change_id for c in lst)


def test_cancel_flow_via_mobile(client, db_mode):
    """SUBMITTED 状态下移动端可撤销 → CANCELLED。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    hdr = _hdr(client, "academic01")
    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    change_id = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body).json()["data"]["changeId"]

    r = client.post(f"{MOB}/teacher/academic/schedule-changes/{change_id}/cancel", headers=hdr,
                    json={"reason": "计划变更"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "CANCELLED"


def test_cross_scope_submit_403_via_mobile(client, db_mode):
    """越权：非本人课位发起调停课 → 403 NO_DATA_SCOPE（复用 PC submit 内部范围校验）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"], teacher_key="other_teacher", teacher_name="他人")
    hdr = _hdr(client, "academic01")
    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    r = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body)
    assert r.status_code == 403


def test_detail_ownership_guard_via_mobile(client, db_mode):
    """移动端新补的 get_change 归属校验：本人可查自己的单据详情；无关教师查他人单据详情 → 403
    （PC 端 get_change 本身对此完全没有校验，这是移动端主动收紧，不改 PC 行为）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _, origin = _published_item(client, admin, ids["class"])
    hdr = _hdr(client, "academic01")
    body = {"originItemId": str(origin), "changeType": "ADJUST", "reason": "教师因公出差需调整",
            "targetWeekday": 3, "targetSlotNo": 2}
    change_id = client.post(f"{MOB}/teacher/academic/schedule-changes", headers=hdr, json=body).json()["data"]["changeId"]

    ok = client.get(f"{MOB}/teacher/academic/schedule-changes/{change_id}", headers=hdr)
    assert ok.status_code == 200 and ok.json()["data"]["changeId"] == change_id

    other_hdr = _hdr(client, "teacher01")
    forbidden = client.get(f"{MOB}/teacher/academic/schedule-changes/{change_id}", headers=other_hdr)
    assert forbidden.status_code == 403
