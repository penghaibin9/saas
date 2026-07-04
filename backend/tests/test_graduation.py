"""毕业设计域测试：学生/选题/开题批阅闭环/成果批阅/答辩发布（冲突拒绝）+ 看板 + 审计。"""
from __future__ import annotations

from datetime import datetime

MAIN_TID = 1000000000000000001


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (GraduationDefenseGroup, GraduationFinal, GraduationProposal,
                            GraduationStudent, GraduationTopic)
    db = get_sessionmaker()()
    try:
        s = GraduationStudent(tenant_id=MAIN_TID, name="毕设甲", student_no="S2026-999001",
                              class_id="c-2301", class_name="软件2301", topic_title="课题A",
                              advisor_name="王芳", stage="TASKBOOK_CONFIRM", risk_level="LOW",
                              phone_encrypted="13612349999")
        db.add(s)
        db.flush()
        p = GraduationProposal(tenant_id=MAIN_TID, gd_student_id=s.id, version="v1", submit_at=datetime.utcnow(),
                               background="bg", plan="plan", outcome="out", status="PENDING_REVIEW")
        f = GraduationFinal(tenant_id=MAIN_TID, gd_student_id=s.id, final_type="定稿", version="v3",
                            submit_at=datetime.utcnow(), plagiarism_rate="12.6%", plagiarism_status="达标",
                            status="PENDING_REVIEW")
        db.add(GraduationTopic(tenant_id=MAIN_TID, title="选题A", source="教师申报", advisor_name="王芳",
                               major_name="软件技术", capacity=2, selected=1, status="CONFIRMED"))
        gok = GraduationDefenseGroup(tenant_id=MAIN_TID, group_name="第1组", defense_date="2026-07-08 09:00",
                                     location="B401", chair="周正邦（教授）", members_json=["孙晓梅"],
                                     secretary="林小婉", student_count=10, conflict=None, published=False)
        gbad = GraduationDefenseGroup(tenant_id=MAIN_TID, group_name="第2组", defense_date="2026-07-08 14:00",
                                      location="B402", chair="王芳", members_json=["王芳"], secretary="孙晓梅",
                                      student_count=8, conflict="评委含指导教师本人", published=False)
        db.add_all([p, f, gok, gbad])
        db.commit()
        return {"student": s.id, "proposal": p.id, "final": f.id, "gok": gok.id, "gbad": gbad.id}
    finally:
        db.close()


def test_students_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/graduation/students", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["stageLabel"] == "任务书确认"
    det = client.get(f"/api/v1/graduation/students/{ids['student']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["proposals"]) == 1 and len(det["data"]["finals"]) == 1


def test_topics(client, auth_headers, db_mode):
    _seed(db_mode)
    lst = client.get("/api/v1/graduation/topics", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["statusLabel"] == "已确认"


def test_proposal_review_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    # 驳回需原因≥5字
    bad = client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                      json={"action": "REJECT", "comment": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                     json={"action": "APPROVE", "comment": ""}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    # 通过后学生阶段推进 GUIDING
    det = client.get(f"/api/v1/graduation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["stage"] == "GUIDING"
    # 重复批阅 409
    dup = client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                      json={"action": "APPROVE"}).json()
    assert dup["code"] == 409001


def test_final_review(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    ok = client.post(f"/api/v1/graduation/finals/{ids['final']}/review", headers=auth_headers,
                     json={"action": "APPROVE"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"


def test_defense_publish_conflict(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    # 冲突组不可发布
    bad = client.post(f"/api/v1/graduation/defense-groups/{ids['gbad']}/publish", headers=auth_headers).json()
    assert bad["code"] == 422001 and "冲突" in bad["message"]
    # 完整组可发布
    ok = client.post(f"/api/v1/graduation/defense-groups/{ids['gok']}/publish", headers=auth_headers).json()
    assert ok["code"] == 0 and ok["data"]["published"] is True
    lst = client.get("/api/v1/graduation/defense-groups", headers=auth_headers).json()
    pub = [g for g in lst["data"]["items"] if g["id"] == str(ids["gok"])][0]
    assert pub["published"] is True


def test_dashboard_and_audit(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    dash = client.get("/api/v1/graduation/dashboard", headers=auth_headers).json()
    assert dash["code"] == 0 and any(s["label"] == "毕设学生" for s in dash["data"]["stats"])
    client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                json={"action": "APPROVE"})
    au = client.get("/api/v1/graduation/audit-logs?bizType=PROPOSAL", headers=auth_headers).json()
    assert au["code"] == 0 and au["data"]["total"] >= 1


def test_requires_login(client):
    assert client.get("/api/v1/graduation/dashboard").json()["code"] == 401001
