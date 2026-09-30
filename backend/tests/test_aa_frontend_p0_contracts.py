"""P0-01～P0-04前端可信边界静态合同。运行时点击验收留到最终验证。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_student_schedule_uses_seven_days_backend_slots_and_time_bands():
    source = _read("student-portal/src/views/academic/StudentScheduleView.vue")

    for day in ("周一", "周二", "周三", "周四", "周五", "周六", "周日"):
        assert day in source
    assert "timeBands" in source
    assert "slotLabel(item)" in source
    assert "按校区作息" in source
    assert 'v-for="item in cellItems(day.value, slot)"' in source
    assert 'return dayItems(day).filter' in source
    assert "item.weekParity === 'ODD'" in source
    assert "item.weekParity === 'EVEN'" in source


def test_student_grade_query_copy_never_uses_inner_html_or_official_wording():
    grades = _read("student-portal/src/views/academic/StudentGradesView.vue")
    legacy = _read("student-portal/src/views/academic/AcademicLegacySafeView.vue")

    assert "个人成绩查询件" in grades
    assert "不等同于学校盖章的正式证明" in grades
    assert "textContent" in grades
    assert "innerHTML" not in grades
    assert "Official Academic Transcript" not in grades
    assert 'RouterLink v-for="item in visibleItems"' in legacy
    assert ':to="item.to"' in legacy
    assert 'AcademicView' not in legacy
    assert 'innerHTML' not in legacy


def test_student_section_route_fails_closed_and_hides_legacy_entry():
    source = _read("student-portal/src/views/academic/AcademicSectionRouteView.vue")

    assert "activationError" in source
    assert "未找到“${target}”业务面板" in source
    assert "未找到“${subTarget}”子工作区" in source
    assert "标题是A、内容是B" in source
    assert "academicSubTab" in source
    assert "button.sp-tab" in source
    assert "兼容综合页" not in source
    assert "router.push('/academic/all')" not in source


def test_makeup_route_uses_dedicated_server_authoritative_workspace():
    router = _read("student-portal/src/router/academicRoutes.js")
    view = _read("student-portal/src/views/academic/StudentMakeupView.vue")

    assert "path: 'makeup'" in router
    assert "StudentMakeupView.vue" in router
    assert "academicSection('makeup'" not in router
    assert "portalApi.academicMakeup()" in view
    assert "portalApi.academicMakeupOptions()" in view
    assert "portalApi.academicRetakeApply" in view
    assert "portalApi.academicExemptionApply" in view
    assert "是否受理以学校规则为准" in view
    assert "提交后由学校按各自规则审核，不直接生成正式成绩" in view
    assert "window.prompt" not in view


def test_student_registration_uses_dedicated_actionable_workspace():
    router = _read("student-portal/src/router/academicRoutes.js")
    view = _read("student-portal/src/views/academic/StudentRegistrationView.vue")

    assert "StudentRegistrationView.vue" in router
    assert "academicSection('registration'" not in router
    assert "portalApi.academicRegistration()" in view
    assert "portalApi.academicRegistrationRegister" in view
    assert "portalApi.academicRegistrationDefer" in view
    assert "batch.blockReason" in view
    assert "batch.canRegister" in view
    assert "batch.canDefer" in view
    assert "暂时无法完成注册的原因（至少 2 字）" in view
    assert "window.prompt" not in view


def test_student_selection_uses_dedicated_server_authoritative_workspace():
    router = _read("student-portal/src/router/academicRoutes.js")
    view = _read("student-portal/src/views/academic/StudentSelectionView.vue")

    assert "StudentSelectionView.vue" in router
    assert "academicSection('selection'" not in router
    assert "portalApi.academicCourseSelection(batchId || undefined)" in view
    assert "portalApi.academicSelectionRecords(batchId || undefined)" in view
    assert "portalApi.academicSelectionPreflight" in view
    assert "portalApi.academicEnroll" in view
    assert "portalApi.academicDrop" in view
    assert "allowedActions" in view
    assert "portalApi.academicSelectionRecords(context.batchId || undefined)" in view
    assert "提交时服务器重新检查容量、时间和学籍资格" in view
    for boundary in ("时间", "容量", "办理窗口"):
        assert boundary in view
    assert "window.prompt" not in view


def test_student_recheck_uses_dedicated_published_grade_workspace():
    router = _read("student-portal/src/router/academicRoutes.js")
    view = _read("student-portal/src/views/academic/StudentRecheckView.vue")

    assert "StudentRecheckView.vue" in router
    assert "academicSection('recheck'" not in router
    assert "portalApi.academicGradeRecheck()" in view
    assert "portalApi.academicTranscript()" in view
    assert "portalApi.academicGradeRecheckSubmit" in view
    assert "exactPositiveDecimalId(grade.gradeId)" in view
    assert "!inFlightGradeIds.value.has(exactPositiveDecimalId(grade.gradeId))" in view
    assert "RETURNED" not in view


def test_student_evaluation_uses_dedicated_secure_workspace():
    router = _read("student-portal/src/router/academicRoutes.js")
    view = _read("student-portal/src/views/academic/StudentEvaluationView.vue")

    assert "path: 'evaluation'" in router
    assert "StudentEvaluationView.vue" in router
    assert "academicSection('evaluation'" not in router
    assert "task.canSubmit === true" in view
    assert "task.submitted === true" in view
    assert "task.canSubmit !== true || task.submitted === true" in view
    assert "submittedCount" not in view
    assert "portalApi.academicEvaluationSubmit" in view


def test_student_home_counts_only_real_actionable_states():
    source = _read("student-portal/src/views/academic/StudentAcademicHomeView.vue")

    assert "function actionableEvaluationRows(data)" in source
    assert "row.canSubmit === true && row.submitted !== true" in source
    assert "const evaluation = actionableEvaluationRows(val(1))" in source
    assert "route: withQuery('/academic/makeup', { tab: 'retake', optionId })" in source
    assert "portalApi.academicGradeRecheck()" not in source
    assert "修改成绩复查申请" not in source


def test_admin_menu_is_fail_closed_and_cache_signature_is_identity_complete():
    source = _read("frontend/src/config/adminMenu.js")

    assert "if (import.meta.env && import.meta.env.PROD) return workbenchOnly(leaf)" in source
    assert "__missing_permissions__" in source
    for field in (
        "tenantId", "userId", "activeContextId", "permissionVersion", "ctxKey", "patterns",
    ):
        assert field in source
    assert "[...ctx.permissionPatterns].sort().join(',')" in source
    assert "clearVisibleAdminMenuCache" in source


def test_academic_layout_has_error_retry_and_back_instead_of_endless_loading():
    source = _read("frontend/src/modules/academicAffairs/views/AdminAcademicAffairsLayout.vue")

    assert '<router-view v-if="ctx"' in source
    assert 'v-else-if="error"' in source
    assert '@retry="loadContext"' in source
    assert '@back="goWorkbench"' in source
    assert "this.ctx = null" in source
    assert "this.error = (err && err.message)" in source
    assert "权限上下文读取失败" in source


def test_teacher_pc_admin_grade_supplement_uses_identity_endpoint_and_required_class():
    api_source = _read("frontend/src/modules/academicAffairs/api/grade-identity.api.js")
    view_source = _read("frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue")

    assert "/academic-affairs/grade-tasks/identity" in api_source
    assert "gradeIdentityApi.createGradeTask(payload)" in view_source
    assert "请选择明确行政班" in view_source
    assert "特殊补录必选" in view_source
