"""毕业设计四端缺陷防回归静态门禁。

本文件不连接数据库，只锁定路由顺序、DTO、前端入口和状态机证据；
真实 MySQL、浏览器与微信开发者工具验收由定向工作流和人工 UAT 执行。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_new_python_files_are_syntax_valid():
    files = [
        "backend/app/api/v1/mobile_graduation_teacher_context.py",
        "backend/app/api/v1/mobile_graduation_extension_teacher.py",
        "backend/app/models/graduation_extension.py",
        "backend/app/modules/graduation/routers/graduation_extension.py",
        "backend/app/modules/graduation/services/graduation_extension_service.py",
        "backend/app/modules/graduation/services/graduation_extension_query_service.py",
        "backend/app/modules/graduation/services/graduation_extension_safety_service.py",
        "backend/app/modules/graduation/services/graduation_material_temp_service.py",
        "backend/app/modules/graduation/services/graduation_mobile_teacher_query_service.py",
        "backend/alembic/versions/0142_gd_excellent_delay_workflows.py",
    ]
    for filename in files:
        ast.parse(read(filename), filename=filename)


def test_alembic_has_one_linear_extension_head():
    migration = read("backend/alembic/versions/0142_gd_excellent_delay_workflows.py")
    assert 'revision = "0142_gd_excellent_delay"' in migration
    assert 'down_revision = "0141_merge_gd_intern_affairs_heads"' in migration
    assert "t_gd_excellent_outcome" in migration
    assert "t_gd_defense_delay" in migration


def test_dead_graduation_qualification_write_is_removed_from_ui():
    layout = read("frontend/src/modules/graduation/views/AdminGraduationLayout.vue")
    api = read("frontend/src/modules/graduation/api/graduation-student.api.js")
    backend_guard = read("backend/app/modules/graduation/routers/graduation_p0_guard.py")
    assert "panel === 'grad-qual'" in layout
    assert "setGradQual" not in api
    assert "毕业设计中心不再直接裁决最终毕业资格" in backend_guard


def test_shared_grade_view_remounts_by_route_identity():
    layout = read("frontend/src/modules/graduation/views/AdminGraduationLayout.vue")
    routes = read("frontend/src/modules/graduation/routes.js")
    assert "businessViewKey" in layout
    assert "this.$route.name" in layout
    assert "this.$route.meta?.defaultPanel" in layout
    for panel in ("plagiarism", "review", "defense", "grade"):
        assert f"defaultPanel: '{panel}'" in routes


def test_teacher_mobile_requires_batch_and_pages_lists():
    router = read("backend/app/api/v1/mobile_graduation_teacher_context.py")
    request = read("miniapp/src/services/request.js")
    picker = read("miniapp/src/components/MobileGraduationBatchContext.vue")
    assert "batchId: int = Query(..., ge=1)" in router
    assert "GraduationStudent.batch_id == int(batch_id)" in router
    assert "pageSize: int = Query(20, ge=1, le=100)" in router
    assert "GD_MAX_AUTO_PAGES" in request
    assert "collectTeacherGraduationPages" in request
    assert "请先选择毕业设计批次" in request
    assert "/mobile/teacher/graduation/batches" in picker


def test_teacher_delay_write_checks_current_batch():
    source = read("backend/app/api/v1/mobile_graduation_extension_teacher.py")
    assert "batchId: int = Query(..., ge=1)" in source
    assert "GraduationDefenseDelay.batch_id == int(batchId)" in source
    assert "该延期答辩申请不属于当前批次" in source


def test_taskbook_legacy_dto_is_not_silently_emptied():
    bridge = read("backend/app/modules/graduation/services/graduation_mobile_teacher_query_service.py")
    request = read("miniapp/src/services/request.js")
    registration = read("backend/app/api/v1/route_registration.py")
    assert "svc.list_taskbooks" in bridge
    assert "GD_TASKBOOK_PATH" in request
    assert "list: data.items" in request
    assert "install_mobile_taskbook_list_bridge()" not in registration
    assert "graduation_mobile_teacher_query_service import" in read(
        "backend/app/services/mobile_teacher_service.py"
    )


def test_student_partial_failures_are_visible_on_both_clients():
    portal_store = read("student-portal/src/stores/graduationHealth.js")
    portal_app = read("student-portal/src/App.vue")
    mini = read("miniapp/src/components/MobileGraduationSectionErrors.vue")
    assert "failGraduationSection" in portal_store
    assert "这不是“暂无业务”" in portal_app
    assert "processErrors" in mini
    assert "这不是“暂无业务”" in mini


def test_menu_route_and_action_permissions_are_aligned():
    workspaces = read("frontend/src/modules/graduation/config/graduationWorkspaces.js")
    routes = read("frontend/src/modules/graduation/routes.js")
    layout = read("frontend/src/modules/graduation/views/AdminGraduationLayout.vue")
    assert "/proposals?tab=PENDING_REVIEW" in workspaces
    assert "/finals?tab=PENDING_REVIEW" in workspaces
    assert "graduationDesign.topic.lib" in workspaces
    assert "graduationDesign.defense.view" in workspaces
    assert "graduationDesign.student.manage" in workspaces
    assert "graduationDesign.topic.lib" in routes
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
    portal = read("student-portal/src/services/request.js")
    janitor = read("miniapp/src/components/MobileGraduationTempFileJanitor.vue")
    assert "owner_user_id" in service and "_binding" in service
    assert "with_for_update=True" in service
    assert "附件已绑定开题或成果记录" in service
    assert "cleanup_stale_temporary_materials" in files_a
    assert "cleanup_stale_temporary_materials" in files_b
    assert "abandonTemporaryGraduationMaterial" in portal
    assert "/mobile/graduation/materials/${fileId}/abandon" in janitor


def test_excellent_outcome_is_independent_multilevel_workflow():
    model = read("backend/app/models/graduation_extension.py")
    service = read("backend/app/modules/graduation/services/graduation_extension_service.py")
    ui = read("frontend/src/modules/graduation/views/GraduationExtensionAdminPanel.vue")
    student_pc = read("student-portal/src/components/graduation/GraduationExtensionPanel.vue")
    student_mobile = read("miniapp/src/components/MobileGraduationExtensionPanel.vue")
    assert "GraduationExcellentOutcome" in model
    assert "PENDING_MAJOR/PENDING_COLLEGE/PUBLISHED" in model
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
    student_mobile_router = read("backend/app/api/v1/mobile_graduation_guard.py")
    student_portal_router = read("backend/app/api/v1/student_portal_graduation_guard.py")
    teacher_ui = read("miniapp/src/components/MobileGraduationDelayQueue.vue")
    assert "PENDING_ADVISOR/PENDING_MAJOR/PENDING_COLLEGE/APPROVED/SCHEDULED" in model
    assert "apply_delay" in service
    assert "advisor_review_delay" in service
    assert "major_review_delay" in service
    assert "college_review_delay" in service
    assert '"REJECTED"' in safety and '"CANCELLED"' in safety
    assert "not has_active_delay" in safety
    assert "MAX_DEFENSE_STUDENTS" in safety
    assert "old_group.published = False" in safety
    assert "_recompute_defense(db, old_group)" in safety
    assert "_recompute_defense(db, group)" in safety
    assert "safety_svc.schedule_delay" in school_router
    assert "extension_safety_svc.my_extensions" in student_mobile_router
    assert "extension_safety_svc.my_extensions" in student_portal_router
    assert "仅显示当前批次、本人指导学生" in teacher_ui


def test_second_defense_and_judge_conflict_are_real_state_machines():
    defense = read("backend/app/modules/graduation/services/graduation_defense_score_service.py")
    group = read("backend/app/modules/graduation/services/graduation_service.py")
    pc = read("frontend/src/modules/graduation/views/GraduationDefenseGradeView.vue")
    assert "round_no" in defense
    assert "def create_second_defense" in defense
    assert "本轮评分尚未全部确认，暂不能创建二次答辩" in defense
    assert "judge_identity" in defense
    assert "评委与指导教师冲突" in group
    assert "存在评委与导师冲突" in group
    assert "发起二次答辩" in pc


def test_total_grade_and_archive_remain_separate_final_steps():
    grade = read("backend/app/modules/graduation/services/graduation_grade_service.py")
    archive = read("backend/app/modules/graduation/services/graduation_archive_service.py")
    assert "advisor_score" in grade and "reviewer_score" in grade and "defense_score" in grade
    assert "PUBLISHED" in grade and "WITHDRAWN" in grade
    assert "checklist" in archive or "FILED" in archive
    assert "GraduationAuditTrail" in archive


def test_requested_workflow_nodes_have_real_source_anchors():
    anchors = {
        "batch": "backend/app/modules/graduation/routers/graduation_batch.py",
        "topic": "backend/app/modules/graduation/routers/graduation_topic.py",
        "dual_selection": "backend/app/modules/graduation/services/graduation_topic_round_service.py",
        "mentor": "backend/app/modules/graduation/routers/graduation_mentor.py",
        "taskbook": "backend/app/modules/graduation/routers/graduation_taskbook.py",
        "proposal": "backend/app/modules/graduation/services/graduation_service.py",
        "midterm": "backend/app/modules/graduation/routers/graduation_midterm.py",
        "guidance": "backend/app/modules/graduation/routers/graduation_guidance.py",
        "final": "backend/app/modules/graduation/services/graduation_service.py",
        "plagiarism": "backend/app/modules/graduation/routers/graduation_defense_score.py",
        "review": "backend/app/modules/graduation/routers/graduation_review.py",
        "defense": "backend/app/modules/graduation/services/graduation_service.py",
        "grade": "backend/app/modules/graduation/routers/graduation_grade.py",
        "excellent_delay": "backend/app/modules/graduation/routers/graduation_extension.py",
        "archive": "backend/app/modules/graduation/routers/graduation_archive.py",
    }
    for name, path in anchors.items():
        assert read(path).strip(), f"missing workflow source: {name} -> {path}"
