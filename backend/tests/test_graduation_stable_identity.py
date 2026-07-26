"""第4批：稳定 mentor_id 身份隔离（同名不串权 / SoD 比 ID）。"""
from __future__ import annotations

from conftest import make_org_class

import uuid

from app.core.context import set_current_user
from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.models import GraduationDefenseGroup, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import can_access_student
from app.modules.graduation.services import graduation_identity as gid

DG = "/api/v1/graduation/defense-groups"
GD_STU = "/api/v1/graduation/gd-students"
GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_REVIEW = "/api/v1/graduation/gd-reviews"
STU = "/api/v1/students"
BATCH = "/api/v1/graduation/batches"
MAIN = 1000000000000000001


def _uniq(prefix="B4"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch(client, h):
    return client.post(BATCH, headers=h, json={
        "batchName": _uniq("批"), "batchNo": _uniq("BN"),
        "gradeYear": "2026届", "plannedCount": 20,
    }).json()["data"]["id"]


def _mentor(client, h, teacher_no, teacher_name="张伟"):
    mid = client.post(GD_MENTOR, headers=h, json={
        "teacherNo": teacher_no, "teacherName": teacher_name, "maxCapacity": 8,
    }).json()["data"]["id"]
    client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    return mid


def _role_headers(role, real_name, login_name):
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{login_name}", "realName": real_name, "loginName": login_name,
        "userType": "TEACHER", "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "WEB",
    })}


def test_defense_group_writes_mentor_ids(client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(client, h)
    chair_id = _mentor(client, h, _uniq("T-CH"), "组长甲")
    sec_id = _mentor(client, h, _uniq("T-SE"), "秘书甲")
    m1 = _mentor(client, h, _uniq("T-M1"), "评委甲")
    m2 = _mentor(client, h, _uniq("T-M2"), "评委乙")
    r = client.post(DG, headers=h, params={"batchId": bid}, json={
        "groupName": _uniq("组"), "batchId": bid, "location": "A101",
        "chairMentorId": int(chair_id), "secretaryMentorId": int(sec_id),
        "memberMentorIds": [int(m1), int(m2)],
    })
    assert r.json()["code"] == 0, r.json()
    data = r.json()["data"]
    assert data["chairMentorId"] == str(chair_id)
    assert data["secretaryMentorId"] == str(sec_id)
    assert data["chair"] == "组长甲"
    assert data["secretary"] == "秘书甲"
    mids = {str(x.get("mentorId")) for x in data["members"]}
    assert str(m1) in mids and str(m2) in mids


def test_same_name_defense_expert_isolated_by_mentor_id(client, auth_headers, db_mode):
    """同名张伟 A/B：仅组内 mentor_id 对应工号可访问学生。"""
    h = auth_headers
    bid = _batch(client, h)
    no_a, no_b = _uniq("TA"), _uniq("TB")
    mid_a = _mentor(client, h, no_a, "张伟")
    mid_b = _mentor(client, h, no_b, "张伟")
    grp = client.post(DG, headers=h, params={"batchId": bid}, json={
        "groupName": _uniq("同名组"), "batchId": bid, "location": "B201",
        "chairMentorId": int(mid_a), "memberMentorIds": [],
        "secretary": "秘书",
    }).json()["data"]
    sid = client.post(STU, headers=h, json={"studentNo": _uniq("S"), "realName": "生同名", "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]

    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gid))
        stu.defense_group_id = int(grp["id"])
        stu.stage = "DEFENSE"
        db.commit()
        group = db.get(GraduationDefenseGroup, int(grp["id"]))
        assert group.chair_mentor_id == int(mid_a)

        set_current_user({
            "currentRoleCode": "GD_DEFENSE_EXPERT", "userType": "TEACHER",
            "realName": "张伟", "loginName": no_a, "tenantId": MAIN,
        })
        assert can_access_student(db, stu) is True

        set_current_user({
            "currentRoleCode": "GD_DEFENSE_EXPERT", "userType": "TEACHER",
            "realName": "张伟", "loginName": no_b, "tenantId": MAIN,
        })
        assert can_access_student(db, stu) is False
    finally:
        set_current_user(None)
        db.close()


def test_sod_review_uses_mentor_id_not_same_name(client, auth_headers, db_mode):
    """A 为指导老师时：同名 B 可评阅；A 本人不可评阅。"""
    h = auth_headers
    bid = _batch(client, h)
    no_a, no_b = _uniq("RA"), _uniq("RB")
    mid_a = _mentor(client, h, no_a, "李华")
    mid_b = _mentor(client, h, no_b, "李华")
    sid = client.post(STU, headers=h, json={"studentNo": _uniq("S"), "realName": "生SoD", "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]
    # 绑定指导老师 A
    assign = client.post("/api/v1/graduation/gd-mentor-assignments/assign", headers=h, json={
        "gdStudentId": gid, "mentorId": mid_a, "reason": "第4批同名SoD测试",
    })
    if assign.status_code >= 400 or assign.json().get("code", 0) != 0:
        db = get_sessionmaker()()
        try:
            stu = db.get(GraduationStudent, int(gid))
            stu.mentor_id = int(mid_a)
            stu.advisor_name = "李华"
            db.commit()
        finally:
            db.close()

    blocked = client.post(f"{GD_REVIEW}/assign", headers=h, json={
        "gdStudentId": str(gid), "reviewerMentorId": int(mid_a),
    })
    assert blocked.json()["code"] != 0, blocked.json()
    assert "指导教师" in (blocked.json().get("message") or "")

    ok = client.post(f"{GD_REVIEW}/assign", headers=h, json={
        "gdStudentId": str(gid), "reviewerMentorId": int(mid_b),
    })
    assert ok.json()["code"] == 0, ok.json()
    assert ok.json()["data"]["reviewerMentorId"] == str(mid_b)
    assert ok.json()["data"]["reviewerName"] == "李华"


def test_identity_helpers_normalize_members():
    assert gid.normalize_member("张三")["name"] == "张三"
    assert gid.normalize_member({"mentorId": 9, "name": "李四"})["mentorId"] == "9"
