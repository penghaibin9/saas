"""6 域通用导出：真实 xlsx + 用途校验 + 未知域拒绝 + 审计。"""
from __future__ import annotations

from datetime import datetime

MAIN_TID = 1000000000000000001


def _seed_intern(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord
    db = get_sessionmaker()()
    try:
        r = InternshipRecord(tenant_id=MAIN_TID, student_id=db_mode["student"], enterprise_name="测试企业",
                             position_name="开发实习生", advisor_name="刘强", status="ONBOARD",
                             risk_level="LOW", intern_start_date=datetime(2026, 3, 2))
        db.add(r)
        db.commit()
        return r.id
    finally:
        db.close()


def test_export_domain_success(client, auth_headers, db_mode):
    _seed_intern(db_mode)
    r = client.post("/api/v1/export/domain/internship", headers=auth_headers,
                    json={"purpose": "实习中期检查名册导出"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "SUCCESS"
    assert r["data"]["rowCount"] >= 1 and r["data"]["fileName"].endswith(".xlsx")
    assert "已脱敏" in r["data"]["securityNotice"]


def test_export_purpose_required(client, auth_headers, db_mode):
    _seed_intern(db_mode)
    bad = client.post("/api/v1/export/domain/internship", headers=auth_headers,
                      json={"purpose": "x"}).json()
    assert bad["code"] == 422001


def test_export_unknown_domain(client, auth_headers, db_mode):
    bad = client.post("/api/v1/export/domain/nosuch", headers=auth_headers,
                      json={"purpose": "测试导出用途说明"}).json()
    assert bad["code"] == 422001


def test_export_all_six_domains(client, auth_headers, db_mode):
    # 各域空数据也应成功导出（0 行 + 表头 + 水印）
    from app.core.token_store import reset_all_for_tests
    for d in ("internship", "orientation", "campus-service", "academic", "graduation", "employment"):
        reset_all_for_tests()  # 逐个重置导出限流窗口（限流本身另有用例覆盖）
        r = client.post(f"/api/v1/export/domain/{d}", headers=auth_headers,
                        json={"purpose": f"{d} 台账合规导出"}).json()
        assert r["code"] == 0 and r["data"]["status"] == "SUCCESS", (d, r)


def test_export_requires_login(client):
    assert client.post("/api/v1/export/domain/internship", json={"purpose": "xxxxx"}).json()["code"] == 401001
