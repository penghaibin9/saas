"""未注册学生搜索：在原范围与暂缓规则内跨页查姓名、学号。"""
from datetime import datetime
from types import SimpleNamespace

import pytest

TID = 1000000000000000001
URL = "/api/v1/academic-affairs/registration/unregistered"


@pytest.fixture
def search_ledger(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaRegistration, AaRegistrationBatch, AaRegistrationDeferral, College, Major, SchoolClass, StudentProfile
    with get_sessionmaker()() as db:
        college = College(tenant_id=TID, college_name="检索测试学院", code="URS-C")
        db.add(college); db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name="检索测试专业", code="URS-M")
        db.add(major); db.flush()
        klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="检索测试班", grade="2026", status="ACTIVE")
        batch = AaRegistrationBatch(tenant_id=TID, batch_name="未注册检索", register_type="ENROLL", status="OPEN", window_end=datetime(2020, 1, 1))
        second = AaRegistrationBatch(tenant_id=TID, batch_name="另一批次", register_type="ENROLL", status="CLOSED")
        db.add_all([klass, batch, second]); db.flush()
        students = []
        names = ["跨页目标甲", "跨页目标乙", *[f"普通学生{i}" for i in range(25)],
                 "字面%_学生", "跨页目标已注册", "跨页目标暂缓", "跨页目标无期限暂缓", "跨页目标删除", "跨页目标外校"]
        for index, name in enumerate(names):
            students.append(StudentProfile(tenant_id=TID + (name == "跨页目标外校"), student_no=f"URS{index:03}", real_name=name,
                college_id=college.id, major_id=major.id, class_id=klass.id, current_stage="ORIENTATION",
                student_status="PENDING_REGISTER", status="ACTIVE", is_deleted=name == "跨页目标删除"))
        db.add_all(students); db.flush()
        by_name = {s.real_name: s for s in students}
        db.add_all([
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=students[1].id, status="UNREGISTERED"),
            AaRegistration(tenant_id=TID, batch_id=second.id, student_id=students[0].id, status="UNREGISTERED"),
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=by_name["跨页目标已注册"].id, status="REGISTERED"),
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=by_name["跨页目标删除"].id, status="UNREGISTERED"),
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=by_name["跨页目标外校"].id, status="UNREGISTERED"),
            AaRegistrationDeferral(tenant_id=TID, batch_id=batch.id, student_id=by_name["跨页目标暂缓"].id, reason="测试暂缓", status="APPROVED", requested_until=datetime(2099, 1, 1)),
            AaRegistrationDeferral(tenant_id=TID, batch_id=batch.id, student_id=by_name["跨页目标无期限暂缓"].id, reason="测试暂缓", status="APPROVED", requested_until=None),
        ])
        db.commit()
        return {"batch": str(batch.id), "otherBatch": str(second.id), "allowed": str(students[0].id), "neighbor": str(students[1].id), "class": klass.id}


def query(client, headers, **params):
    response = client.get(URL, headers=headers, params=params)
    assert response.status_code == 200, response.text
    assert response.json()["code"] == 0
    return response.json()["data"]


def test_unregistered_search_crosses_pages_preserves_both_ledger_kinds(client, search_ledger, auth_headers):
    ids = search_ledger
    initial = query(client, auth_headers, batchId=ids["batch"], pageSize=20)
    assert ids["allowed"] not in {r["studentId"] for r in initial["items"]}
    first = query(client, auth_headers, batchId=ids["batch"], keyword="跨页目标", pageSize=1, page=1)
    second = query(client, auth_headers, batchId=ids["batch"], keyword="跨页目标", pageSize=1, page=2)
    assert first["total"] == second["total"] == 2
    rows = first["items"] + second["items"]
    assert {r["studentId"] for r in rows} == {ids["allowed"], ids["neighbor"]}
    assert {r["kind"] for r in rows} == {"UNREGISTERED", "OVERDUE_PENDING_SCAN"}
    multiple = query(client, auth_headers, keyword="urs000")
    assert multiple["total"] == 2
    assert {r["batchId"] for r in multiple["items"]} == {ids["batch"], ids["otherBatch"]}


def test_unregistered_search_keeps_literal_matching_and_exact_student_scope(client, search_ledger, auth_headers, monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_registration_read_guard as guard
    ids = search_ledger
    literal = query(client, auth_headers, batchId=ids["batch"], keyword="%_")
    assert literal["total"] == 1 and literal["items"][0]["realName"] == "字面%_学生"
    point = SimpleNamespace(scope_type="STUDENT", student_ids={int(ids["allowed"])}, psychology_student_ids=set(), allowed_class_ids=lambda _db: {ids["class"]})
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db=None: point)
    result = query(client, auth_headers, batchId=ids["batch"], keyword="跨页目标")
    assert result["total"] == 1 and result["items"][0]["studentId"] == ids["allowed"]
    point.student_ids = set()
    assert query(client, auth_headers, batchId=ids["batch"], keyword="跨页目标")["total"] == 0


def test_unregistered_search_rejects_invalid_keyword_and_student_access(client, search_ledger, auth_headers):
    assert client.get(URL, headers=auth_headers, params={"keyword": "x" * 201}).status_code == 400
    token = client.post("/api/v1/auth/mock-login", json={"loginName": "student01", "password": "any"}).json()["data"]["accessToken"]
    assert client.get(URL, headers={"Authorization": f"Bearer {token}"}, params={"keyword": "跨页目标"}).status_code == 403
