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


def test_affairs_summary_shape(client, auth_headers):
    """学生360·学工摘要：6 域聚合结构齐全，涉密明细不外泄（只出计数/状态）。"""
    sid = client.get("/api/v1/students", headers=auth_headers).json()["data"]["items"][0]["id"]
    body = client.get(f"/api/v1/students/{sid}/affairs-summary", headers=auth_headers).json()
    assert body["code"] == 0
    d = body["data"]
    for k in ("leave", "grant", "discipline", "dorm", "mental", "family"):
        assert k in d, f"缺少学工摘要域：{k}"
    assert isinstance(d["leave"]["total"], int) and isinstance(d["leave"]["pending"], int)
    assert "approvedAmount" in d["grant"]
    assert "flag" in d["mental"] and "careLevel" in d["mental"]
    # 涉密辅导员备注/心理明细不出现在摘要里
    assert "counselorNote" not in d["mental"] and "summary" not in d["mental"]


def test_affairs_summary_db_mode(client, db_mode, auth_headers):
    """DB 真库模式：无学工记录时各域计数为 0，跨域聚合不 500（越权由数据范围拦）。"""
    sid = client.get("/api/v1/students", headers=auth_headers).json()["data"]["items"][0]["id"]
    body = client.get(f"/api/v1/students/{sid}/affairs-summary", headers=auth_headers).json()
    assert body["code"] == 0
    d = body["data"]
    assert d["leave"]["total"] == 0 and d["grant"]["total"] == 0 and d["family"]["total"] == 0
    assert d["dorm"]["building"] == "" and d["mental"]["flag"] is False
