"""13A-P4 违纪处分闭环 · 端到端（真实 DB 模式）。

D1 登记+提交建流；D2 一般处分全链→EFFECTIVE+投影+360+对账；D3 严重处分走校级；
D4 驳回原因校验+生效不可再审；D5 解除全链→REMOVED+投影record_status+对账；
未生效发起解除409；越权跨班403。
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


def _register(client, hdr, sid, disc_type="WARNING"):
    return client.post(f"{BASE}/discipline/cases", headers=hdr, json={
        "studentId": str(sid), "discType": disc_type, "reason": "考试违纪，情节较轻，予以处分"})


def _to_effective(client, hdr, cid, severe=False):
    client.post(f"{BASE}/discipline/cases/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/discipline/cases/{cid}/review", headers=hdr, json={"action": "APPROVE"})  # COLLEGE
    r = client.post(f"{BASE}/discipline/cases/{cid}/review", headers=hdr, json={"action": "APPROVE"})  # SA
    if severe:
        r = client.post(f"{BASE}/discipline/cases/{cid}/review", headers=hdr, json={"action": "APPROVE"})  # SCHOOL
    return r.json()


def test_d1_register_submit_creates_workflow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    r = client.post(f"{BASE}/discipline/cases/{cid}/submit", headers=hdr).json()
    assert r["data"]["status"] == "COLLEGE_REVIEW"
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance
    db = get_sessionmaker()()
    assert db.query(WorkflowInstance).filter_by(source_biz_id=int(cid), source_biz_type="DISCIPLINE").count() == 1
    db.close()


def test_d2_normal_to_effective_projection_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"], "WARNING").json()["data"]["caseId"]
    r = _to_effective(client, hdr, cid, severe=False)
    assert r["data"]["status"] == "EFFECTIVE"
    assert r["data"]["csDisciplineId"]  # 投影行已建
    # 投影 + 360 + 对账
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline, StudentStageEvent
    db = get_sessionmaker()()
    proj = db.query(CsDiscipline).filter_by(source_case_id=int(cid), record_status="ACTIVE").count()
    ev = db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="DISCIPLINE_EFFECTIVE").count()
    db.close()
    assert proj == 1 and ev == 1
    rec = client.get(f"{BASE}/discipline/reconcile", headers=hdr).json()["data"]
    assert rec["consistent"] is True and rec["effectiveCases"] == 1 and rec["activeProjections"] == 1


def test_d3_severe_goes_school_review(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"], "EXPEL").json()["data"]["caseId"]
    client.post(f"{BASE}/discipline/cases/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/discipline/cases/{cid}/review", headers=hdr, json={"action": "APPROVE"})  # COLLEGE
    r = client.post(f"{BASE}/discipline/cases/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()  # SA
    assert r["data"]["status"] == "SCHOOL_REVIEW"  # 严重处分转校级
    r2 = client.post(f"{BASE}/discipline/cases/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "EFFECTIVE"


def test_d4_reject_and_effective_immutable(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    client.post(f"{BASE}/discipline/cases/{cid}/submit", headers=hdr)
    # 原因<5字 → 400
    assert client.post(f"{BASE}/discipline/cases/{cid}/review", headers=hdr,
                       json={"action": "REJECT", "reason": "不"}).status_code == 400
    # 生效后再审 → 409
    _to_effective(client, hdr, _register(client, hdr, ids["sa"]).json()["data"]["caseId"])
    cid2 = _register(client, hdr, ids["sb"] if False else ids["sa"]).json()["data"]["caseId"]  # 另一单
    _to_effective(client, hdr, cid2)
    assert client.post(f"{BASE}/discipline/cases/{cid2}/review", headers=hdr,
                       json={"action": "APPROVE"}).status_code == 409


def test_d5_remove_flow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    _to_effective(client, hdr, cid)
    # 发起解除 → REMOVE_REVIEW
    r = client.post(f"{BASE}/discipline/cases/{cid}/remove", headers=hdr,
                    json={"reason": "表现良好，申请解除处分"}).json()
    assert r["data"]["status"] == "REMOVE_REVIEW"
    # 辅→院→处 三级审批
    for _ in range(3):
        r = client.post(f"{BASE}/discipline/cases/{cid}/remove-review", headers=hdr,
                        json={"action": "APPROVE"}).json()
    assert r["data"]["status"] == "REMOVED"
    # 投影 record_status 更新 + 对账（生效数=0，投影ACTIVE=0）
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline
    db = get_sessionmaker()()
    revoked = db.query(CsDiscipline).filter_by(source_case_id=int(cid), record_status="REVOKED").count()
    db.close()
    assert revoked == 1
    rec = client.get(f"{BASE}/discipline/reconcile", headers=hdr).json()["data"]
    assert rec["consistent"] is True


def test_d6_remove_before_effective_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    assert client.post(f"{BASE}/discipline/cases/{cid}/remove", headers=hdr,
                       json={"reason": "尚未生效就申请解除"}).status_code == 409


def test_d7_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    cid = _register(client, admin, ids["sb"]).json()["data"]["caseId"]
    r = client.get(f"{BASE}/discipline/cases/{cid}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_d_register_non_digit_student_400_not_500(client, db_mode):
    """历史欠账收口：登记违纪 studentId 非数字此前 int() 抛 500，现应 400 VALIDATION_ERROR。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/discipline/cases", headers=hdr, json={
        "studentId": "abc", "discType": "WARNING", "reason": "考试违纪，情节较轻，予以处分"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"
