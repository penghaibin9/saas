"""学生主档第一批 API。"""
from __future__ import annotations


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


def test_create_student(client, auth_headers):
    body = client.post("/api/v1/students", headers=auth_headers,
                       json={"studentNo": "2099115999", "realName": "测试新生", "phone": "13800001111"}).json()
    assert body["code"] == 0
    assert body["data"]["studentNo"] == "2099115999"
    assert "****" in body["data"]["phoneMasked"]


def test_void_student_is_logical_delete(client, auth_headers):
    sid = client.post("/api/v1/students", headers=auth_headers,
                      json={"studentNo": "2099115998", "realName": "待作废"}).json()["data"]["id"]
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


def test_void_then_create_restores_same_id(client, auth_headers):
    no = "2099777888"
    created = client.post("/api/v1/students", headers=auth_headers, json={
        "studentNo": no, "realName": "复活甲", "phone": "13900001111",
    }).json()
    assert created["code"] == 0
    sid = created["data"]["id"]
    voided = client.post(f"/api/v1/students/{sid}/void", headers=auth_headers, json={
        "reason": "测试作废后复活原档",
    }).json()
    assert voided["code"] == 0 and voided["data"]["isDeleted"] is True
    again = client.post("/api/v1/students", headers=auth_headers, json={
        "studentNo": no, "realName": "复活乙", "phone": "13900002222",
    }).json()
    assert again["code"] == 0
    assert again["data"]["id"] == sid
    assert again["data"].get("restored") is True
    assert again["data"]["realName"] == "复活乙"
