"""13A-P3 困难认定闭环 · 端到端（真实 DB 模式）。

A1 建批次+申请建流；A2 多级评审→公示→通过(困难库+360)；A3 驳回原因校验；
A4 公示扫描幂等；A5 敏感四连测(默认脱敏/越权403+审计/授权reveal+审计/列表不出明细)；
重复申请409；越权跨班403。
"""
from __future__ import annotations

from datetime import datetime, timedelta

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    """建立真实学院、班级、账号、角色和逐级受理关系。

    生产代码对没有具体受理人的节点 fail-closed；测试不能再只写一条文本 scope
    就假装存在辅导员/学院/学校审批人。
    """
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, Major, Role, SchoolClass,
        StudentProfile, TeacherStudentScope, User, UserRole,
    )

    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()

    a = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()

    counselor_user = User(
        tenant_id=TID, login_name="counselor01", real_name="王莉",
        password_hash="test-only", user_type="TEACHER", status="ACTIVE",
    )
    college_user = User(
        tenant_id=TID, login_name="college_admin01", real_name="学院管理员",
        password_hash="test-only", user_type="TEACHER", status="ACTIVE",
    )
    school_user = User(
        tenant_id=TID, login_name="school_admin01", real_name="学校管理员",
        password_hash="test-only", user_type="SCHOOL_ADMIN", status="ACTIVE",
    )
    db.add_all([counselor_user, college_user, school_user]); db.flush()

    roles = {}
    for code, name in (
        ("COUNSELOR", "辅导员"),
        ("COLLEGE_ADMIN", "学院管理员"),
        ("SCHOOL_ADMIN", "学校管理员"),
    ):
        role = Role(tenant_id=TID, role_code=code, role_name=name, role_type="SYSTEM", status="ACTIVE")
        db.add(role); db.flush()
        roles[code] = role
    db.add_all([
        UserRole(tenant_id=TID, user_id=counselor_user.id, role_id=roles["COUNSELOR"].id, status="ACTIVE"),
        UserRole(tenant_id=TID, user_id=college_user.id, role_id=roles["COLLEGE_ADMIN"].id, status="ACTIVE"),
        UserRole(tenant_id=TID, user_id=school_user.id, role_id=roles["SCHOOL_ADMIN"].id, status="ACTIVE"),
    ])

    now = datetime.utcnow()
    db.add_all([
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=a.id, user_id=counselor_user.id,
            duty_type="PRIMARY", status="ACTIVE", effective_from=now - timedelta(days=1),
        ),
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=b.id, user_id=counselor_user.id,
            duty_type="PRIMARY", status="ACTIVE", effective_from=now - timedelta(days=1),
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
            role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101", status="ACTIVE",
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="college_admin01", teacher_name="学院管理员",
            role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value=college.college_name, status="ACTIVE",
        ),
    ])

    sa = StudentProfile(
        tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id, college_id=college.id,
        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE",
    )
    sb = StudentProfile(
        tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id, college_id=college.id,
        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE",
    )
    db.add(sa); db.add(sb); db.flush()
    db.commit()
    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids


def _open_batch(client, hdr, publicity_days=1):
    result = client.post(f"{BASE}/aid/batches", headers=hdr, json={
        "batchName": "2026春困难认定", "schoolYear": "2025-2026",
        "publicityDays": publicity_days, "levelConfig": {"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]},
        "publish": True}).json()
    assert result["code"] == 0, result
    return result["data"]["batchId"]


def _apply(client, hdr, batch_id, sid, level="DIFFICULT"):
    return client.post(f"{BASE}/aid/applications", headers=hdr, json={
        "batchId": str(batch_id), "studentId": str(sid), "applyLevel": level,
        "statement": "家庭收入较低，父母务农，需要资助支持完成学业",
        "memberCount": 4, "annualIncome": "25000", "specialTags": ["单亲"]})


def _review(client, hdr, item, *, action="APPROVE", level=None, reason=""):
    body = {"action": action, "version": item["version"]}
    if level:
        body["level"] = level
    if reason:
        body["reason"] = reason
    result = client.post(f"{BASE}/aid/applications/{item['applyId']}/review", headers=hdr, json=body).json()
    assert result["code"] == 0, result
    return result["data"]


def _expire_publicity(apply_id):
    """测试时间推进：正式规则仍为公示至少1天，仅把测试记录回拨到已到期。"""
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    db = get_sessionmaker()()
    row = db.get(AidApply, int(apply_id))
    row.publicity_at = datetime.utcnow() - timedelta(days=2)
    db.commit(); db.close()


def _approve_to_publicity(client, hdr, aid_id):
    current = client.get(f"{BASE}/aid/applications/{aid_id}", headers=hdr).json()["data"]
    for _ in range(3):
        current = _review(client, hdr, current)
    current = _review(client, hdr, current, level="DIFFICULT")
    assert current["status"] == "PUBLICITY"
    _expire_publicity(aid_id)
    return current


def test_a1_apply_creates_workflow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    r = _apply(client, hdr, bid, ids["sa"]).json()
    assert r["code"] == 0, r
    d = r["data"]
    assert d["status"] == "CLASS_REVIEW"
    assert d["familyEconomy"]["detailMasked"] is True
    assert "annualIncome" not in d["familyEconomy"]
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
    current = _approve_to_publicity(client, hdr, aid_id)
    assert current["finalLevel"] == "DIFFICULT"
    c = client.post(
        f"{BASE}/aid/applications/{aid_id}/publicity-confirm",
        headers=hdr,
        json={"version": current["version"]},
    ).json()
    assert c["code"] == 0 and c["data"]["status"] == "APPROVED"
    lib = client.get(f"{BASE}/aid/difficult-students", headers=hdr).json()["data"]["items"]
    assert any(s["studentId"] == str(ids["sa"]) and s["level"] == "DIFFICULT" for s in lib)
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
    item = _apply(client, hdr, bid, ids["sa"]).json()["data"]
    assert client.post(f"{BASE}/aid/applications/{item['applyId']}/review", headers=hdr,
                       json={"action": "REJECT", "reason": "不行", "version": item["version"]}).status_code == 400
    r = client.post(f"{BASE}/aid/applications/{item['applyId']}/review", headers=hdr,
                    json={"action": "REJECT", "reason": "材料不齐，无法认定",
                          "version": item["version"]}).json()
    assert r["code"] == 0 and r["data"]["status"] == "REJECTED"


def test_a4_publicity_scan_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr, publicity_days=1)
    aid_id = _apply(client, hdr, bid, ids["sa"]).json()["data"]["applyId"]
    _approve_to_publicity(client, hdr, aid_id)
    r = client.post(f"{BASE}/aid/scan-publicity", headers=hdr).json()
    assert r["data"]["count"] == 1
    r2 = client.post(f"{BASE}/aid/scan-publicity", headers=hdr).json()
    assert r2["data"]["count"] == 0
    d = client.get(f"{BASE}/aid/applications/{aid_id}", headers=hdr).json()["data"]
    assert d["status"] == "APPROVED"


