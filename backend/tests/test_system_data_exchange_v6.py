from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.data_exchange import ExportJob, ImportJob, ImportRowError
from app.services import data_exchange_job_service as jobs

TENANT_ID = 1000000000000000001
OTHER_TENANT_ID = 1000000000000000002
SYS_ADMIN = {
    "userId": 101,
    "tenantId": TENANT_ID,
    "currentRoleCode": "SYS_ADMIN",
    "loginName": "sys_admin_v6",
}
ACADEMIC_ADMIN = {
    "userId": 202,
    "tenantId": TENANT_ID,
    "currentRoleCode": "ACADEMIC_ADMIN",
    "loginName": "academic_admin_v6",
}


def _import(
    *,
    tenant_id: int = TENANT_ID,
    operator_id: int | None,
    module_code: str,
    adapter_ref: str,
    status: str = "VALIDATED",
    adapter_type: str = jobs.IMPORT_ADAPTER_EXCEL,
    created_at: datetime | None = None,
) -> ImportJob:
    return ImportJob(
        tenant_id=tenant_id,
        module_code=module_code,
        import_type=f"{module_code}_TEST",
        source_file_id=None,
        adapter_type=adapter_type,
        adapter_ref=adapter_ref,
        template_version="v1",
        status=status,
        total_rows=10,
        valid_rows=10 if status != "VALIDATION_FAILED" else 8,
        invalid_rows=2 if status == "VALIDATION_FAILED" else 0,
        confirmed_rows=0,
        operator_id=operator_id,
        operator_name=f"operator-{operator_id}" if operator_id else "",
        expires_at=datetime.utcnow() + timedelta(hours=24),
        source_snapshot_json={},
        result_json={},
        created_by=operator_id,
        created_at=created_at or datetime.utcnow(),
        version=0,
    )


def _export(
    *,
    tenant_id: int = TENANT_ID,
    operator_id: int | None,
    module_code: str,
    adapter_ref: str,
    status: str = "SUCCEEDED",
    created_at: datetime | None = None,
) -> ExportJob:
    return ExportJob(
        tenant_id=tenant_id,
        module_code=module_code,
        export_type="TEST_EXPORT",
        purpose="V6 数据交换测试",
        adapter_type="V6_TEST",
        adapter_ref=adapter_ref,
        status=status,
        progress=100 if status == "SUCCEEDED" else 0,
        row_count=5,
        file_object_id=9001 if status == "SUCCEEDED" else None,
        expires_at=datetime.utcnow() + timedelta(hours=24),
        downloaded_count=0,
        operator_id=operator_id,
        finished_at=datetime.utcnow() if status == "SUCCEEDED" else None,
        result_json={},
        created_by=operator_id,
        created_at=created_at or datetime.utcnow(),
        version=0,
    )


@pytest.fixture()
def exchange_seed(db_mode, monkeypatch):
    monkeypatch.setattr(jobs, "_tenant_id", lambda: TENANT_ID)
    db = get_sessionmaker()()
    try:
        own_import = _import(
            operator_id=SYS_ADMIN["userId"],
            module_code="SYSTEM",
            adapter_ref="own-system-import",
        )
        other_system_import = _import(
            operator_id=303,
            module_code="SYSTEM",
            adapter_ref="other-system-import",
        )
        academic_failed = _import(
            operator_id=ACADEMIC_ADMIN["userId"],
            module_code="ACADEMIC_AFFAIRS",
            adapter_ref="academic-failed",
            status="VALIDATION_FAILED",
        )
        retryable = _import(
            operator_id=SYS_ADMIN["userId"],
            module_code="SYSTEM",
            adapter_ref="retryable-scan",
            status="VALIDATION_FAILED",
            adapter_type=jobs.PENDING_IDENTITY_ADAPTER,
        )
        other_tenant = _import(
            tenant_id=OTHER_TENANT_ID,
            operator_id=SYS_ADMIN["userId"],
            module_code="SYSTEM",
            adapter_ref="other-tenant-import",
        )
        own_export = _export(
            operator_id=SYS_ADMIN["userId"],
            module_code="SYSTEM",
            adapter_ref="own-system-export",
        )
        academic_export = _export(
            operator_id=ACADEMIC_ADMIN["userId"],
            module_code="ACADEMIC_AFFAIRS",
            adapter_ref="academic-export",
        )
        db.add_all([
            own_import,
            other_system_import,
            academic_failed,
            retryable,
            other_tenant,
            own_export,
            academic_export,
        ])
        db.flush()
        db.add_all([
            ImportRowError(
                tenant_id=TENANT_ID,
                import_job_id=academic_failed.id,
                sheet_name="导入模板",
                row_no=2,
                field_code="studentNo",
                error_code="REQUIRED",
                error_message="学号不能为空",
                raw_snapshot_json={"row": 2},
                created_by=ACADEMIC_ADMIN["userId"],
            ),
            ImportRowError(
                tenant_id=TENANT_ID,
                import_job_id=academic_failed.id,
                sheet_name="导入模板",
                row_no=5,
                field_code="classCode",
                error_code="NOT_FOUND",
                error_message="班级不存在",
                raw_snapshot_json={"row": 5},
                created_by=ACADEMIC_ADMIN["userId"],
            ),
        ])
        db.commit()
        return {
            "own_import": own_import.id,
            "other_system_import": other_system_import.id,
            "academic_failed": academic_failed.id,
            "retryable": retryable.id,
            "other_tenant": other_tenant.id,
        }
    finally:
        db.close()


