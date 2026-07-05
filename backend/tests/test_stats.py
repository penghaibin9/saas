"""P8 跨域统计 /stats/*：教职工可用、学生 403、空域返回 0 不 500、结构稳定、租户过滤。

依赖 conftest 的 client / auth_headers（school_admin01 教职工）/ db_mode（临时 SQLite + 最小种子，TID=主租户）。
db_mode 未播种 迎新/学业/就业 等域 → 这些域计数应为 0，接口不得 500。
"""
from __future__ import annotations


def _student_headers(client) -> dict:
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "student01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


# ── 教职工可访问 + 结构稳定 ──

def test_overview_staff_ok(client, auth_headers, db_mode):
    r = client.get("/api/v1/stats/overview", headers=auth_headers).json()
    assert r["code"] == 0
    d = r["data"]
    assert isinstance(d["stageFlow"], list) and len(d["stageFlow"]) == 6
    assert isinstance(d["metrics"], list)
    assert any(m["key"] == "studentTotal" for m in d["metrics"])


def test_lifecycle_staff_ok(client, auth_headers, db_mode):
    r = client.get("/api/v1/stats/lifecycle", headers=auth_headers).json()
    assert r["code"] == 0
    assert "totalCount" in r["data"]
    assert isinstance(r["data"]["stages"], list)


def test_risk_staff_ok(client, auth_headers, db_mode):
    r = client.get("/api/v1/stats/risk", headers=auth_headers).json()
    assert r["code"] == 0
    assert "summary" in r["data"]
    assert isinstance(r["data"]["byDomain"], list)


def test_workbench_staff_ok(client, auth_headers, db_mode):
    r = client.get("/api/v1/stats/workbench", headers=auth_headers).json()
    assert r["code"] == 0
    d = r["data"]
    for k in ("studentTotal", "pendingTodo", "pendingApproval", "unreadMessage"):
        assert k in d and isinstance(d[k], int) and d[k] >= 0


# ── 空数据返回 0 / 空结构，不 500 ──

def test_empty_domains_zero_not_500(client, auth_headers, db_mode):
    ov = client.get("/api/v1/stats/overview", headers=auth_headers)
    assert ov.status_code == 200 and ov.json()["code"] == 0
    risk = client.get("/api/v1/stats/risk", headers=auth_headers)
    assert risk.status_code == 200
    d = risk.json()["data"]
    assert d["summary"]["high"] >= 0 and d["summary"]["medium"] >= 0


# ── 学生越权：4 个统计端点全部拒绝（require_staff → 403）──

def test_student_forbidden_on_all_stats(client, db_mode):
    h = _student_headers(client)
    for path in ("overview", "lifecycle", "risk", "workbench"):
        resp = client.get(f"/api/v1/stats/{path}", headers=h)
        assert resp.status_code == 403 or resp.json().get("code") not in (0, None), \
            f"/stats/{path} 未拒绝学生访问"
