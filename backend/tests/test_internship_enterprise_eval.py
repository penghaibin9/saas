"""P2-B · 企业评价（五维评分校验 / 学校审核 / owner / 数据范围 / 来源可追溯 / 导出 / 学生403）。"""
from __future__ import annotations

TID = 1000000000000000001
INT = "/api/v1/internship"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student(sno, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(tid), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    ids = {}
    try:
        for no, name, adv, key in [("EE-A", "甲", "刘强", "a"), ("EE-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生",
                                 status="ONBOARD", risk_level="NONE")
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
        db.commit()
        return ids
    finally:
        db.close()


def _payload(iid, **over):
    p = {"internshipId": str(iid), "mentorName": "企业导师张三", "attendanceScore": 90,
         "skillScore": 85, "attitudeScore": 88, "collaborationScore": 92, "safetyScore": 95,
         "overallComment": "表现优秀", "recommendHire": True}
    p.update(over)
    return p


def test_create_review_flow(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    res = client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_a"]), headers=h)
    assert res.status_code == 200 and res.json()["data"]["source"] == "SCHOOL_RECORDED"
    eid = res.json()["data"]["id"]
    # 重复录入被拒
    assert client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_a"]), headers=h).status_code == 409
    # 详情：均分 = (90+85+88+92+95)/5 = 90
    detail = client.get(f"{INT}/enterprise-evals/{eid}", headers=h).json()["data"]
    assert detail["avgScore"] == 90.0 and detail["mentorName"] == "企业导师张三"
    # 审核通过
    ok = client.post(f"{INT}/enterprise-evals/{eid}/review", json={"action": "APPROVE"}, headers=h)
    assert ok.status_code == 200 and ok.json()["data"]["reviewStatus"] == "APPROVED"
    # 已审核再审 → 409
    assert client.post(f"{INT}/enterprise-evals/{eid}/review", json={"action": "APPROVE"}, headers=h).status_code == 409


def test_score_validation(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    # 超范围
    assert client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_a"], skillScore=150), headers=h).status_code == 400
    # 缺项
    p = _payload(ids["rec_a"]); del p["attitudeScore"]
    assert client.post(f"{INT}/enterprise-evals", json=p, headers=h).status_code == 400
    # 缺企业导师姓名
    p2 = _payload(ids["rec_a"], mentorName="")
    assert client.post(f"{INT}/enterprise-evals", json=p2, headers=h).status_code == 400


def test_return_requires_reason(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    eid = client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_a"]), headers=h).json()["data"]["id"]
    assert client.post(f"{INT}/enterprise-evals/{eid}/review", json={"action": "RETURN", "comment": "no"}, headers=h).status_code == 400
    ok = client.post(f"{INT}/enterprise-evals/{eid}/review", json={"action": "RETURN", "comment": "评分与实际不符请重填"}, headers=h)
    assert ok.status_code == 200 and ok.json()["data"]["reviewStatus"] == "RETURNED"


def test_owner_and_scope(client, db_mode):
    ids = _seed(db_mode)
    # 王芳学生 B
    bid = client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_b"]), headers=_mentor("王芳")).json()["data"]["id"]
    # 刘强越权审核 → 403
    assert client.post(f"{INT}/enterprise-evals/{bid}/review", json={"action": "APPROVE"}, headers=_mentor("刘强")).status_code == 403
    # 刘强录入自己学生
    client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_a"]), headers=_mentor("刘强"))
    assert client.get(f"{INT}/enterprise-evals", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/enterprise-evals", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    assert client.get(f"{INT}/enterprise-evals", headers=_student("EE-A")).status_code == 403
    assert client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_a"]), headers=_student("EE-A")).status_code == 403


def test_export(client, db_mode):
    ids = _seed(db_mode)
    client.post(f"{INT}/enterprise-evals", json=_payload(ids["rec_a"]), headers=_mentor("刘强"))
    res = client.post(f"{INT}/enterprise-evals/export", headers=_admin(client))
    assert res.status_code == 200 and res.json()["data"]["filename"].endswith(".xlsx")
    assert res.json()["data"]["rowCount"] == 1