def test_visibility_is_explicit_and_cross_tenant_is_always_excluded(exchange_seed):
    own = jobs.list_jobs(user=SYS_ADMIN, visibility="OWN", page=1, page_size=100)
    assert own["total"] == 3
    assert {item["id"] for item in own["list"]} >= {
        str(exchange_seed["own_import"]),
        str(exchange_seed["retryable"]),
    }
    assert str(exchange_seed["other_system_import"]) not in {item["id"] for item in own["list"]}

    tenant = jobs.list_jobs(user=SYS_ADMIN, visibility="TENANT", page=1, page_size=100)
    assert tenant["total"] == 6
    assert str(exchange_seed["other_tenant"]) not in {item["id"] for item in tenant["list"]}

    academic = jobs.list_jobs(
        user=ACADEMIC_ADMIN,
        visibility="MODULE",
        module_code="ACADEMIC_AFFAIRS",
        page=1,
        page_size=100,
    )
    assert academic["total"] == 2
    assert {item["moduleCode"] for item in academic["list"]} == {"ACADEMIC_AFFAIRS"}

    with pytest.raises(AppException):
        jobs.list_jobs(user=ACADEMIC_ADMIN, visibility="TENANT")

    with pytest.raises(AppException):
        jobs.get_import_job(str(exchange_seed["other_tenant"]), user=SYS_ADMIN)


def test_independent_summary_matches_database_not_current_page(exchange_seed):
    first_page = jobs.list_jobs(user=SYS_ADMIN, visibility="TENANT", page=1, page_size=1)
    summary = jobs.get_summary(user=SYS_ADMIN, visibility="TENANT")

    assert len(first_page["list"]) == 1
    assert first_page["total"] == 6
    assert summary["total"] == 6
    assert summary["imports"] == 4
    assert summary["exports"] == 2
    assert summary["failed"] == 2
    assert summary["receipts"] == 2


def test_database_pagination_is_stable_and_does_not_materialize_full_tables(exchange_seed):
    db = get_sessionmaker()()
    try:
        for index in range(25):
            db.add(_import(
                operator_id=SYS_ADMIN["userId"],
                module_code="SYSTEM",
                adapter_ref=f"pagination-{index}",
                created_at=datetime.utcnow() + timedelta(seconds=index),
            ))
        db.commit()
    finally:
        db.close()

    page_one = jobs.list_jobs(user=SYS_ADMIN, visibility="TENANT", page=1, page_size=5)
    page_two = jobs.list_jobs(user=SYS_ADMIN, visibility="TENANT", page=2, page_size=5)
    assert page_one["total"] == 31
    assert len(page_one["list"]) == 5
    assert len(page_two["list"]) == 5
    assert {item["id"] for item in page_one["list"]}.isdisjoint(
        {item["id"] for item in page_two["list"]}
    )

    source = Path(jobs.__file__).read_text(encoding="utf-8")
    assert "union_all(*parts)" in source
    assert ".offset((page - 1) * page_size)" in source
    assert "rows.extend(_import_row" not in source
    assert "rows.extend(_export_row" not in source


def test_error_rows_are_server_authoritative_and_paginated(exchange_seed):
    result = jobs.get_import_errors(
        str(exchange_seed["academic_failed"]),
        user=ACADEMIC_ADMIN,
        visibility="MODULE",
        module_code="ACADEMIC_AFFAIRS",
        page=1,
        page_size=1,
    )
    assert result["total"] == 2
    assert len(result["list"]) == 1
    assert result["list"][0]["rowNo"] == 2
    assert result["list"][0]["message"] == "学号不能为空"


def test_cancel_and_retry_use_expected_version_and_real_state_boundaries(exchange_seed):
    cancelled = jobs.cancel_import_job(
        str(exchange_seed["own_import"]),
        expected_version=0,
        reason="学校管理员确认本批次不再执行",
        user=SYS_ADMIN,
    )
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancellable"] is False

    with pytest.raises(AppException):
        jobs.cancel_import_job(
            str(exchange_seed["own_import"]),
            expected_version=0,
            reason="再次取消应被版本锁拒绝",
            user=SYS_ADMIN,
        )

    retried = jobs.retry_import_job(
        str(exchange_seed["retryable"]),
        expected_version=0,
        user=SYS_ADMIN,
    )
    assert retried["status"] == "SCANNING"
    assert retried["result"]["retryCount"] == 1

    with pytest.raises(AppException):
        jobs.retry_import_job(
            str(exchange_seed["academic_failed"]),
            expected_version=0,
            user=ACADEMIC_ADMIN,
        )


def test_frontend_contract_sends_idempotency_header_and_removes_browser_prompts():
    repo_root = Path(__file__).resolve().parents[2]
    api_source = (repo_root / "frontend/src/modules/system/api/dataExchange.api.js").read_text(encoding="utf-8")
    view_source = (repo_root / "frontend/src/modules/system/views/SystemDataExchangeView.vue").read_text(encoding="utf-8")

    assert "Idempotency-Key" in api_source
    assert "createIdempotencyKey" in api_source
    assert "data-exchange/summary" in api_source
    assert "getImportErrors" in api_source
    assert "window.confirm" not in view_source
    assert "window.prompt" not in view_source
    assert "强敏感、24 小时有效、一次性下载" in view_source
