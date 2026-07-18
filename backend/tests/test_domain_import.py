"""6 域通用导入：Dry-Run 校验（必填/批内重复/库内重复）+ 确认写入 + 未过校验禁确认。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException

MAIN_TID = 1000000000000000001


def test_academic_import_dry_run_and_confirm(client, auth_headers, db_mode):
    rows = [{"name": "导入生A", "studentNo": "IMP2026001", "className": "软件2301班"},
            {"name": "导入生B", "studentNo": "IMP2026002"},
            {"name": "", "studentNo": "IMP2026003"},          # 姓名缺失
            {"name": "重复", "studentNo": "IMP2026001"}]        # 批内重复
    dr = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                     json={"rows": rows}).json()
    assert dr["code"] == 0 and dr["data"]["status"] == "DRY_RUN_FAILED"
    assert dr["data"]["okRows"] == 2 and dr["data"]["errorRows"] == 2

    # 全部合法 → 通过 → 确认
    good = [{"name": "导入生C", "studentNo": "IMP2026010"}, {"name": "导入生D", "studentNo": "IMP2026011"}]
    dr2 = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                      json={"rows": good}).json()
    assert dr2["data"]["status"] == "DRY_RUN_PASSED" and dr2["data"]["okRows"] == 2
    cf = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                     json={"batchNo": dr2["data"]["batchNo"]}).json()
    assert cf["code"] == 0 and cf["data"]["insertedRows"] == 2
    # 已导入的学号再导入 → 库内重复
    dr3 = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                      json={"rows": [{"name": "x", "studentNo": "IMP2026010"}]}).json()
    assert dr3["data"]["errorRows"] == 1


def test_import_failed_batch_cannot_confirm(client, auth_headers, db_mode):
    dr = client.post("/api/v1/import/domain/employment/validate", headers=auth_headers,
                     json={"rows": [{"name": "", "studentNo": ""}]}).json()
    assert dr["data"]["status"] == "DRY_RUN_FAILED"
    cf = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                     json={"batchNo": dr["data"]["batchNo"]}).json()
    assert cf["code"] == 422001


def test_import_unknown_domain(client, auth_headers, db_mode):
    bad = client.post("/api/v1/import/domain/nosuch/validate", headers=auth_headers,
                      json={"rows": []}).json()
    assert bad["code"] == 422001


def test_import_requires_login(client):
    assert client.post("/api/v1/import/domain/academic/validate", json={"rows": []}).json()["code"] == 401001


def test_import_rejects_unbounded_batches():
    from app.services import domain_import_service as service

    with pytest.raises(AppException) as exc:
        service.dry_run("academic", [{}] * (service.MAX_IMPORT_ROWS + 1))
    assert exc.value.code == "VALIDATION_ERROR"