def test_a5_sensitive_family_economy(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _open_batch(client, admin)
    aid_id = _apply(client, admin, bid, ids["sa"]).json()["data"]["applyId"]
    lst = client.get(f"{BASE}/aid/applications", headers=admin).json()["data"]["items"]
    fe = next(a["familyEconomy"] for a in lst if a["applyId"] == aid_id)
    assert fe["annualIncomeRange"] == "2-4万" and "annualIncome" not in fe
    ok_c = client.post(f"{BASE}/aid/applications/{aid_id}/reveal",
                       headers=_hdr(client, "counselor01"), json={"reason": "核实家庭情况"})
    assert ok_c.status_code == 200
    assert ok_c.json()["data"]["familyEconomy"]["annualIncome"] == "25000"
    ok = client.post(f"{BASE}/aid/applications/{aid_id}/reveal", headers=admin,
                     json={"reason": "评审需核实家庭经济"}).json()
    assert ok["data"]["familyEconomy"]["annualIncome"] == "25000"
    assert ok["data"]["familyEconomy"]["detailMasked"] is False
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    db = get_sessionmaker()()
    n = db.query(SecurityAuditLog).filter_by(action="SENSITIVE_VIEW", result="SUCCESS").count()
    db.close()
    assert n >= 2


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
    aid_id = _apply(client, admin, bid, ids["sb"]).json()["data"]["applyId"]
    r = client.get(f"{BASE}/aid/applications/{aid_id}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403
    assert r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_a8_counselor_review_scoped_to_counselor_review_node(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    counselor = _hdr(client, "counselor01")
    bid = _open_batch(client, admin)
    current = _apply(client, admin, bid, ids["sa"]).json()["data"]
    assert current["status"] == "CLASS_REVIEW"

    r1 = client.post(f"{BASE}/aid/applications/{current['applyId']}/review", headers=counselor,
                     json={"action": "APPROVE", "version": current["version"]})
    assert r1.status_code == 200
    current = r1.json()["data"]
    assert current["status"] == "COUNSELOR_REVIEW"

    reveal = client.post(f"{BASE}/aid/applications/{current['applyId']}/reveal", headers=counselor,
                         json={"reason": "初审核实家庭情况"})
    assert reveal.status_code == 200
    assert reveal.json()["data"]["familyEconomy"]["annualIncome"] == "25000"

    r2 = client.post(f"{BASE}/aid/applications/{current['applyId']}/review", headers=counselor,
                     json={"action": "APPROVE", "level": "DIFFICULT", "version": current["version"]}).json()
    current = r2["data"]
    assert current["status"] == "COLLEGE_REVIEW"
    assert current["suggestLevel"] == "DIFFICULT"

    r3 = client.post(f"{BASE}/aid/applications/{current['applyId']}/review", headers=counselor,
                     json={"action": "APPROVE", "version": current["version"]})
    assert r3.status_code == 403
    r4 = client.post(f"{BASE}/aid/applications/{current['applyId']}/reveal", headers=counselor,
                     json={"reason": "复核"})
    assert r4.status_code == 403


def test_a_apply_non_digit_ids_400_not_500(client, db_mode):
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
