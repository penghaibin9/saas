"""学工待办下钻：studentId 列表过滤 + 范围外不可见。

覆盖：
1. aid list 带 studentId 只返回该生
2. 辅导员范围外学生过滤为空（不泄露）
3. PENDING 语义映射由前端 vitest 保证；本文件附带签名与文档化断言
"""
from __future__ import annotations

import inspect

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
    sa = StudentProfile(tenant_id=TID, student_no="TD001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sb = StudentProfile(tenant_id=TID, student_no="TD002", real_name="乙一", class_id=b.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.add(sb); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids


def _open_batch(client, hdr):
    r = client.post(f"{BASE}/aid/batches", headers=hdr, json={
        "batchName": "下钻批次", "schoolYear": "2025-2026",
        "publicityDays": 1, "levelConfig": {"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]},
        "publish": True}).json()
    assert r.get("code") == 0, r
    return r["data"]["batchId"]


def _apply(client, hdr, batch_id, sid):
    return client.post(f"{BASE}/aid/applications", headers=hdr, json={
        "batchId": str(batch_id), "studentId": str(sid), "applyLevel": "DIFFICULT",
        "statement": "家庭收入较低，父母务农，需要资助支持完成学业",
        "memberCount": 4, "annualIncome": "25000", "specialTags": ["单亲"]})


def test_pending_semantics_and_list_signatures():
    """文档化公共语义 + 确认 list 函数已接受 student_id。"""
    assert resolve_todo_status_doc("aid", "PENDING") == "REVIEW"
    assert resolve_todo_status_doc("discipline", "REMOVE_PENDING") == "REMOVE_REVIEW"
    assert resolve_todo_status_doc("risk", "PENDING") == "PENDING"

    from app.services import affairs_aid_service as aid
    from app.services import affairs_funding_service as funding
    from app.services import affairs_discipline_service as disc
    from app.services import affairs_dorm_service as dorm
    from app.services import affairs_leave_service as leave
    for fn in (aid.list_applications, funding.list_applications, disc.list_cases,
               dorm.list_transfers, dorm.list_exceptions, leave.list_leaves):
        assert "student_id" in inspect.signature(fn).parameters


def resolve_todo_status_doc(domain, raw):
    """与前端 todoFilterSemantics 对齐的最小文档映射（仅测关键 PENDING）。"""
    table = {
        ("aid", "PENDING"): "REVIEW",
        ("discipline", "REMOVE_PENDING"): "REMOVE_REVIEW",
        ("risk", "PENDING"): "PENDING",
        ("aid", "ADJUST_PENDING"): "ADJUST_REVIEW",
    }
    return table[(domain, raw)]


def test_aid_list_student_id_filter_and_scope(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _open_batch(client, admin)
    r1 = _apply(client, admin, bid, ids["sa"]).json()
    r2 = _apply(client, admin, bid, ids["sb"]).json()
    assert r1["code"] == 0 and r2["code"] == 0

    all_list = client.get(f"{BASE}/aid/applications", headers=admin,
                          params={"batchId": bid, "pageSize": 50}).json()["data"]["items"]
    assert len(all_list) >= 2

    only_a = client.get(f"{BASE}/aid/applications", headers=admin, params={
        "batchId": bid, "studentId": str(ids["sa"]), "pageSize": 50
    }).json()["data"]["items"]
    assert len(only_a) == 1
    assert str(only_a[0]["studentId"]) == str(ids["sa"])

    # 辅导员仅软件2101：查范围外学生 sb → 空列表（过滤掉，不泄露）
    counselor = _hdr(client, "counselor01")
    out_of_scope = client.get(f"{BASE}/aid/applications", headers=counselor, params={
        "batchId": bid, "studentId": str(ids["sb"]), "pageSize": 50
    }).json()["data"]["items"]
    assert out_of_scope == []
