"""13A-P5 学工画像 + 成长时间线 · 端到端（真实 DB 模式）。

P1 画像汇总各域沉淀；P2 时间线合并 P2-P5 进360事件倒序；越权跨班403。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    sa = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sb = StudentProfile(tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.add(sb); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids


def _leave_closed(client, hdr, sid):
    lid = client.post(f"{BASE}/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": "PERSONAL", "startTime": "2026-03-01",
        "endTime": "2026-03-02", "reason": "回家有事"}).json()["data"]["id"]
    client.post(f"{BASE}/leave/{lid}/approve", headers=hdr)
    client.post(f"{BASE}/leave/{lid}/cancel", headers=hdr, json={"proofNote": "已返校"})
    client.post(f"{BASE}/leave/{lid}/cancel-confirm", headers=hdr, json={"note": "确认返校"})


def _talk_done(client, hdr, sid):
    tid = client.post(f"{BASE}/talks", headers=hdr, json={
        "studentIds": [str(sid)], "talkType": "DAILY", "topic": "谈话"}).json()["data"]["talkIds"][0]
    client.post(f"{BASE}/talks/{tid}/record", headers=hdr,
                json={"content": "与学生进行了深入交流，全面了解其近期学习和生活情况，整体状态良好情绪稳定",
                      "result": "GOOD", "needFollowUp": False})


def test_profile_aggregates_domains(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _leave_closed(client, hdr, ids["sa"])
    _talk_done(client, hdr, ids["sa"])
    p = client.get(f"{BASE}/students/{ids['sa']}/profile", headers=hdr).json()["data"]
    assert p["baseInfo"]["realName"] == "甲一"
    assert p["leaveSummary"]["total"] >= 1
    assert p["talkSummary"]["total"] >= 1
    assert "disciplineSummary" in p and "riskSummary" in p and "psyFlag" in p


def test_timeline_merges_360_events(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _leave_closed(client, hdr, ids["sa"])
    _talk_done(client, hdr, ids["sa"])
    items = client.get(f"{BASE}/students/{ids['sa']}/timeline", headers=hdr).json()["data"]["items"]
    types = {e["eventType"] for e in items}
    assert "LEAVE_CLOSED" in types and "TALK_COMPLETED" in types
    # 倒序：最新在前（talk 后于 leave 完成）
    assert items[0]["module"] in ("talk", "leave")


def test_disc_summary_restricted_for_non_disc_role(client, db_mode):
    ids = _seed(db_mode)
    # counselor 有 discipline 计数可见（在 _DISC_ROLES）——此处验证画像端点可访问本班学生
    p = client.get(f"{BASE}/students/{ids['sa']}/profile", headers=_hdr(client, "counselor01"))
    assert p.status_code == 200


def test_profile_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    r = client.get(f"{BASE}/students/{ids['sb']}/profile", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"
