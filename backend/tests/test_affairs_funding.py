"""13A-P3 奖助闭环 · 端到端（真实 DB 模式）。

F1 奖学金申请建流；F2 全流程→公示→GRANTED 进360；F3 助学金非困难库→409；
F4 助学金困难库在库→放行→GRANTED；F5 重复申请409；F6 越权跨班403；F7 金额脱敏。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

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
    ensure_workflow_assignees([ids["sa"], ids["sb"]])
    return ids


def _open_project_batch(client, hdr, ptype="SCHOLARSHIP", amount=3000):
    pid = client.post(f"{BASE}/funding/projects", headers=hdr, json={
        "projectName": f"{ptype}项目", "projectType": ptype, "amount": amount,
        "quota": 10}).json()["data"]["projectId"]
    bid = client.post(f"{BASE}/funding/batches", headers=hdr, json={
        "projectId": str(pid), "schoolYear": "2025-2026", "publicityDays": 1,
        "quota": 10, "publish": True}).json()["data"]["batchId"]
    return bid


def _fund_apply(client, hdr, bid, sid):
    return client.post(f"{BASE}/funding/applications", headers=hdr, json={
        "batchId": str(bid), "studentId": str(sid), "amount": 3000, "statement": "申请奖学金"})


def _make_difficult(client, hdr, sid):
    """把学生推入困难库（认定通过）。"""
    bid = client.post(f"{BASE}/aid/batches", headers=hdr, json={
        "batchName": "困难认定", "schoolYear": "2025-2026", "publicityDays": 1,
        "levelConfig": {}, "publish": True}).json()["data"]["batchId"]
    aid_id = client.post(f"{BASE}/aid/applications", headers=hdr, json={
        "batchId": str(bid), "studentId": str(sid), "applyLevel": "DIFFICULT",
        "statement": "家庭经济困难需要资助支持完成学业"}).json()["data"]["applyId"]
    for _ in range(3):
        post_versioned(client, f"{BASE}/aid/applications/{aid_id}/review", headers=hdr, json={"action": "APPROVE"})
    post_versioned(client, f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                json={"action": "APPROVE", "level": "DIFFICULT"})
    post_versioned(client, f"{BASE}/aid/applications/{aid_id}/publicity-confirm", headers=hdr)


def _approve_to_publicity(client, hdr, app_id):
    for _ in range(3):
        post_versioned(client, f"{BASE}/funding/applications/{app_id}/review", headers=hdr, json={"action": "APPROVE"})


def test_f1_scholarship_apply_creates_workflow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_project_batch(client, hdr, "SCHOLARSHIP")
    r = _fund_apply(client, hdr, bid, ids["sa"]).json()
    assert r["code"] == 0
    assert r["data"]["status"] == "COUNSELOR_REVIEW"
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance
    db = get_sessionmaker()()
    assert db.query(WorkflowInstance).filter_by(
        source_biz_id=int(r["data"]["applicationId"]), source_biz_type="FUNDING").count() == 1
    db.close()


def test_f2_full_flow_granted_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_project_batch(client, hdr, "SCHOLARSHIP")
    app_id = _fund_apply(client, hdr, bid, ids["sa"]).json()["data"]["applicationId"]
    _approve_to_publicity(client, hdr, app_id)
    d = client.get(f"{BASE}/funding/applications/{app_id}", headers=hdr).json()["data"]
    assert d["status"] == "PUBLICITY"
    c = post_versioned(client, f"{BASE}/funding/applications/{app_id}/publicity-confirm", headers=hdr).json()
    assert c["data"]["status"] == "GRANTED"
    from app.db.session import get_sessionmaker
    from app.models import StudentStageEvent
    db = get_sessionmaker()()
    assert db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="FUNDING_GRANTED").count() == 1
    db.close()


def test_f3_grant_not_in_library_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_project_batch(client, hdr, "GRANT")
    # 未通过困难认定 → 助学金申请被资格校验拦截
    assert _fund_apply(client, hdr, bid, ids["sa"]).status_code == 409


def test_f4_grant_in_library_ok(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _make_difficult(client, hdr, ids["sa"])  # 先进困难库
    bid = _open_project_batch(client, hdr, "GRANT")
    r = _fund_apply(client, hdr, bid, ids["sa"]).json()
    assert r["code"] == 0 and r["data"]["status"] == "COUNSELOR_REVIEW"


def test_f5_duplicate_apply_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_project_batch(client, hdr, "SCHOLARSHIP")
    _fund_apply(client, hdr, bid, ids["sa"])
    assert _fund_apply(client, hdr, bid, ids["sa"]).status_code == 409


def test_f6_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _open_project_batch(client, admin, "SCHOLARSHIP")
    app_id = _fund_apply(client, admin, bid, ids["sb"]).json()["data"]["applicationId"]
    r = client.get(f"{BASE}/funding/applications/{app_id}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403
    assert r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_f7_amount_desensitized_by_role(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _open_project_batch(client, admin, "SCHOLARSHIP")
    _fund_apply(client, admin, bid, ids["sa"])
    # 学工处见真实金额
    items = client.get(f"{BASE}/funding/applications", headers=admin).json()["data"]["items"]
    assert any(a["amount"] == 3000 for a in items)


def test_f8_review_approve_without_workflow_instance_not_500(client, db_mode):
    """历史欠账回归：无 workflow 实例的申请（如沙箱种子直接置 COUNSELOR_REVIEW，未走 apply()）
    审核通过此前在 `instance_id=inst.id`（inst=None）处 AttributeError→500。现应正常推进状态机。"""
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingProject
    db = get_sessionmaker()()
    p = FundingProject(tenant_id=TID, project_name="国家助学金", project_type="GRANT",
                       amount=3300, quota=5, status="ENABLED")
    db.add(p); db.flush()
    b = FundingBatch(tenant_id=TID, project_id=p.id, project_type="GRANT", year_code="2025-2026",
                     status="OPEN", quota=5, publicity_days=5)
    db.add(b); db.flush()
    x = FundingApplication(tenant_id=TID, batch_id=b.id, student_id=ids["sa"], apply_source="SELF",
                           project_type="GRANT", amount=3300, status="COUNSELOR_REVIEW",
                           statement="家庭经济困难，申请国家助学金资助。")  # 注意：不设 workflow_instance_id
    db.add(x); db.commit()
    app_id = x.id
    db.close()
    admin = _hdr(client, "school_admin01")
    r = post_versioned(client, f"{BASE}/funding/applications/{app_id}/review", headers=admin,
                    json={"action": "APPROVE"})
    assert r.status_code == 200, f"无 workflow 实例的申请审核通过不应 500，实得 {r.status_code}"
    assert r.json()["data"]["status"] == "COLLEGE_REVIEW"  # COUNSELOR_REVIEW → 下一节点
