# -*- coding: utf-8 -*-
"""SA 交付缺口 1-7 冒烟：mobile 困难/奖助写口、续假、门户宿舍、老师宿舍待办。"""
from __future__ import annotations

PORTAL = "/api/v1/portal/affairs"
MB = "/api/v1/mobile"
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
    from datetime import datetime

    from app.db.session import get_sessionmaker
    from app.models import CsLeave, SchoolClass, StudentProfile, User

    db = get_sessionmaker()()
    counselor = db.query(User).filter(
        User.tenant_id == TID,
        User.login_name == "counselor01",
    ).first()
    if counselor is None:
        counselor = User(
            tenant_id=TID,
            login_name="counselor01",
            real_name="王莉",
            password_hash="test-hash",
            user_type="TEACHER",
            status="ACTIVE",
        )
        db.add(counselor)
        db.flush()
    else:
        counselor.status = "ACTIVE"
        counselor.is_deleted = False

    a = SchoolClass(
        tenant_id=TID,
        major_id=1,
        class_name="软件2101",
        grade="2021",
        counselor_id=counselor.id,
        status="ACTIVE",
    )
    db.add(a)
    db.flush()
    zhang = StudentProfile(
        tenant_id=TID,
        student_no="SA17MB01",
        real_name="收口张",
        class_id=a.id,
        gender="M",
        current_stage="ON_CAMPUS",
        student_status="REGISTERED",
        status="ACTIVE",
    )
    db.add(zhang)
    db.flush()

    # SA17 验证的是“学生本人续假”渠道合同，不重复构造初次请假三级审批链。
    # 直接种一条已通过请假事实；续假仍走真实服务，真实解析班级辅导员并创建待办。
    start = datetime(2027, 6, 1)
    end = datetime(2027, 6, 2)
    leave = CsLeave(
        tenant_id=TID,
        code="SA17-LV-001",
        student_id=zhang.id,
        leave_type="PERSONAL",
        start_time=start,
        end_time=end,
        days=1,
        reason="家庭事务请假",
        status="APPROVED",
        affairs_status="APPROVED",
        apply_time=datetime.utcnow(),
        expected_return_at=end,
    )
    db.add(leave)
    db.flush()
    ids = {"zhang": int(zhang.id), "leave": int(leave.id)}
    db.commit()
    db.close()
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
    lid = ids["leave"]
    h = _stu_token("收口张", "SA17MB01")
    mine = client.get(f"{MB}/affairs/leave/my", headers=h).json()["data"]["items"]
    assert mine and mine[0]["leaveId"] == str(lid)
    assert "SUBMIT_EXTENSION" in mine[0]["allowedActions"]
    r = client.post(f"{MB}/affairs/leave/{lid}/extension", headers=h, json={
        "newEndTime": "2027-06-05", "reason": "因病需要续假"
    }).json()
    assert r["code"] == 0, r
    mine2 = client.get(f"{MB}/affairs/leave/my", headers=h).json()["data"]["items"]
    assert mine2[0]["status"] == "EXTENSION_REVIEW"
    assert "SUBMIT_EXTENSION" not in mine2[0]["allowedActions"]
    # 门户续假入口存在（当前已在续假审，再次提交应业务冲突）
    hp = _stu_token("收口张", "SA17MB01", "PC")
    again = client.post(f"{PORTAL}/leave/{lid}/extension", headers=hp, json={
        "newEndTime": "2027-06-06", "reason": "再次续假测试"
    }).json()
    assert again["code"] != 0


def test_teacher_dorm_pending(client, db_mode):
    h = _hdr(client, "counselor01")
    r = client.get(f"{MB}/teacher/affairs/dorm/pending", headers=h).json()
    assert r["code"] == 0
    assert "transfers" in r["data"] and "exceptions" in r["data"]
