"""P2-C · 学生鉴定/自评（学生提交/重交 / 教师意见 / 学校审核 / owner / 数据范围 / 导出）。"""
from __future__ import annotations

TID = 1000000000000000001
INT = "/api/v1/internship"
M = "/api/v1/mobile/internship/self-eval"


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
        b = InternshipBatch(tenant_id=TID, batch_name="学生鉴定测试批次",
                            batch_no=f"SEBATCH-{uuid4().hex[:8]}", status="RUNNING", planned_count=5)
        db.add(b); db.flush()
        ids["batch"] = b.id
        for no, name, adv, key in [("SE-A", "甲", "刘强", "a"), ("SE-B", "乙", "王芳", "b")]:
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


def test_full_flow(client, db_mode):
    ids = _seed(db_mode)
    sa = _student("SE-A")
    # 学生提交自评
    sub = client.post(M, json={"selfSummary": "本次实习收获很大", "selfHarvest": "掌握了实操",
                               "selfProblem": "沟通仍需提升"}, headers=sa)
    assert sub.status_code == 200 and sub.json()["data"]["submitStatus"] == "SUBMITTED"
    # 我的自评可读
    mine = client.get(M, headers=sa).json()["data"]
    assert mine["selfSummary"] == "本次实习收获很大"
    # 教师端列表可见
    lst = client.get(f"{INT}/student-evals", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]
    assert lst["total"] == 1
    eid = lst["items"][0]["id"]
    # 指导教师填意见
    ac = client.post(f"{INT}/student-evals/{eid}/advisor-comment",
                     json={"advisorOpinion": "实习表现良好，同意鉴定", "mentorOpinion": "企业认可"}, headers=_mentor("刘强"))
    assert ac.status_code == 200
    # 学校审核通过
    rv = client.post(f"{INT}/student-evals/{eid}/review", json={"action": "APPROVE"}, headers=_mentor("刘强"))
    assert rv.status_code == 200 and rv.json()["data"]["reviewStatus"] == "APPROVED"
    # 详情含自评+意见+审计
    detail = client.get(f"{INT}/student-evals/{eid}", headers=_mentor("刘强")).json()["data"]
    assert detail["advisorOpinion"] == "实习表现良好，同意鉴定"
    assert {"STUDENT_SUBMIT", "ADVISOR_COMMENT", "REVIEW_APPROVE"} <= {t["action"] for t in detail["auditTrail"]}


def test_summary_required(client, db_mode):
    _seed(db_mode)
    assert client.post(M, json={"selfHarvest": "x"}, headers=_student("SE-A")).status_code == 400


def test_return_and_resubmit(client, db_mode):
    ids = _seed(db_mode)
    sa = _student("SE-A")
    client.post(M, json={"selfSummary": "初稿总结"}, headers=sa)
    eid = client.get(f"{INT}/student-evals", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]["items"][0]["id"]
    # 退回需原因
    assert client.post(f"{INT}/student-evals/{eid}/review", json={"action": "RETURN", "comment": "no"}, headers=_mentor("刘强")).status_code == 400
    rv = client.post(f"{INT}/student-evals/{eid}/review", json={"action": "RETURN", "comment": "总结过于简单请补充"}, headers=_mentor("刘强"))
    assert rv.json()["data"]["reviewStatus"] == "RETURNED"
    # 学生重交 → 回到待审
    client.post(M, json={"selfSummary": "补充后的详细总结内容"}, headers=sa)
    assert client.get(f"{INT}/student-evals/{eid}", headers=_mentor("刘强")).json()["data"]["reviewStatus"] == "PENDING"


def test_advisor_before_submit_conflict(client, db_mode):
    ids = _seed(db_mode)
    # 直接建一条 DRAFT（未提交）无法用 API，改为：学生未提交时列表无记录，教师无从评论
    # 用已提交但由另一导师评论验证 owner
    client.post(M, json={"selfSummary": "总结"}, headers=_student("SE-A"))
    eid = client.get(f"{INT}/student-evals", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]["items"][0]["id"]
    # 王芳越权填意见 → 403
    assert client.post(f"{INT}/student-evals/{eid}/advisor-comment",
                       json={"advisorOpinion": "越权"}, headers=_mentor("王芳")).status_code == 403


def test_scope_and_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    client.post(M, json={"selfSummary": "A总结"}, headers=_student("SE-A"))
    client.post(M, json={"selfSummary": "B总结"}, headers=_student("SE-B"))
    assert client.get(f"{INT}/student-evals", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]["total"] == 2
    assert client.get(f"{INT}/student-evals", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]["total"] == 1
    assert client.get(f"{INT}/student-evals", headers=_student("SE-A"), params={"batchId": ids["batch"]}).status_code == 403


def test_export(client, db_mode):
    ids = _seed(db_mode)
    client.post(M, json={"selfSummary": "总结"}, headers=_student("SE-A"))
    res = client.post(f"{INT}/student-evals/export", headers=_admin(client), params={"batchId": ids["batch"]})
    assert res.status_code == 200 and res.json()["data"]["filename"].endswith(".xlsx")
    assert res.json()["data"]["rowCount"] == 1
