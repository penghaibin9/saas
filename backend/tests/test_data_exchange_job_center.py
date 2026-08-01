from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1.data_exchange import ConfirmImportRequest
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


def test_confirm_request_forbids_frontend_rows_and_batch_number():
    request = ConfirmImportRequest(expectedVersion=3)
    assert request.expectedVersion == 3

    with pytest.raises(ValidationError):
        ConfirmImportRequest(expectedVersion=3, rows=[{"studentNo": "S001"}])

    with pytest.raises(ValidationError):
        ConfirmImportRequest(expectedVersion=3, batchNo="LEGACY-BATCH")


def test_stage3_models_use_frozen_table_names():
    assert ImportJob.__tablename__ == "t_import_job"
    assert ImportRowError.__tablename__ == "t_import_row_error"
    assert ExportJob.__tablename__ == "t_export_job"
    assert {column.name for column in ImportJob.__table__.columns} >= {
        "source_file_id", "adapter_type", "adapter_ref", "lease_token",
        "error_receipt_file_id", "credential_receipt_file_id", "version",
    }
    assert {column.name for column in ExportJob.__table__.columns} >= {
        "file_object_id", "expires_at", "downloaded_count", "revoked_at", "version",
    }


def test_import_projection_is_refresh_safe_and_versioned():
    row = SimpleNamespace(
        id=12,
        module_code="SYSTEM",
        import_type="IDENTITY_STUDENT",
        source_file_id=66,
        adapter_type=jobs.IMPORT_ADAPTER_IDENTITY,
        adapter_ref="IDIMP-1",
        template_version="v1",
        status="VALIDATED",
        total_rows=10,
        valid_rows=9,
        invalid_rows=1,
        confirmed_rows=0,
        error_receipt_file_id=70,
        credential_receipt_file_id=None,
        expires_at=None,
        confirmed_at=None,
        operator_name="系统管理员",
        result_json=None,
        error_message=None,
        version=4,
        created_at=None,
        updated_at=None,
    )
    data = jobs._import_row(row)
    assert data["id"] == "12"
    assert data["sourceFileId"] == "66"
    assert data["errorReceiptFileId"] == "70"
    assert data["version"] == 4
    assert data["status"] == "VALIDATED"
    assert data["cancellable"] is True
    assert data["retryable"] is False


def test_export_projection_marks_expired_output_unavailable():
    now = jobs._now()
    row = SimpleNamespace(
        id=21,
        module_code="SYSTEM",
        export_type="INITIAL_CREDENTIAL_RECEIPT",
        purpose="初始账号凭据",
        adapter_type="IMPORT_JOB",
        adapter_ref="12",
        status="SUCCEEDED",
        progress=100,
        row_count=3,
        file_object_id=88,
        expires_at=now,
        downloaded_count=0,
        revoked_at=None,
        revoke_reason=None,
        error_message=None,
        version=2,
        created_at=None,
        updated_at=None,
    )
    data = jobs._export_row(row)
    assert data["status"] == "EXPIRED"
    assert data["downloadable"] is False
    assert data["strongSensitive"] is True
    assert data["oneTimeTicket"] is True
    assert data["validityHours"] == 24


def test_owned_domain_job_is_visible_without_widening_module_or_null_operator_scope():
    owner = {
        "userId": 501,
        "tenantId": TENANT_ID,
        "currentRoleCode": "GD_MENTOR",
        "loginName": "graduation_mentor",
    }
    owned = SimpleNamespace(operator_id=501, created_by=501, module_code="GRADUATION")
    jobs._assert_row_visible(owned, owner)

    other_user_job = SimpleNamespace(operator_id=502, created_by=502, module_code="GRADUATION")
    with pytest.raises(AppException):
        jobs._assert_row_visible(other_user_job, owner)

    legacy_null_job = SimpleNamespace(operator_id=None, created_by=502, module_code="GRADUATION")
    with pytest.raises(AppException):
        jobs._assert_row_visible(legacy_null_job, owner)


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
    """一次 MySQL schema 建立内覆盖全部 V6 合同，避免每个断言重复重建约 250 张表。"""
    monkeypatch.setattr(jobs, "_tenant_id", lambda: TENANT_ID)
    db = get_sessionmaker()()
    try:
        own_import = _import(
            operator_id=SYS_ADMIN["userId"], module_code="SYSTEM", adapter_ref="own-system-import"
        )
        other_system_import = _import(
            operator_id=303, module_code="SYSTEM", adapter_ref="other-system-import"
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
            operator_id=SYS_ADMIN["userId"], module_code="SYSTEM", adapter_ref="own-system-export"
        )
        academic_export = _export(
            operator_id=ACADEMIC_ADMIN["userId"],
            module_code="ACADEMIC_AFFAIRS",
            adapter_ref="academic-export",
        )
        db.add_all([
            own_import, other_system_import, academic_failed, retryable,
            other_tenant, own_export, academic_export,
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


def test_v6_mysql_visibility_summary_pagination_errors_and_actions(exchange_seed):
    # OWN 不再把 operator_id 为空或他人任务隐式放给管理员。
    own = jobs.list_jobs(user=SYS_ADMIN, visibility="OWN", page=1, page_size=100)
    assert own["total"] == 3
    assert {item["id"] for item in own["list"]} >= {
        str(exchange_seed["own_import"]), str(exchange_seed["retryable"]),
    }
    assert str(exchange_seed["other_system_import"]) not in {item["id"] for item in own["list"]}

    # TENANT 仅含当前租户；MODULE 仅含有职责的业务模块。
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

    # summary 独立统计，不受当前页 pageSize 影响。
    first_page = jobs.list_jobs(user=SYS_ADMIN, visibility="TENANT", page=1, page_size=1)
    summary = jobs.get_summary(user=SYS_ADMIN, visibility="TENANT")
    assert len(first_page["list"]) == 1
    assert first_page["total"] == 6
    assert summary["total"] == 6
    assert summary["imports"] == 4
    assert summary["exports"] == 2
    assert summary["failed"] == 2
    assert summary["receipts"] == 2

    # 错误行来自服务端 ImportRowError，并使用数据库分页。
    errors = jobs.get_import_errors(
        str(exchange_seed["academic_failed"]),
        user=ACADEMIC_ADMIN,
        visibility="MODULE",
        module_code="ACADEMIC_AFFAIRS",
        page=1,
        page_size=1,
    )
    assert errors["total"] == 2
    assert len(errors["list"]) == 1
    assert errors["list"][0]["rowNo"] == 2
    assert errors["list"][0]["message"] == "学号不能为空"

    # 大任务列表仅读取当前页，分页稳定且不在 Python 全量拼接。
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

    # 取消与重试都执行 expectedVersion 和真实状态边界。
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
        str(exchange_seed["retryable"]), expected_version=0, user=SYS_ADMIN
    )
    assert retried["status"] == "SCANNING"
    assert retried["result"]["retryCount"] == 1
    with pytest.raises(AppException):
        jobs.retry_import_job(
            str(exchange_seed["academic_failed"]),
            expected_version=0,
            user=ACADEMIC_ADMIN,
        )


def test_v6_frontend_sends_idempotency_header_and_removes_browser_prompts():
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
