"""学生 PC · 离校清单（V3 施工手册 SP-D01~SP-D04）。

离校是对各域已有真实结论的只读编排，本身不写任何业务状态。用真实 MySQL 跑。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/departure"
TID = 1000000000000000001


def _stu_token(real_name, student_no, student_id=None):
    from app.core.security import create_access_token
    claims = {
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC",
    }
    if student_id is not None:
        claims["studentId"] = str(student_id)
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_student(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        row = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M",
                             grade="2022", current_stage="EMPLOYMENT",
                             student_status="NORMAL", status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)
    finally:
        db.close()


def _items(client, headers):
    r = client.get(f"{PORTAL}/my", headers=headers).json()
    assert r["code"] == 0, r
    return r["data"], {x["key"]: x for x in r["data"]["items"]}


def test_departure_returns_per_item_source_result_blocking_and_evidence(client, db_mode):
    """SP-D01 验收门槛：每项返回 source / result / blocking / action / evidenceVersion。"""
    sid = _seed_student("DEP-001", "离校一")
    data, by_key = _items(client, _stu_token("离校一", "DEP-001", sid))

    assert data["hasData"] is True
    assert data["departureVersion"] == 1
    assert set(by_key) == {"graduation", "internship", "employment", "discipline"}
    for item in data["items"]:
        assert item["source"], item
        assert item["result"] in {
            "PASS", "FAIL", "NOT_REQUIRED", "NOT_STARTED",
            "MANUAL_PENDING", "UNKNOWN", "ERROR"}, item
        assert isinstance(item["blocking"], bool), item
        assert "action" in item and "evidenceVersion" in item, item
    # 阻断口径是系统保守默认，必须如实标注，不假装是学校已配置的规则
    assert data["policySource"] == "default_conservative"
    assert data["policyNote"]


def test_empty_employment_record_does_not_pass(client, db_mode):
    """SP-D02 核心：EmpStudent.destination_type 默认就是 UNEMPLOYED，
    "存在就业档案"绝不能被当成"学生已声明去向"。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    sid = _seed_student("DEP-002", "离校二")
    db = get_sessionmaker()()
    try:
        # 只建一条默认档案：destination_type 走数据库默认 UNEMPLOYED
        db.add(EmpStudent(tenant_id=TID, student_id=sid, student_no="DEP-002",
                          name="离校二", record_status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    data, by_key = _items(client, _stu_token("离校二", "DEP-002", sid))
    emp = by_key["employment"]
    assert emp["result"] == "NOT_STARTED", emp
    assert emp["blocking"] is True
    assert data["readiness"] == "NOT_READY"


def test_no_employment_record_is_not_started_not_pass(client, db_mode):
    """完全没有就业档案同样不能 PASS。"""
    sid = _seed_student("DEP-003", "离校三")
    _data, by_key = _items(client, _stu_token("离校三", "DEP-003", sid))
    assert by_key["employment"]["result"] == "NOT_STARTED"


def test_verified_destination_passes_and_returned_fails(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    sid = _seed_student("DEP-004", "离校四")
    db = get_sessionmaker()()
    try:
        db.add(EmpStudent(tenant_id=TID, student_id=sid, student_no="DEP-004", name="离校四",
                          destination_type="SIGNED", company_name="某公司",
                          verify_status="VERIFIED", record_status="ACTIVE"))
        db.commit()
    finally:
        db.close()
    _d, by_key = _items(client, _stu_token("离校四", "DEP-004", sid))
    assert by_key["employment"]["result"] == "PASS", by_key["employment"]

    db = get_sessionmaker()()
    try:
        row = db.query(EmpStudent).filter(EmpStudent.student_id == sid).first()
        row.verify_status = "RETURNED"
        db.commit()
    finally:
        db.close()
    _d2, by_key2 = _items(client, _stu_token("离校四", "DEP-004", sid))
    assert by_key2["employment"]["result"] == "FAIL", by_key2["employment"]


def test_submitted_but_unverified_is_manual_pending_not_pass(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    sid = _seed_student("DEP-005", "离校五")
    db = get_sessionmaker()()
    try:
        db.add(EmpStudent(tenant_id=TID, student_id=sid, student_no="DEP-005", name="离校五",
                          destination_type="SIGNED", company_name="某公司",
                          verify_status="PENDING_VERIFY", record_status="ACTIVE"))
        db.commit()
    finally:
        db.close()
    data, by_key = _items(client, _stu_token("离校五", "DEP-005", sid))
    assert by_key["employment"]["result"] == "MANUAL_PENDING"
    assert data["readiness"] == "NOT_READY"


def test_source_failure_is_error_not_unknown_and_does_not_break_other_items(client, db_mode, monkeypatch):
    """SP-D03：单域故障必须显式 ERROR（不是 UNKNOWN、更不是"暂无"），
    且不能拖垮其他环节——跨域聚合最容易犯的错就是一个源挂了整张清单打不开。"""
    from app.services import departure_projection_service as proj

    sid = _seed_student("DEP-006", "离校六")

    def _boom(db, student):
        raise RuntimeError("simulated graduation outage")

    monkeypatch.setattr(proj, "_graduation_item", _boom)
    # _BUILDERS 在模块导入时已绑定函数对象，需一并替换才能生效
    monkeypatch.setattr(proj, "_BUILDERS", tuple(
        (k, t, s, b, (_boom if k == "graduation" else fn))
        for k, t, s, b, fn in proj._BUILDERS
    ))

    data, by_key = _items(client, _stu_token("离校六", "DEP-006", sid))
    assert by_key["graduation"]["result"] == "ERROR", by_key["graduation"]
    assert "读取失败" in by_key["graduation"]["detail"]
    # 其他环节仍给出真实结论
    assert by_key["employment"]["result"] == "NOT_STARTED"
    assert by_key["internship"]["result"] in {"NOT_REQUIRED", "MANUAL_PENDING"}
    # blocking 项处于 ERROR 时不得 READY
    assert data["readiness"] == "NOT_READY"


def test_discipline_is_reported_but_not_blocking_by_default(client, db_mode):
    """是否因违纪阻断离校属于校本制度，系统只如实呈现、交学校判定。"""
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import DisciplineCase

    sid = _seed_student("DEP-007", "离校七")
    db = get_sessionmaker()()
    try:
        db.add(DisciplineCase(tenant_id=TID, student_id=sid, disc_type="WARNING",
                              reason="测试违纪", status="REGISTERED",
                              decide_date=datetime.utcnow()))
        db.commit()
    finally:
        db.close()
    _d, by_key = _items(client, _stu_token("离校七", "DEP-007", sid))
    disc = by_key["discipline"]
    assert disc["result"] == "MANUAL_PENDING"
    assert disc["blocking"] is False, "违纪是否阻断离校是校本制度，系统不得替学校下结论"


def test_non_student_rejected(client, db_mode):
    assert client.get(f"{PORTAL}/my", headers=_admin(client)).json()["code"] == 403001
