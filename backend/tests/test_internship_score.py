"""P2-D · 实习成绩五项权重（权重和=100 / 计算正确 / 缺项不能发布 / 复核发布留痕 / 非法发布拒 / 数据范围 / 企业分自动取数）。"""
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
    from uuid import uuid4

    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    ids = {}
    try:
        b = InternshipBatch(tenant_id=TID, batch_name="成绩测试批次",
                            batch_no=f"SCOREB-{uuid4().hex[:8]}", status="RUNNING", planned_count=5)
        db.add(b); db.flush()
        ids["batch"] = b.id
        for no, name, adv, key in [("SC-A", "甲", "刘强", "a"), ("SC-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生",
                                 status="ONBOARD", risk_level="NONE", batch_id=b.id)
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
        db.commit()
        return ids
    finally:
        db.close()


def _cfg100(client):
    # 权重 20/20/10/30/20 = 100
    return client.post(f"{INT}/scores/config", json={"checkinWeight": 20, "weeklyWeight": 20,
                       "monthlyWeight": 10, "enterpriseWeight": 30, "schoolWeight": 20, "passLine": 60},
                       headers=_admin(client))


def test_config_weight_sum_must_be_100(client, db_mode):
    _seed(db_mode)
    bad = client.post(f"{INT}/scores/config", json={"checkinWeight": 20, "weeklyWeight": 20,
                      "monthlyWeight": 10, "enterpriseWeight": 30, "schoolWeight": 30}, headers=_admin(client))
    assert bad.status_code == 400
    assert _cfg100(client).status_code == 200
    cfg = client.get(f"{INT}/scores/config", headers=_admin(client)).json()["data"]
    assert cfg["enterpriseWeight"] == 30 and cfg["passLine"] == 60 and cfg["configId"]


def test_score_keeps_configuration_snapshot_and_mentor_cannot_change_config(client, db_mode):
    ids = _seed(db_mode)
    first = _cfg100(client).json()["data"]
    denied = client.post(f"{INT}/scores/config", json={"checkinWeight": 20, "weeklyWeight": 20,
                         "monthlyWeight": 10, "enterpriseWeight": 30, "schoolWeight": 20},
                         headers=_mentor("刘强"))
    assert denied.status_code == 403
    computed = client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_a"]),
                           "checkinScore": 80, "weeklyScore": 80, "monthlyScore": 80,
                           "enterpriseScore": 80, "schoolScore": 80}, headers=_mentor("刘强")).json()["data"]
    assert computed["total"] == 80.0
    second = client.post(f"{INT}/scores/config", json={"checkinWeight": 10, "weeklyWeight": 10,
                         "monthlyWeight": 10, "enterpriseWeight": 40, "schoolWeight": 30, "passLine": 60},
                         headers=_admin(client)).json()["data"]
    assert second["configId"] != first["configId"]
    detail = client.get(f"{INT}/scores/{computed['id']}", headers=_mentor("刘强")).json()["data"]
    assert detail["scoreConfigId"] == first["configId"] and detail["scoreConfigVersion"] >= 1


def test_compute_correct_and_publish(client, db_mode):
    ids = _seed(db_mode)
    _cfg100(client)
    h = _mentor("刘强")
    # 全项：checkin90 weekly80 monthly70 enterprise60 school100 → (90*20+80*20+70*10+60*30+100*20)/100 = 79.0
    c = client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_a"]), "checkinScore": 90,
                    "weeklyScore": 80, "monthlyScore": 70, "enterpriseScore": 60, "schoolScore": 100}, headers=h)
    assert c.status_code == 200
    data = c.json()["data"]
    assert data["total"] == 79.0 and data["incomplete"] is False and data["isPass"] is True
    sid = data["id"]
    # 发布
    pub = client.post(f"{INT}/scores/{sid}/publish", headers=h)
    assert pub.status_code == 200 and pub.json()["data"]["status"] == "PUBLISHED"
    # 复核/发布留痕
    detail = client.get(f"{INT}/scores/{sid}", headers=h).json()["data"]
    assert {"COMPUTE", "PUBLISH"} <= {t["action"] for t in detail["auditTrail"]}
    # 非法发布拒：已发布再发布 → 409
    assert client.post(f"{INT}/scores/{sid}/publish", headers=h).status_code == 409


