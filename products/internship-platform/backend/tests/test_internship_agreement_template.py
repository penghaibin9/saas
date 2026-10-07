"""岗位实习中心 · 实习协议模板库测试：CRUD + 状态机(草稿/启用/停用/归档)
+ 默认模板(同类型唯一/停用归档失默认) + 适用范围筛选 + 变量字典 + 正文 + 审计 + 越权404。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

BASE = "/api/v1/internship/agreement-templates"


def _mk(client, h, **over):
    body = {"name": "顶岗实习三方协议", "category": "三方协议", "version": "v1.0",
            "scopeGrades": ["2024级"], "scopeCollegeIds": ["101"],
            "body": "甲方：{{schoolName}}  乙方：{{companyName}}  学生：{{studentName}}",
            "variables": [{"key": "studentName", "label": "学生姓名", "example": "张三"}],
            "remark": "标准三方协议"}
    body.update(over)
    return client.post(BASE, headers=h, json=body).json()


def _enable(client, h, tid):
    return client.post(f"{BASE}/{tid}/status", headers=h, json={"action": "ENABLE"}).json()


def test_create_default_draft(client, auth_headers, db_mode):
    r = _mk(client, auth_headers)
    assert r["code"] == 0
    assert r["data"]["status"] == "DRAFT" and r["data"]["isDefault"] is False
    assert r["data"]["version"] == "v1.0"
    assert r["data"]["scopeSummary"]  # 适用范围摘要非空


def test_list_and_detail_with_body_variables(client, auth_headers, db_mode):
    tid = _mk(client, auth_headers)["data"]["id"]
    lst = client.get(BASE, headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    d = client.get(f"{BASE}/{tid}", headers=auth_headers).json()
    assert d["code"] == 0
    assert "studentName" in d["data"]["body"]
    assert d["data"]["variables"][0]["key"] == "studentName"
    assert "auditTrail" in d["data"] and len(d["data"]["auditTrail"]) >= 1  # CREATE 留痕


def test_update_then_archived_locked(client, auth_headers, db_mode):
    tid = _mk(client, auth_headers)["data"]["id"]
    up = client.put(f"{BASE}/{tid}", headers=auth_headers,
                    json={"name": "顶岗实习三方协议(修订)", "version": "v1.1"}).json()
    assert up["code"] == 0 and up["data"]["version"] == "v1.1"
    # 归档后不可编辑
    client.post(f"{BASE}/{tid}/status", headers=auth_headers, json={"action": "ARCHIVE"})
    locked = client.put(f"{BASE}/{tid}", headers=auth_headers, json={"name": "X"}).json()
    assert locked["code"] != 0


def test_status_machine(client, auth_headers, db_mode):
    tid = _mk(client, auth_headers)["data"]["id"]
    assert _enable(client, auth_headers, tid)["data"]["status"] == "ENABLED"
    dis = client.post(f"{BASE}/{tid}/status", headers=auth_headers, json={"action": "DISABLE"}).json()
    assert dis["data"]["status"] == "DISABLED"
    # DISABLED 再 ENABLE 合法
    assert _enable(client, auth_headers, tid)["data"]["status"] == "ENABLED"
    # 非法：ENABLED 不能直接再 ENABLE
    bad = client.post(f"{BASE}/{tid}/status", headers=auth_headers, json={"action": "ENABLE"}).json()
    assert bad["code"] != 0


def test_default_requires_enabled_and_unique_per_category(client, auth_headers, db_mode):
    t1 = _mk(client, auth_headers, name="三方协议A")["data"]["id"]
    t2 = _mk(client, auth_headers, name="三方协议B")["data"]["id"]
    # 草稿不能设默认
    assert client.post(f"{BASE}/{t1}/default", headers=auth_headers, json={"on": True}).json()["code"] != 0
    _enable(client, auth_headers, t1)
    _enable(client, auth_headers, t2)
    assert client.post(f"{BASE}/{t1}/default", headers=auth_headers, json={"on": True}).json()["data"]["isDefault"] is True
    # 设 t2 默认后，t1 失默认（同类型唯一）
    assert client.post(f"{BASE}/{t2}/default", headers=auth_headers, json={"on": True}).json()["data"]["isDefault"] is True
    d1 = client.get(f"{BASE}/{t1}", headers=auth_headers).json()
    assert d1["data"]["isDefault"] is False


def test_disable_clears_default(client, auth_headers, db_mode):
    tid = _mk(client, auth_headers)["data"]["id"]
    _enable(client, auth_headers, tid)
    client.post(f"{BASE}/{tid}/default", headers=auth_headers, json={"on": True})
    dis = client.post(f"{BASE}/{tid}/status", headers=auth_headers, json={"action": "DISABLE"}).json()
    assert dis["data"]["isDefault"] is False  # 停用即失去默认


def test_scope_filter(client, auth_headers, db_mode):
    _mk(client, auth_headers, name="信工院模板", scopeCollegeIds=["101"], scopeGrades=["2024级"])
    _mk(client, auth_headers, name="商学院模板", scopeCollegeIds=["202"], scopeGrades=["2023级"])
    r = client.get(f"{BASE}?collegeId=202", headers=auth_headers).json()
    assert r["code"] == 0
    assert all("202" in [str(i) for i in x["scopeCollegeIds"]] for x in r["data"]["items"])
    assert any(x["name"] == "商学院模板" for x in r["data"]["items"])


def test_variables_preset(client, auth_headers, db_mode):
    r = client.get(f"{BASE}/variables", headers=auth_headers).json()
    assert r["code"] == 0
    keys = [v["key"] for v in r["data"]]
    for k in ("studentName", "companyName", "positionName", "internPeriod"):
        assert k in keys


def test_stats(client, auth_headers, db_mode):
    _mk(client, auth_headers)
    tid = _mk(client, auth_headers)["data"]["id"]
    _enable(client, auth_headers, tid)
    s = client.get(f"{BASE}/stats", headers=auth_headers).json()
    assert s["code"] == 0 and s["data"]["total"] >= 2
    assert any(x["status"] == "ENABLED" for x in s["data"]["byStatus"])


def test_not_found(client, auth_headers, db_mode):
    assert client.get(f"{BASE}/99999999", headers=auth_headers).json()["code"] != 0
    assert client.put(f"{BASE}/99999999", headers=auth_headers, json={"name": "X"}).json()["code"] != 0
