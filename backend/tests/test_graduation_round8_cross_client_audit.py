from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_opening_material_review_is_really_enabled():
    component = read("frontend/src/components/business/AppFileList.vue")
    proposal = read("frontend/src/modules/graduation/views/GraduationProposalReviewView.vue")
    teacher_pc = read("frontend/src/services/graduation.api.js")
    assert "supportsPreview" in component and "supportsDownload" in component
    assert ':supports-preview="true"' in proposal
    assert ':supports-download="true"' in proposal
    assert "getGraduationProposalDetail" in teacher_pc
    assert "downloadGraduationMaterial" in teacher_pc


def test_mobile_review_routes_are_batch_and_permission_guarded():
    teacher = read("backend/app/api/v1/mobile_graduation_teacher_context.py")
    router = read("backend/app/api/v1/route_registration.py")
    assert "require_mobile_graduation_request_permission" in router
    assert "expectedVersion" in teacher
    assert "batchId" in teacher


def test_student_material_detail_and_error_states_exist():
    portal = read("student-portal/src/components/graduation/GraduationMaterialsPanel.vue")
    mobile = read("miniapp/src/components/MobileGraduationMaterialsPanel.vue")
    assert "loadFinalDetail" in portal
    assert "loadFinalDetail" in mobile
    assert "retryLoad" in portal
    assert "retryLoad" in mobile
    assert "上传失败" in portal
    assert "上传失败" in mobile


def test_graduation_material_download_has_specialized_authorized_route():
    service = read("backend/app/modules/graduation/services/graduation_material_access_service.py")
    router = read("backend/app/modules/graduation/routers/graduation_material_sensitive_router.py")
    assert "authorize_graduation_material" in service
    assert "record_graduation_material_download" in service
    assert "/materials/{file_id}/download" in router
    assert "FileResponse" in router


def test_archive_export_is_real_xlsx_and_zip():
    service = read("backend/app/modules/graduation/services/graduation_archive_service.py")
    router = read("backend/app/modules/graduation/routers/graduation_archive.py")
    assert "Workbook" in service
    assert "zipfile.ZipFile" in service
    assert "StreamingResponse" in router
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in router
    assert "application/zip" in router


def test_batch_archive_has_hard_caps_and_failure_audit():
    service = read("backend/app/modules/graduation/services/graduation_archive_service.py")
    assert "MAX_BATCH_STUDENTS" in service
    assert "MAX_PACKAGE_BYTES" in service
    assert "BATCH_PACKAGE_FAILED" in service
    assert "BATCH_PACKAGE_SUCCEEDED" in service


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
    # 两套 API 均委托统一 upload_contract；清理逻辑只在权威合同执行一次，禁止复制回路由。
    assert "upload_contract" in files_a
    assert "upload_contract" in files_b
    assert "cleanup_stale_temporary_materials" in contract
    assert "abandonTemporaryGraduationMaterial" in portal
    assert "/mobile/graduation/materials/${fileId}/abandon" in janitor


def test_excellent_outcome_is_independent_multilevel_workflow():
    model = read("backend/app/models/graduation_extension.py")
    service = read("backend/app/modules/graduation/services/graduation_extension_service.py")
    ui = read("frontend/src/modules/graduation/views/GraduationExtensionAdminPanel.vue")
    student_pc = read("student-portal/src/components/graduation/GraduationExtensionPanel.vue")
    student_mobile = read("miniapp/src/components/MobileGraduationExtensionPanel.vue")
    assert "GraduationExcellentOutcome" in model
    assert "PENDING_MAJOR/PENDING_COLLEGE/PUBLISHED" in service
    assert 'grade.grade_level != "优秀"' in service
    assert "正式定稿" in service
    assert "major_review_excellent" in service
    assert "college_review_excellent" in service
    assert "成绩“优秀”只是候选条件" in ui
    assert "优秀成果认定" in student_pc
    assert "优秀成果认定" in student_mobile


def test_delayed_defense_reapply_and_regrouping_are_safe():
    model = read("backend/app/models/graduation_extension.py")
    service = read("backend/app/modules/graduation/services/graduation_extension_service.py")
    safety = read("backend/app/modules/graduation/services/graduation_extension_safety_service.py")
    school_router = read("backend/app/modules/graduation/routers/graduation_extension.py")
    assert "GraduationDelayedDefense" in model
    assert "PENDING_MENTOR/PENDING_COLLEGE/PENDING_SCHOOL/APPROVED" in service
    assert "reapply_delayed_defense" in service
    assert "regroup_delayed_defense" in service
    assert "with_for_update" in safety
    assert "PENDING_SCHOOL" in school_router
