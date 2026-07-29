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
    assert "operations._require_student_scope" in guard
    assert "MATERIAL_REQUIREMENT" in guard
    assert "文件授权必须 fail-closed" in guard
    assert "row.current_submission_id = None" in guard


def test_dorm_material_scope_is_limited_to_managed_buildings():
    guard = _read("backend/app/services/affairs_operations_final_guard.py")

    assert 'ctx.scope_type != "DORM_BUILDING"' in guard
    assert "ctx.dorm_building_ids" in guard
    assert 'DormBed.status == "OCCUPIED"' in guard
    assert "DormTransfer.to_bed_id" in guard
    assert "该学生的住宿或调宿记录不在您的楼栋范围内" in guard
    assert 'visible_biz_types &= {"DORM_TRANSFER"}' in guard


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
    assert 'biz_type="BATCH_JOB"' in guard
    assert 'existed.status == "PENDING"' in guard
    assert "return operations.run_batch_job(resume_id, user)" in guard


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


def test_student_portal_has_real_material_upload_versions_and_notice_deep_link():
    api = _read("student-portal/src/services/affairsFourEndApi.js")
    page = _read("student-portal/src/views/affairs/MaterialSupplementView.vue")
    routes = _read("student-portal/src/router/index.js")
    hall = _read("student-portal/src/views/hall/ServiceHallView.vue")
    messages = _read("student-portal/src/views/messages/MessagesView.vue")

    assert "myMaterialRequirements" in api
    assert "uploadMaterialFile" in api
    assert "submitMaterialVersion" in api
    assert "version.versionNo" in page
    assert "历史版本不会被覆盖" in page
    assert "path: 'materials'" in routes
    assert "材料补交" in hall
    assert "materialRequirementId" in messages
    assert "/materials?requirementId=" in messages


def test_teacher_pc_has_material_queue_review_and_failed_only_batch_retry():
    api = _read("frontend/src/modules/studentAffairs/api/operations.api.js")
    page = _read("frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue")
    routes = _read("frontend/src/router/index.js")

    assert "createRequirement" in api
    assert "reviewRequirement" in api
    assert "createBatchJob" in api
    assert "retryFailed" in api
    assert "逐条校验权限、范围、状态和版本" in page
    assert "验收" in page and "退回" in page and "免交" in page
    assert "/admin/student-affairs/material-operations" in routes


def test_student_miniapp_has_authenticated_upload_versions_and_notice_focus():
    request = _read("miniapp/src/services/request.js")
    api = _read("miniapp/src/services/affairsContractApi.js")
    page = _read("miniapp/src/pages/student/affairs/index.vue")
    message = _read("miniapp/src/pages/common/message-detail/index.vue")

    assert "export function realUpload" in request
    assert "export function realDownload" in request
    assert "_refreshOnce()" in request
    assert "getMyMaterialRequirements" in api
    assert "uploadMaterialFile" in api
    assert "submitMaterialVersion" in api
    assert "item.version" in page
    assert "version.versionNo" in page
    assert "历史" in page or "版本记录" in page
    assert "materialRequirementId" in message
    assert "/pages/student/affairs/index?materialRequirementId=" in message


def test_teacher_miniapp_has_inline_review_safe_batch_and_todo_focus():
    api = _read("miniapp/src/services/affairsContractApi.js")
    page = _read("miniapp/src/pages/teacher/affairs/index.vue")

    assert "getMaterialRequirements" in api
    assert "reviewMaterialRequirement" in api
    assert "createMaterialReminderBatch" in api
    assert "retryMaterialBatchFailed" in api
    assert "MATERIAL_REVIEW" in page
    assert "逐条校验权限、范围、状态和版本" in page
    assert "验收" in page and "退回" in page and "免交" in page
    assert "重试失败项" in page
    # 复用已注册的学工首页，不为本轮新增 pages.json 路由，降低小程序页面清单变更风险。
    assert "pages/student/affairs/index" in _read("miniapp/src/pages.json")
    assert "pages/teacher/affairs/index" in _read("miniapp/src/pages.json")


def test_temporary_student_affairs_diagnostics_workflow_is_removed():
    assert not (ROOT / ".github/workflows/student-affairs-diagnostics.yml").exists()
