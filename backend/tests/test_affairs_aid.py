"""13A-P3 困难认定闭环 · 端到端（真实 DB 模式）。

A1 建批次+申请建流；A2 多级评审→公示→通过(困难库+360)；A3 驳回原因校验；
A4 公示扫描幂等；A5 敏感四连测(默认脱敏/越权403+审计/授权reveal+审计/列表不出明细)；
重复申请409；越权跨班403。
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


def _open_batch(client, hdr, publicity_days=0):
    return client.post(f"{BASE}/aid/batches", headers=hdr, json={
        "batchName": "2026春困难认定", "schoolYear": "2025-2026",
        "publicityDays": publicity_days, "levelConfig": {"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]},
        "publish": True}).json()["data"]["batchId"]


def _apply(client, hdr, batch_id, sid, level="DIFFICULT"):
    return client.post(f"{BASE}/aid/applications", headers=hdr, json={
        "batchId": str(batch_id), "studentId": str(sid), "applyLevel": level,
        "statement": "家庭收入较低，父母务农，需要资助支持完成学业",
        "memberCount": 4, "annualIncome": "25000", "specialTags": ["单亲"]})


def _approve_to_publicity(client, hdr, aid_id):
    for _ in range(3):
        client.post(f"{BASE}/aid/applications/{aid_id}/review", headers=hdr, json={"action": "APPROVE"})
    return client.post(f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                       json={"action": "APPROVE", "level": "DIFFICULT"}).json()


def test_a1_apply_creates_workflow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    r = _apply(client, hdr, bid, ids["sa"]).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["status"] == "CLASS_REVIEW"
    assert d["familyEconomy"]["detailMasked"] is True
    assert "annualIncome" not in d["familyEconomy"]  # 明细不出
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo, WorkflowInstance
    db = get_sessionmaker()()
    assert db.query(WorkflowInstance).filter_by(
        source_biz_id=int(d["applyId"]), source_biz_type="AID").count() == 1
    assert db.query(UnifiedTodo).filter_by(source_biz_id=int(d["applyId"]), todo_type="AID_APPROVAL").count() == 1
    db.close()


def test_a2_full_flow_to_difficult_library(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    aid_id = _apply(client, hdr, bid, ids["sa"]).json()["data"]["applyId"]
    r = _approve_to_publicity(client, hdr, aid_id)
    assert r["data"]["status"] == "PUBLICITY"
    assert r["data"]["finalLevel"] == "DIFFICULT"
    # 人工确认公示 → APPROVED
    c = client.post(f"{BASE}/aid/applications/{aid_id}/publicity-confirm", headers=hdr).json()
    assert c["data"]["status"] == "APPROVED"
    # 进困难库
    lib = client.get(f"{BASE}/aid/difficult-students", headers=hdr).json()["data"]["items"]
    assert any(s["studentId"] == str(ids["sa"]) and s["level"] == "DIFFICULT" for s in lib)
    # 进 360 + 写等级历史
    from app.db.session import get_sessionmaker
    from app.models import AidLevelHistory, StudentStageEvent
    db = get_sessionmaker()()
    assert db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="AID_APPROVED").count() == 1
    assert db.query(AidLevelHistory).filter_by(student_id=ids["sa"], change_type="IDENTIFY").count() == 1
    db.close()


def test_a3_reject_reason_required(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    aid_id = _apply(client, hdr, bid, ids["sa"]).json()["data"]["applyId"]
    # 原因 <5 字 → 400
    assert client.post(f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                       json={"action": "REJECT", "reason": "不行"}).status_code == 400
    r = client.post(f"{BASE}/aid/applications/{aid_id}/review", headers=hdr,
                    json={"action": "REJECT", "reason": "材料不齐，无法认定"}).json()
    assert r["data"]["status"] == "REJECTED"


def test_a4_publicity_scan_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr, publicity_days=0)  # 0 天 → 即刻可确认
    aid_id = _apply(client, hdr, bid, ids["sa"]).json()["data"]["applyId"]
    _approve_to_publicity(client, hdr, aid_id)
    r = client.post(f"{BASE}/aid/scan-publicity", headers=hdr).json()
    assert r["data"]["count"] == 1
    r2 = client.post(f"{BASE}/aid/scan-publicity", headers=hdr).json()
    assert r2["data"]["count"] == 0  # 幂等
    d = client.get(f"{BASE}/aid/applications/{aid_id}", headers=hdr).json()["data"]
    assert d["status"] == "APPROVED"


def test_a5_sensitive_family_economy(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _open_batch(client, admin)
    aid_id = _apply(client, admin, bid, ids["sa"]).json()["data"]["applyId"]
    # ① 列表默认脱敏：只出区间，不出真实收入
    lst = client.get(f"{BASE}/aid/applications", headers=admin).json()["data"]["items"]
    fe = next(a["familyEconomy"] for a in lst if a["applyId"] == aid_id)
    assert fe["annualIncomeRange"] == "2-4万" and "annualIncome" not in fe
    # ② 越权 reveal（辅导员无 sensitiveView）→ 403 + 审计 DENY
    r403 = client.post(f"{BASE}/aid/applications/{aid_id}/reveal",
                       headers=_hdr(client, "counselor01"), json={"reason": "核实家庭情况"})
    assert r403.status_code == 403
    # ③ 授权 reveal（学工处）→ 完整值 + 审计 SUCCESS
    ok = client.post(f"{BASE}/aid/applications/{aid_id}/reveal", headers=admin,
                     json={"reason": "评审需核实家庭经济"}).json()
    assert ok["data"]["familyEconomy"]["annualIncome"] == "25000"
    assert ok["data"]["familyEconomy"]["detailMasked"] is False
    # ④ 两次访问均落 SENSITIVE_VIEW 审计
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    db = get_sessionmaker()()
    n = db.query(SecurityAuditLog).filter_by(action="SENSITIVE_VIEW").count()
    db.close()
    assert n == 2


def test_a6_duplicate_apply_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    _apply(client, hdr, bid, ids["sa"])
    assert _apply(client, hdr, bid, ids["sa"]).status_code == 409


def test_a7_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _open_batch(client, admin)
    aid_id = _apply(client, admin, bid, ids["sb"]).json()["data"]["applyId"]  # B 班
    r = client.get(f"{BASE}/aid/applications/{aid_id}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403
    assert r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_a_apply_non_digit_ids_400_not_500(client, db_mode):
    """历史欠账收口：studentId/batchId 非数字此前 int() 抛 500，现应 400 VALIDATION_ERROR。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _open_batch(client, admin)
    r1 = client.post(f"{BASE}/aid/applications", headers=admin, json={
        "batchId": str(bid), "studentId": "abc", "applyLevel": "DIFFICULT",
        "statement": "家庭收入较低，需要资助支持完成学业"})
    assert r1.status_code == 400 and r1.json()["bizCode"] == "VALIDATION_ERROR"
    r2 = client.post(f"{BASE}/aid/applications", headers=admin, json={
        "batchId": "notnum", "studentId": str(ids["sa"]), "applyLevel": "DIFFICULT",
        "statement": "家庭收入较低，需要资助支持完成学业"})
    assert r2.status_code == 400 and r2.json()["bizCode"] == "VALIDATION_ERROR"
