# -*- coding: utf-8 -*-
"""SA 交付缺口 1-7 冒烟：mobile 困难/奖助写口、续假、门户宿舍、老师宿舍待办。"""
from __future__ import annotations

PORTAL = "/api/v1/portal/affairs"
MB = "/api/v1/mobile"
BASE = "/api/v1/student-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no, client_type="MP"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": client_type})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    zhang = StudentProfile(tenant_id=TID, student_no="SA17MB01", real_name="收口张", class_id=a.id,
                           gender="M", current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(zhang); db.flush()
    ids = {"zhang": zhang.id}
    db.commit(); db.close()
    return ids


def test_mobile_aid_funding_apply_guards_and_portal_dorm(client, db_mode):
    _seed(db_mode)
    h = _stu_token("收口张", "SA17MB01")
    assert client.get(f"{MB}/affairs/aid/batches", headers=h).json()["code"] == 0
    assert client.get(f"{MB}/affairs/funding/batches", headers=h).json()["code"] == 0
    assert client.post(f"{MB}/affairs/aid/apply", headers=h, json={
        "batchId": "1", "applyLevel": "GENERAL", "statement": "家庭经济困难情况说明"
    }).json()["code"] != 0
    assert client.post(f"{MB}/affairs/funding/apply", headers=h, json={
        "batchId": "1", "statement": "申请奖学金理由说明"
    }).json()["code"] != 0
    d = client.get(f"{PORTAL}/dorm", headers=_stu_token("收口张", "SA17MB01", "PC")).json()
    assert d["code"] == 0 and "hasBed" in d["data"] and "myBed" in d["data"]


def test_mobile_and_portal_leave_extend_self(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    lid = client.post(f"{BASE}/leave", headers=admin, json={
        "studentId": str(ids["zhang"]), "leaveType": "PERSONAL",
        "startTime": "2026-06-01", "endTime": "2026-06-02", "reason": "回家有事"
    }).json()["data"]["id"]
    client.post(f"{BASE}/leave/{lid}/approve", headers=admin)
    h = _stu_token("收口张", "SA17MB01")
    mine = client.get(f"{MB}/affairs/leave/my", headers=h).json()["data"]["items"]
    assert mine and mine[0]["canExtend"] is True
    r = client.post(f"{MB}/affairs/leave/{lid}/extension", headers=h, json={
        "newEndTime": "2026-06-05", "reason": "因病需要续假"
    }).json()
    assert r["code"] == 0, r
    mine2 = client.get(f"{MB}/affairs/leave/my", headers=h).json()["data"]["items"]
    assert mine2[0]["status"] == "EXTENSION_REVIEW"
    assert mine2[0]["canExtend"] is False
    # 门户续假入口存在（当前已在续假审，再次提交应业务冲突）
    hp = _stu_token("收口张", "SA17MB01", "PC")
    again = client.post(f"{PORTAL}/leave/{lid}/extension", headers=hp, json={
        "newEndTime": "2026-06-06", "reason": "再次续假测试"
    }).json()
    assert again["code"] != 0


def test_teacher_dorm_pending(client, db_mode):
    h = _hdr(client, "counselor01")
    r = client.get(f"{MB}/teacher/affairs/dorm/pending", headers=h).json()
    assert r["code"] == 0
    assert "transfers" in r["data"] and "exceptions" in r["data"]
