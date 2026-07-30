from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_secure_file_actions_are_visible_across_three_clients():
    teacher_pc = read("frontend/src/components/file/SecureFileList.vue")
    student_pc = read("student-portal/src/components/file/SecureFileList.vue")
    miniapp = read("miniapp/src/components/file/SecureFileList.vue")
    for source in (teacher_pc, student_pc, miniapp):
        assert "statusText" in source
        assert "canPreview" in source
        assert "canDownload" in source
        assert "暂不可使用" in source


def test_three_client_sdks_share_security_status_and_server_actions():
    teacher_pc = read("frontend/src/services/file/fileSdk.js")
    student_pc = read("student-portal/src/services/fileSdk.js")
    miniapp = read("miniapp/src/services/fileSdk.js")
    for source in (teacher_pc, student_pc, miniapp):
        assert "FILE_STATUS_TEXT" in source
        assert "等待安全扫描" in source
        assert "安全可用" in source
        assert "allowedActions.includes('preview')" in source
        assert "allowedActions.includes('download')" in source


def test_mobile_review_routes_are_batch_and_permission_guarded():
    teacher = read("backend/app/api/v1/mobile_graduation_teacher_context.py")
    router = read("backend/app/api/v1/route_registration.py")
    assert "require_mobile_graduation_request_permission" in router
    assert "batchId: int = Query(..., ge=1)" in teacher
    assert "_material_student(GraduationProposal" in teacher
    assert "_material_student(GraduationFinal" in teacher
    assert "真正写入仍复用 mobile_teacher_service" in teacher


def test_generic_file_routes_cannot_bypass_graduation_audit_boundary():
    contract = read("backend/app/api/v1/file_contract.py")
    files_a = read("backend/app/api/v1/files.py")
    files_b = read("backend/app/api/v1/file.py")
    assert "_requires_audited_business_download" in contract
    assert '== "GRADUATION_MATERIAL"' in contract
    assert "raise not_found(\"文件不存在\")" in contract
    assert "download_contract" in files_a
    assert "download_contract" in files_b


def test_graduation_batch_safe_routers_precede_legacy_routes():
    router = read("backend/app/api/v1/route_registration.py")
    material = read("backend/app/modules/graduation/routers/graduation_material_sensitive_router.py")
    sensitive = read("backend/app/modules/graduation/routers/graduation_sensitive_router.py")
    assert "graduation_material_sensitive_router" in router
    assert "graduation_sensitive_router" in router
    assert "assert_student_batch" in material
    assert "require_batch_id" in material
    assert "load_student_in_batch" in sensitive
    assert "accessible_student_ids" in sensitive


def test_student_readonly_scope_is_visible_in_pc_layout():
    layout = read("frontend/src/modules/graduation/views/AdminGraduationLayout.vue")
    assert "gd-student-readonly" in layout


def test_reminder_copy_matches_real_message_delivery():
    toast = read("frontend/src/utils/toast.js")
    layout = read("frontend/src/modules/graduation/views/AdminGraduationLayout.vue")
    backend = read("backend/app/modules/graduation/services/graduation_service.py")
    assert "发送开题站内催办并写入留痕" in toast
    assert "催交会发送真实站内消息" in layout
    assert "def _deliver_student_reminder" in backend
    assert "UnifiedMessage(" in backend
    assert "学生未绑定有效登录账号，提醒未发送" in backend


def test_temporary_file_cleanup_is_owner_scoped_and_binding_safe():
    service = read("backend/app/modules/graduation/services/graduation_material_temp_service.py")
    files_a = read("backend/app/api/v1/files.py")
    files_b = read("backend/app/api/v1/file.py")
    contract = read("backend/app/api/v1/file_contract.py")
    portal = read("student-portal/src/services/request.js")
    janitor = read("miniapp/src/components/MobileGraduationTempFileJanitor.vue")
    assert "owner_user_id" in service and "_binding" in service
    assert "with_for_update=True" in service
    assert "附件已绑定开题或成果记录" in service
    # 两套 API 委托统一 upload_contract；清理逻辑只在权威合同执行一次，禁止复制回路由。
    assert "upload_contract" in files_a
    assert "upload_contract" in files_b
    assert "cleanup_stale_temporary_materials" in contract
    assert "abandonTemporaryGraduationMaterial" in portal
    assert "/mobile/graduation/materials/${fileId}/abandon" in janitor


def test_phase3_receipts_do_not_impersonate_graduation_materials():
    jobs = read("backend/app/services/data_exchange_job_service.py")
    contract = read("backend/app/api/v1/file_contract.py")
    assert 'biz_type="DATA_EXCHANGE_RECEIPT"' in jobs
    assert 'security_level="HIGHLY_SENSITIVE"' in jobs
    assert 'normalized == "GRADUATION_MATERIAL"' in contract
    assert "temporary" in contract
