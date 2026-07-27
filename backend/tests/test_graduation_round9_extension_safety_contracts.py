"""毕业设计优秀成果/延期答辩安全与四端 UI 静态合同。

不连接数据库；真实 MySQL、构建、浏览器和微信开发者工具结果必须单独记录。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_extension_python_sources_parse():
    for path in (
        "backend/app/modules/graduation/services/graduation_extension_action_service.py",
        "backend/app/modules/graduation/services/graduation_extension_safety_service.py",
        "backend/app/modules/graduation/services/graduation_extension_query_service.py",
        "backend/app/modules/graduation/routers/graduation_extension.py",
        "backend/app/api/v1/mobile_graduation_extension_teacher.py",
        "backend/app/api/v1/mobile_graduation_guard.py",
        "backend/app/api/v1/student_portal_graduation_guard.py",
    ):
        ast.parse(read(path), filename=path)


def test_advisor_nodes_use_stable_binding_and_no_admin_substitution():
    safety = read("backend/app/modules/graduation/services/graduation_extension_safety_service.py")
    action = read("backend/app/modules/graduation/services/graduation_extension_action_service.py")
    router = read("backend/app/modules/graduation/routers/graduation_extension.py")
    teacher = read("backend/app/api/v1/mobile_graduation_extension_teacher.py")
    assert "def _assert_bound_advisor" in safety
    assert "current_user_mentor" in safety
    assert "student.mentor_id" in safety
    assert "任何管理员身份都不能代替" in safety
    assert "safety.nominate_excellent" in action
    assert "safety.advisor_review_delay" in action
    assert "action_svc.nominate_excellent" in router
    assert "action_svc.advisor_review_delay" in router
    assert "action_svc.advisor_review_delay" in teacher


def test_duplicate_submissions_are_business_conflicts():
    safety = read("backend/app/modules/graduation/services/graduation_extension_safety_service.py")
    action = read("backend/app/modules/graduation/services/graduation_extension_action_service.py")
    student_mobile = read("backend/app/api/v1/mobile_graduation_guard.py")
    student_portal = read("backend/app/api/v1/student_portal_graduation_guard.py")
    assert "IntegrityError" in safety
    assert "优秀成果提名已被其他请求提交" in safety
    assert "延期答辩申请已被其他请求提交" in safety
    assert "safety.apply_delay" in action
    assert "extension_action_svc.apply_delay" in student_mobile
    assert "extension_action_svc.apply_delay" in student_portal


def test_write_payloads_are_bounded_and_auditable():
    action = read("backend/app/modules/graduation/services/graduation_extension_action_service.py")
    router = read("backend/app/modules/graduation/routers/graduation_extension.py")
    assert "maximum: int = 1000" in action
    assert "附件证据最多 20 项" in action
    assert "date.fromisoformat" in action
    assert "延期答辩日期必须为 YYYY-MM-DD" in action
    assert "graduation_extension_action_service as action_svc" in router
    for fn in (
        "nominate_excellent", "major_review_excellent", "college_review_excellent",
        "advisor_review_delay", "major_review_delay", "college_review_delay", "schedule_delay",
    ):
        assert f"action_svc.{fn}" in router


def test_delay_reapply_uses_real_active_key_not_latest_history_only():
    safety = read("backend/app/modules/graduation/services/graduation_extension_safety_service.py")
    portal_ui = read("student-portal/src/components/graduation/GraduationExtensionPanel.vue")
    mini_ui = read("miniapp/src/components/MobileGraduationExtensionPanel.vue")
    assert 'active_key == f"active:{student.id}"' in safety
    assert "and not active_delay_id" in safety
    assert "重新申请延期答辩" in portal_ui
    assert "重新申请延期答辩" in mini_ui
    assert "data.canApplyDelay" in portal_ui
    assert "data.canApplyDelay" in mini_ui


def test_teacher_queue_is_database_paginated_by_stable_mentor():
    safety = read("backend/app/modules/graduation/services/graduation_extension_safety_service.py")
    route = read("backend/app/api/v1/mobile_graduation_extension_teacher.py")
    ui = read("miniapp/src/components/MobileGraduationDelayQueue.vue")
    assert "def list_advisor_delays" in safety
    assert "GraduationStudent.mentor_id == int(mentor.id)" in safety
    assert 'GraduationDefenseDelay.status == "PENDING_ADVISOR"' in safety
    assert "offset((max(1, page) - 1) * page_size).limit(page_size)" in safety
    assert "safety_svc.list_advisor_delays" in route
    assert "row.allowedActions && row.allowedActions.advisorReview" in ui
    assert "这不是“暂无待办”" in ui


def test_regrouping_locks_capacity_and_republishes_both_groups():
    safety = read("backend/app/modules/graduation/services/graduation_extension_safety_service.py")
    assert "with_for_update=True" in safety
    assert "MAX_DEFENSE_STUDENTS" in safety
    assert "old_group.published = False" in safety
    assert "group.published = False" in safety
    assert "_recompute_defense(db, old_group)" in safety
    assert "_recompute_defense(db, group)" in safety


def test_school_ui_uses_row_actions_and_surfaces_partial_failures():
    ui = read("frontend/src/modules/graduation/views/GraduationExtensionAdminPanel.vue")
    query = read("backend/app/modules/graduation/services/graduation_extension_query_service.py")
    safety = read("backend/app/modules/graduation/services/graduation_extension_safety_service.py")
    assert '"canNominate"' in query
    assert '"allowedActions"' in safety
    assert "row.canNominate" in ui
    assert "can(row, 'majorReview')" in ui
    assert "can(row, 'collegeReview')" in ui
    assert "can(row, 'advisorReview')" in ui
    assert "can(row, 'schedule')" in ui
    assert "supportError" in ui
    assert "候选加载失败" in ui
    assert "答辩组加载失败" in ui
    assert "当前页待处理" in ui
    assert "下一步" in ui


def test_defense_group_picker_is_batch_bound_and_accepts_canonical_date_dto():
    api = read("frontend/src/modules/graduation/api/graduation-student.api.js")
    more_api = read("frontend/src/modules/graduation/api/graduation-more.api.js")
    assert "params: withBatch({ page: 1, pageSize: 200, ...params })" in api
    assert "defenseDate: g.date || g.defenseDate" in api
    assert "withBatch({ page: 1, pageSize: 200, ...params })" in more_api


def test_main_workflow_precedes_low_frequency_extensions():
    portal_app = read("student-portal/src/App.vue")
    mobile_shell = read("miniapp/src/components/MobileGlobalState.vue")
    assert portal_app.index("<router-view />") < portal_app.index("<GraduationExtensionPanel")
    assert mobile_shell.index('<slot v-if="state === \'ready\'"') < mobile_shell.index("<MobileGraduationExtensionPanel")
    assert "route.name === 'graduation-workbench'" in portal_app


def test_student_panels_have_first_screen_state_and_mobile_overflow_guards():
    portal = read("student-portal/src/components/graduation/GraduationExtensionPanel.vue")
    mini = read("miniapp/src/components/MobileGraduationExtensionPanel.vue")
    teacher = read("miniapp/src/components/MobileGraduationDelayQueue.vue")
    for source in (portal, mini):
        assert "下一步" in source
        assert "加载失败" in source or "这不是“暂无业务”" in source
    assert "overflow:hidden" in mini
    assert "word-break:break-word" in mini
    assert "overflow:hidden" in teacher
    assert "word-break:break-word" in teacher
