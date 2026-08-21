"""6 域通用导出：真实 xlsx + 用途校验 + 未知域拒绝 + 审计。"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

MAIN_TID = 1000000000000000001


def _seed_intern(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=MAIN_TID,
            batch_name=f"通用导出批次-{uuid4().hex[:6]}",
            batch_no=f"EXP-{uuid4().hex[:8]}",
            status="RUNNING",
            start_date=datetime(2026, 3, 1),
            end_date=datetime(2026, 8, 31),
            planned_count=10,
        )
        db.add(batch)
        db.flush()
        r = InternshipRecord(
            tenant_id=MAIN_TID,
            student_id=db_mode["student"],
            batch_id=batch.id,
            enterprise_name="测试企业",
            position_name="开发实习生",
            advisor_name="刘强",
            status="ONBOARD",
            risk_level="LOW",
            intern_start_date=datetime(2026, 3, 2),
        )
        db.add(r)
        db.commit()
        return {"recordId": r.id, "batchId": batch.id}
    finally:
        db.close()


def test_export_domain_success(client, auth_headers, db_mode):
    seeded = _seed_intern(db_mode)
    r = client.post(
        "/api/v1/export/domain/internship",
        headers=auth_headers,
        json={"purpose": "实习中期检查名册导出", "batchId": str(seeded["batchId"])},
    ).json()
    assert r["code"] == 0 and r["data"]["status"] == "SUCCESS"
    assert r["data"]["rowCount"] >= 1 and r["data"]["fileName"].endswith(".xlsx")
    assert "已脱敏" in r["data"]["securityNotice"]


def test_export_purpose_required(client, auth_headers, db_mode):
    seeded = _seed_intern(db_mode)
    bad = client.post(
        "/api/v1/export/domain/internship",
        headers=auth_headers,
        json={"purpose": "x", "batchId": str(seeded["batchId"])},
    ).json()
    assert bad["code"] == 422001


def test_export_internship_requires_batch_context(client, auth_headers, db_mode):
    _seed_intern(db_mode)
    bad = client.post(
        "/api/v1/export/domain/internship",
        headers=auth_headers,
        json={"purpose": "实习批次台账合规导出"},
    ).json()
    assert bad["code"] == 422001
    assert "batchId" in bad["message"]


def test_export_unknown_domain(client, auth_headers, db_mode):
    bad = client.post("/api/v1/export/domain/nosuch", headers=auth_headers,
                      json={"purpose": "测试导出用途说明"}).json()
    assert bad["code"] == 422001


def test_export_all_six_domains(client, auth_headers, db_mode, monkeypatch):
    # 本用例验证六域内容/格式覆盖，不重复验证“5 次/分钟”限流；P0 后限流权威已迁到
    # MySQL，旧 reset_all_for_tests() 只清进程内存，继续调用会让第六域被真实限流误伤。
    # 只在本用例隔离 API limiter，不抬生产阈值；限流本身由独立安全测试锁定。
    from app.api.v1 import import_export as import_export_api
    monkeypatch.setattr(import_export_api, "_limit_operation", lambda *a, **k: None)

    seeded = _seed_intern(db_mode)
    for d in ("internship", "orientation", "campus-service", "academic", "graduation", "employment"):
        body = {"purpose": f"{d} 台账合规导出"}
        if d == "internship":
            body["batchId"] = str(seeded["batchId"])
        r = client.post(f"/api/v1/export/domain/{d}", headers=auth_headers, json=body).json()
        assert r["code"] == 0 and r["data"]["status"] == "SUCCESS", (d, r)


def test_export_requires_login(client):
    assert client.post("/api/v1/export/domain/internship", json={"purpose": "xxxxx"}).json()["code"] == 401001
