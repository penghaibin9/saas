import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_operations_python_sources_are_parseable():
    for relative in (
        "backend/app/models/affairs_operations.py",
        "backend/app/services/affairs_operations_service.py",
        "backend/app/services/affairs_operations_final_guard.py",
        "backend/app/api/v1/affairs_operations_api.py",
        "backend/alembic/versions/0127_affairs_material_batch_ops.py",
    ):
        ast.parse(_read(relative), filename=relative)


def test_material_and_batch_schema_is_persistent_and_on_single_chain():
    migration = _read("backend/alembic/versions/0127_affairs_material_batch_ops.py")
    models = _read("backend/app/models/affairs_operations.py")

    assert 'down_revision = "0126_aa_grade_task_uniqueness_guard"' in migration
    for table in (
        "t_affairs_material_requirement",
        "t_affairs_material_submission",
        "t_affairs_batch_job",
        "t_affairs_batch_job_item",
    ):
        assert table in migration
        assert table in models
    assert "uk_affairs_material_submission_version" in migration
    assert "uk_affairs_batch_job_idempotency" in migration
    assert "uk_affairs_batch_job_item_key" in migration


def test_material_supplement_is_versioned_and_object_scoped():
    service = _read("backend/app/services/affairs_operations_service.py")
    guard = _read("backend/app/services/affairs_operations_final_guard.py")

    assert 'latest.status = "SUPERSEDED"' in service
    assert "version_no = int(latest.version_no if latest else 0) + 1" in service
    assert 'file.biz_type = "MATERIAL_REQUIREMENT"' in service
    assert 'file.visibility = "STUDENT_SELF"' in service
    assert "只能提交本人上传的文件" in service
    assert "build_affairs_context(user or {}, db).require_student" in guard
    assert "MATERIAL_REQUIREMENT" in guard
    assert "文件授权必须 fail-closed" in guard


def test_material_and_batch_endpoints_are_complete():
    api = _read("backend/app/api/v1/affairs_operations_api.py")
    for route in (
        '/student-affairs/material-requirements"',
        '/student-affairs/material-requirements/{requirement_id}/review"',
        '/mobile/affairs/material-requirements"',
        '/mobile/affairs/material-requirements/{requirement_id}/submissions"',
        '/student-affairs/batch-jobs"',
        '/student-affairs/batch-jobs/{job_id}"',
        '/student-affairs/batch-jobs/{job_id}/retry-failed"',
    ):
        assert route in api
    assert "version: int = Field(..., ge=0" in api


def test_safe_batch_is_low_risk_idempotent_and_retryable_per_item():
    service = _read("backend/app/services/affairs_operations_service.py")
    guard = _read("backend/app/services/affairs_operations_final_guard.py")

    assert 'job_type != "MATERIAL_REMIND"' in service
    assert "审批/发放/处分等必须逐条处理" in service
    assert 'item.action != "REMIND"' in service
    assert "check_version(req.version, item.expected_version)" in service
    assert "failed_only=True" in _read("backend/app/api/v1/affairs_operations_api.py")
    assert "IDEMPOTENCY_CONFLICT" in guard
    assert "同一幂等键不能用于不同的批次记录" in guard
    assert "批量提醒每一条都必须携带当前材料版本" in guard
    assert 'row.status == "FAILED"' in guard
    assert "row.attempt_count = before + 1" in guard


def test_dorm_exception_returns_risk_responsibility_and_actions_without_auto_close():
    service = _read("backend/app/services/affairs_operations_service.py")

    assert 'AffairsRiskRecord.source == "DORM"' in service
    for field in (
        '"ownerName"', '"dueAt"', '"overdue"', '"allowedActions"',
        '"riskProjection"', '"relatedRiskId"',
    ):
        assert field in service
    assert "original_handle(exception_id" in service
    assert "risk_service.close" not in service


def test_install_order_preserves_student_contract_security_and_final_file_guard():
    router = _read("backend/app/api/v1/router.py")

    assert router.index("install_student_contract_security_guard()") < router.index("install_affairs_operations()")
    assert router.index("install_affairs_operations()") < router.index("install_affairs_operations_final_guard()")
    assert "affairs_operations_router" in router


def test_temporary_student_affairs_diagnostics_workflow_is_removed():
    assert not (ROOT / ".github/workflows/student-affairs-diagnostics.yml").exists()
