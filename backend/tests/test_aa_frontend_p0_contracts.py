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
    assert "v-for=\"item in dayItems(day.value)\"" in source
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
    assert "旧课表算法和客户端“官方成绩单”入口已停用" in legacy
    assert ".sp-tab:nth-child(5)" in legacy


def test_student_section_route_fails_closed_and_hides_legacy_entry():
    source = _read("student-portal/src/views/academic/AcademicSectionRouteView.vue")

    assert "activationError" in source
    assert "未找到“${target}”业务面板" in source
    assert "标题是A、内容是B" in source
    assert "兼容综合页" not in source
    assert "router.push('/academic/all')" not in source


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
