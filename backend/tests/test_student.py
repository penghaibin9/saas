"""学生主档第一批 API。"""
from __future__ import annotations

import pytest


def test_students_list(client, auth_headers):
    body = client.get("/api/v1/students", headers=auth_headers).json()
    assert body["code"] == 0
    assert isinstance(body["data"]["items"], list) and body["data"]["total"] >= 1


def test_students_detail(client, auth_headers):
    sid = client.get("/api/v1/students", headers=auth_headers).json()["data"]["items"][0]["id"]
    body = client.get(f"/api/v1/students/{sid}", headers=auth_headers).json()
    assert body["code"] == 0
    d = body["data"]
    assert d["contacts"] and d["timeline"] and d["statusRecord"]
    assert "****" in d["phoneMasked"]  # 敏感字段脱敏口径


TID = 1000000000000000001


@pytest.fixture()
def org_class(db_mode):
    """正式建档必须有完整学院/专业/班级，故测试自建一套并返回班级 ID。"""
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=TID, college_name="测试学院", status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=TID, college_id=col.id, major_name="测试专业", status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="测试2601",
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        cid = cls.id
        db.commit()
        return str(cid)
    finally:
        db.close()


def test_create_student(client, auth_headers, org_class):
    body = client.post("/api/v1/students", headers=auth_headers,
                       json={"studentNo": "2099115999", "realName": "测试新生",
                             "phone": "13800001111", "classId": org_class}).json()
    assert body["code"] == 0
    assert body["data"]["studentNo"] == "2099115999"
    assert "****" in body["data"]["phoneMasked"]


def test_void_student_is_logical_delete(client, auth_headers, org_class):
    sid = client.post("/api/v1/students", headers=auth_headers,
                      json={"studentNo": "2099115998", "realName": "待作废",
                            "classId": org_class}).json()["data"]["id"]
    body = client.post(f"/api/v1/students/{sid}/void", headers=auth_headers,
                       json={"reason": "重复建档需要作废"}).json()
    assert body["code"] == 0
    assert body["data"]["physicalDelete"] is False and body["data"]["isDeleted"] is True
    # 作废后列表不可见（默认过滤 is_deleted）
    items = client.get("/api/v1/students?keyword=待作废", headers=auth_headers).json()["data"]["items"]
    assert all(r["id"] != sid for r in items)


def test_void_requires_reason(client, auth_headers):
    sid = client.get("/api/v1/students", headers=auth_headers).json()["data"]["items"][0]["id"]
    resp = client.post(f"/api/v1/students/{sid}/void", headers=auth_headers, json={"reason": "短"})
    assert resp.json()["code"] in (400001, 422001)


def test_void_then_create_is_blocked_not_auto_restored(client, auth_headers, org_class):
    """作废后同号再建档必须被拦。

    学号租户内永久唯一：作废档案只能走主档恢复流程/身份核验，不能靠再提交一次
    建档表单把已退学、已回收的学生悄悄改回在籍（补充审计 §7.5）。
    """
    no = "2099777888"
    created = client.post("/api/v1/students", headers=auth_headers, json={
        "studentNo": no, "realName": "复活甲", "phone": "13900001111", "classId": org_class,
    }).json()
    assert created["code"] == 0
    sid = created["data"]["id"]
    voided = client.post(f"/api/v1/students/{sid}/void", headers=auth_headers, json={
        "reason": "测试作废后不可自动复活",
    }).json()
    assert voided["code"] == 0 and voided["data"]["isDeleted"] is True
    again = client.post("/api/v1/students", headers=auth_headers, json={
        "studentNo": no, "realName": "复活乙", "phone": "13900002222", "classId": org_class,
    }).json()
    assert again["code"] != 0, "作废学号不应被建档表单自动复活"
    assert "作废" in (again.get("message") or "")
