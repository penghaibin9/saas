import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _miniapp_routes() -> set[str]:
    """pages.json 的真实路由清单。

    S1 之后学生/教师页进了普通分包，pages.json 里只剩 subPackages[].root + pages[].path
    两段，整串 "pages/student/affairs/index" 不再以字面量出现。这里按 uni-app 的拼接规则
    还原完整路由，断言的仍然是"这条页面存在"，而不是"文件里有这个子串"。
    """
    import json
    data = json.loads(_read("miniapp/src/pages.json"))
    routes = {str(page["path"]) for page in data.get("pages") or []}
    for package in data.get("subPackages") or []:
        root = str(package.get("root") or "").strip("/")
        for page in package.get("pages") or []:
            routes.add(f"{root}/{str(page['path']).lstrip('/')}")
    return routes


def test_operations_python_sources_are_parseable():
    for relative in (
        "backend/app/models/affairs_operations.py",
        "backend/app/services/affairs_operations_service.py",
        "backend/app/services/affairs_operations_final_guard.py",
        "backend/app/modules/student_affairs/services/affairs_material_center_service.py",
        "backend/app/services/file_access_resolvers.py",
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
    legacy = _read("backend/app/services/affairs_operations_service.py")
    center = _read("backend/app/modules/student_affairs/services/affairs_material_center_service.py")
    guard = _read("backend/app/services/affairs_operations_final_guard.py")
    resolvers = _read("backend/app/services/file_access_resolvers.py")

    assert 'latest.status = "SUPERSEDED"' in legacy
    assert "version_no = int(latest.version_no if latest else 0) + 1" in legacy
    assert 'file.biz_type = "MATERIAL_REQUIREMENT"' in legacy
    assert 'file.visibility = "STUDENT_SELF"' in legacy
    assert "只能提交本人上传的文件" in legacy
    assert "FileAsset" in center and "FileVersion" in center and "FileBinding" in center
    assert "_require_file_ready(file_obj)" in center
    assert '@register_file_resolver("MATERIAL_REQUIREMENT")' in resolvers
    assert "center._has_biz_permission" in resolvers
    assert "center._require_student_scope" in resolvers
    assert "MATERIAL_REQUIREMENT 已由 resolver registry 授权" in guard
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


def test_router_mounts_authoritative_material_center_before_legacy_operations_api():
    router = _read("backend/app/api/v1/router.py")
    api = _read("backend/app/api/v1/affairs_operations_api.py")
    mount_block = router.split("for supplemental_router in (", 1)[1].split("):", 1)[0]

    assert mount_block.index("affairs_material_center_router") < mount_block.index("affairs_operations_router")
    assert "affairs_material_center_service as operations" in api
    assert "install_affairs_operations()" not in router
    assert "install_affairs_operations_final_guard()" not in router


def test_student_portal_has_real_material_upload_versions_and_notice_deep_link():
    """SP-M01 之后：补交材料的深链落点不再由 MessagesView.vue 本地拼接
    `/materials?requirementId=`，而是服务端 message_action_registry 的
    student.affairs.material 条目 + action_projection_service 透传原始
    actionParams（materialRequirementId），页面端同时兼容 requirementId 旧参数名。
    """
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
    assert "materialRequirementId" in page
    # 页面自己不再拼接这条深链——路由决策已经在服务端，页面只消费 query。
    assert "/materials?requirementId=" not in messages

    from app.services import message_action_registry as registry
    spec = registry.ACTION_REGISTRY["student.affairs.material"]
    assert spec["studentPc"] == "/materials"
    assert "materialRequirementId" in spec["requiredParams"]


def test_teacher_pc_has_material_queue_review_and_failed_only_batch_retry():
    api = _read("frontend/src/modules/studentAffairs/api/operations.api.js")
    page = _read("frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue")
    routes = _read("frontend/src/router/index.js")

    assert "createRequirement" in api
    assert "reviewRequirement" in api
    assert "createBatchJob" in api
    assert "retryFailed" in api
    assert "后端先按业务权限、班级/学院范围与强敏感逐生授权过滤" in page
    assert "row.allowedActions" in page and "row.version" in page
    assert "验收" in page and "退回" in page and "免交" in page
    assert "/admin/student-affairs/material-operations" in routes


def test_student_miniapp_has_authenticated_upload_versions_and_notice_focus():
    request = _read("miniapp/src/services/request.js")
    api = _read("miniapp/src/services/affairsContractApi.js")
    page = _read("miniapp/src/pages/student/affairs/index.vue")
    message = _read("miniapp/src/pages/common/message-detail/index.vue")

    assert "export function realUpload" in request
    assert "export function realDownload" in request
    assert "function _refreshOnce(expectedGeneration = currentSessionGeneration())" in request
    assert "_refreshOnce(requestSnapshot.generation)" in request
    assert "guardSessionPromise(" in request
    assert "captureSessionSnapshot(" in request
    assert "sessionChangedError()" in request
    assert "getMyMaterialRequirements" in api
    assert "uploadMaterialFile" in api
    assert "submitMaterialVersion" in api
    assert "item.version" in page
    assert "version.versionNo" in page
    assert "历史" in page or "版本记录" in page
    # V3 §4.2（深审 P0-02）：补交材料的对象聚焦不再靠消息详情页自己拼
    # "/pages/student/affairs/index?materialRequirementId="——那是客户端猜路由。
    # 现在由服务端 message_action_registry 下发已解析的 target，页面只执行它。
    # 聚焦能力因此改在真正生效的三处断言：注册表的落点与必需参数、focus 合同登记的
    # 参数名，以及业务页确实消费了这个参数。
    from app.services import message_action_registry as registry
    from app.services.mobile_focus_contract import FOCUS_READY_PAGES

    spec = registry.ACTION_REGISTRY["student.affairs.material"]
    assert spec["studentMini"] == "/pages/student/affairs/index"
    assert "materialRequirementId" in spec["requiredParams"]
    assert FOCUS_READY_PAGES["/pages/student/affairs/index"] == "materialRequirementId"
    assert "materialRequirementId" in page
    # 消息详情页只跑服务端 action，不得再出现本地拼接的补交材料路由。
    assert "/pages/student/affairs/index?materialRequirementId=" not in message
    assert "runAction(" in message


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
    routes = _miniapp_routes()
    assert "pages/student/affairs/index" in routes
    assert "pages/teacher/affairs/index" in routes


def test_temporary_student_affairs_diagnostics_workflow_is_removed():
    assert not (ROOT / ".github/workflows/student-affairs-diagnostics.yml").exists()