def test_incomplete_cannot_publish(client, db_mode):
    ids = _seed(db_mode)
    _cfg100(client)
    h = _mentor("刘强")
    # 缺 monthly + enterprise（无企业评价自动取数）
    c = client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_a"]), "checkinScore": 90,
                    "weeklyScore": 80, "schoolScore": 100}, headers=h)
    assert c.status_code == 200 and c.json()["data"]["incomplete"] is True
    sid = c.json()["data"]["id"]
    # 缺项不能发布 → 409
    assert client.post(f"{INT}/scores/{sid}/publish", headers=h).status_code == 409


def test_enterprise_score_auto_from_eval(client, db_mode):
    import io
    ids = _seed(db_mode)
    _cfg100(client)
    h = _mentor("刘强")
    # 学校代录企业评价须绑定纸质评价扫描件
    up = client.post("/api/v1/files/upload", headers=h,
                     files={"file": ("eval.txt", io.BytesIO(b"scan"), "text/plain")},
                     data={"bizType": "ENT_EVAL"})
    fid = up.json()["data"]["fileId"]
    # 先录入并审核通过企业评价（均分 (80+80+80+80+100)/5 = 84）
    ev = client.post(f"{INT}/enterprise-evals", json={"internshipId": str(ids["rec_a"]), "mentorName": "李导师",
                     "attendanceScore": 80, "skillScore": 80, "attitudeScore": 80,
                     "collaborationScore": 80, "safetyScore": 100, "sourceFileId": fid}, headers=h).json()["data"]["id"]
    client.post(f"{INT}/enterprise-evals/{ev}/review", json={"action": "APPROVE"}, headers=h)
    # 核算不传 enterpriseScore → 自动取 84
    c = client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_a"]), "checkinScore": 100,
                    "weeklyScore": 100, "monthlyScore": 100, "schoolScore": 100}, headers=h)
    detail = client.get(f"{INT}/scores/{c.json()['data']['id']}", headers=h).json()["data"]
    assert detail["enterpriseScore"] == 84


def test_scope_and_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    _cfg100(client)
    p = {"checkinScore": 80, "weeklyScore": 80, "monthlyScore": 80, "enterpriseScore": 80, "schoolScore": 80}
    client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_a"]), **p}, headers=_mentor("刘强"))
    bid = client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_b"]), **p}, headers=_mentor("王芳")).json()["data"]["id"]
    # 刘强越权发布王芳学生成绩 → 403
    assert client.post(f"{INT}/scores/{bid}/publish", headers=_mentor("刘强")).status_code == 403
    # 数据范围
    assert client.get(f"{INT}/scores", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]["total"] == 2
    assert client.get(f"{INT}/scores", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]["total"] == 1
    # 学生 403
    assert client.get(f"{INT}/scores", headers=_student("SC-A"), params={"batchId": ids["batch"]}).status_code == 403
    assert client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_a"]), **p}, headers=_student("SC-A")).status_code == 403


def test_withdraw_and_export(client, db_mode):
    ids = _seed(db_mode)
    _cfg100(client)
    h = _mentor("刘强")
    p = {"checkinScore": 80, "weeklyScore": 80, "monthlyScore": 80, "enterpriseScore": 80, "schoolScore": 80}
    sid = client.post(f"{INT}/scores/compute", json={"internshipId": str(ids["rec_a"]), **p}, headers=h).json()["data"]["id"]
    client.post(f"{INT}/scores/{sid}/publish", headers=h)
    # 撤回需原因
    assert client.post(f"{INT}/scores/{sid}/withdraw", json={"reason": "x"}, headers=h).status_code == 400
    assert client.post(f"{INT}/scores/{sid}/withdraw", json={"reason": "成绩录入有误需重算"}, headers=h).json()["data"]["status"] == "WITHDRAWN"
    res = client.post(f"{INT}/scores/export", headers=_admin(client))
    assert res.status_code == 200 and res.json()["data"]["filename"].endswith(".xlsx") and res.json()["data"]["rowCount"] == 1
