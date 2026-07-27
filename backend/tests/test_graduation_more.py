"""毕业设计中心 · Batch 6/7/8 闭环测试：
开题答辩(现场 PASS/FAIL，须书面已通过) + 开题/成果统计 + 成果互查整改(分配→互查→整改) +
答辩专家库(新增/停用) + 成绩申诉守卫(未发布不可申诉)。全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

STU = "/api/v1/students"
GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
PROP = "/api/v1/graduation/proposals"
PEER = "/api/v1/graduation/gd-peer-reviews"
EXPERT = "/api/v1/graduation/gd-defense-experts"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT", "tid": "demo",
        "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def _approved_proposal(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={"title": f"{name}题", "sourceType": "TEACHER",
                     "advisorName": "李老师", "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    sh = _stu_token(name)
    client.post(f"{MOBILE}/graduation/proposal", headers=sh,
                json={"background": "背景说明足够长", "plan": "研究方案足够长", "outcome": ""})
    pid = next(r for r in client.get(PROP, headers=h, params={"status": "PENDING_REVIEW"}).json()["data"]["items"]
               if r["studentName"] == name)["id"]
    client.post(f"{PROP}/{pid}/review", headers=h, json={"action": "APPROVE", "comment": "选题合理"})
    return gid, pid


def test_proposal_defense_and_stats(client, auth_headers, db_mode):
    h = auth_headers
    gid, pid = _approved_proposal(client, h, "PD1", "开题答辩生")

    ok = client.post(f"{PROP}/{pid}/defense", headers=h, json={"result": "PASS"})
    assert ok.json()["code"] == 0 and ok.json()["data"]["defenseResult"] == "PASS"

    detail = client.get(f"{PROP}/{pid}", headers=h).json()["data"]
    assert detail["defenseResult"] == "PASS"

    stats = client.get(f"{PROP}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1 and "byStatus" in stats
    fstats = client.get("/api/v1/graduation/finals/stats", headers=h).json()["data"]
    assert "byStatus" in fstats


def test_proposal_defense_requires_approved(client, auth_headers, db_mode):
    h = auth_headers
    sid = client.post(STU, headers=h, json={"studentNo": "PD2", "realName": "未批开题生", "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={"title": "未批开题生题", "sourceType": "TEACHER",
                     "advisorName": "李老师", "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    sh = _stu_token("未批开题生")
    client.post(f"{MOBILE}/graduation/proposal", headers=sh, json={"background": "背景足够长", "plan": "方案足够长"})
    pid = next(r for r in client.get(PROP, headers=h, params={"status": "PENDING_REVIEW"}).json()["data"]["items"]
               if r["studentName"] == "未批开题生")["id"]
    # 未书面通过前不可开题答辩
    bad = client.post(f"{PROP}/{pid}/defense", headers=h, json={"result": "PASS"})
    assert bad.json()["code"] != 0


def test_peer_review_flow(client, auth_headers, db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal

    h = auth_headers
    g1 = _gd_student(client, h, "PR1", "互查被评")
    g2 = _gd_student(client, h, "PR2", "互查评人")

    self_assign = client.post(f"{PEER}/assign", headers=h, json={"gdStudentId": g1, "reviewerGdStudentId": g1})
    assert self_assign.json()["code"] != 0  # 不能互查本人

    db = get_sessionmaker()()
    try:
        db.add(GraduationFinal(
            tenant_id=MAIN, gd_student_id=int(g1), final_type="定稿",
            version="v1", submit_at=datetime.utcnow(), status="APPROVED",
            plagiarism_rate="10.0%", plagiarism_status="已检测", attachments_json=[],
        ))
        db.commit()
    finally:
        db.close()

    a = client.post(f"{PEER}/assign", headers=h, json={"gdStudentId": g1, "reviewerGdStudentId": g2})
    pid = a.json()["data"]["id"]
    assert a.json()["data"]["status"] == "ASSIGNED"

    sub = client.post(f"{PEER}/{pid}/submit", headers=h, json={"opinion": "论文结构建议调整第三章"})
    assert sub.json()["data"]["status"] == "REVIEWED"

    rec = client.post(f"{PEER}/{pid}/rectify", headers=h, json={"note": "已按意见调整第三章结构"})
    assert rec.json()["data"]["status"] == "RECTIFIED"

    lst = client.get(PEER, headers=h, params={"gdStudentId": g1}).json()["data"]["items"]
    assert len(lst) == 1


def test_defense_expert_pool(client, auth_headers, db_mode):
    h = auth_headers
    e = client.post(EXPERT, headers=h, json={"expertName": "外聘王教授", "title": "教授",
                    "isExternal": True, "avoidNote": "回避本院学生"})
    eid = e.json()["data"]["id"]
    assert e.json()["data"]["isExternal"] is True

    dis = client.post(f"{EXPERT}/{eid}/status", headers=h, json={"action": "DISABLE"})
    assert dis.json()["data"]["status"] == "DISABLED"

    lst = client.get(EXPERT, headers=h, params={"status": "DISABLED"}).json()["data"]["items"]
    assert any(x["id"] == eid for x in lst)


def test_grade_appeal_requires_published(client, auth_headers, db_mode):
    h = auth_headers
    _gd_student(client, h, "AP1", "申诉生")
    sh = _stu_token("申诉生")
    # 成绩未发布不可申诉
    res = client.post(f"{MOBILE}/graduation/grade/appeal", headers=sh, json={"reason": "对答辩分有异议请复核"})
    assert res.json()["code"] != 0
