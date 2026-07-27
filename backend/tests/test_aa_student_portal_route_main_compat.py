"""教务独立路由不得覆盖当前 main 已存在的学生门户路由与接口。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "student-portal/src/router/index.js").read_text(encoding="utf-8")
PORTAL_API = (ROOT / "student-portal/src/services/portalApi.js").read_text(encoding="utf-8")
COMPLIANCE_API = (ROOT / "student-portal/src/services/internshipComplianceApi.js").read_text(encoding="utf-8")
CORE_API = (ROOT / "student-portal/src/services/internshipCoreApi.js").read_text(encoding="utf-8")
GRADUATION_EXTENSION_API = (
    ROOT / "student-portal/src/services/graduationExtensionApi.js"
).read_text(encoding="utf-8")


def test_academic_routes_remain_independent_and_legacy_safe():
    for token in (
        "academic-home",
        "academic-schedule",
        "academic-grades",
        "academic-registration",
        "academic-selection",
        "academic-evaluation",
        "academic-recheck",
        "academic-status",
        "academic-exam",
        "academic-graduation",
        "AcademicLegacySafeView.vue",
    ):
        assert token in SOURCE


def test_current_main_portal_routes_are_preserved():
    for path in (
        "profile",
        "campus-service",
        "internship",
        "internship/compliance",
        "employment",
        "orientation",
        "messages",
        "service-hall",
        "graduation",
    ):
        assert f"path: '{path}'" in SOURCE

    for name in (
        "internship-compliance",
        "graduation-workbench",
    ):
        assert f"name: '{name}'" in SOURCE


def test_main_optional_view_is_build_safe_on_long_lived_branch():
    assert "import.meta.glob('../views/**/*.vue')" in SOURCE
    assert "const optionalView =" in SOURCE
    assert "optionalViews[`../views/${relativePath}.vue`] || fallback" in SOURCE
    assert "optionalView(" in SOURCE
    # 主线新增页面在当前分支尚不存在时，不得用静态 import 使 Vite 直接构建失败。
    assert "() => import('../views/internship/InternshipComplianceView.vue')" not in SOURCE


def test_main_internship_compliance_contract_is_preserved():
    for token in (
        "internshipCompliance",
        "internshipConsents",
        "internshipConsentDetail",
        "internshipConsentView",
        "internshipConsentConfirm",
        "internshipConsentReject",
        "internshipSafetyCourses",
        "internshipSafetyCompletions",
        "internshipSafetyDetail",
        "internshipSafetyStart",
        "internshipSafetySubmit",
        "internshipSafetyCommit",
    ):
        assert token in PORTAL_API
    assert "/portal/internship/compliance" in COMPLIANCE_API
    assert "/portal/internship/consents" in COMPLIANCE_API
    assert "/portal/internship/safety/courses" in COMPLIANCE_API


def test_main_internship_and_graduation_support_facades_exist():
    for token in (
        "/portal/internship/context/applications",
        "expectedVersion",
        "INTERNSHIP_APPLICATION_EVIDENCE",
        "INTERNSHIP_INSURANCE_POLICY",
    ):
        assert token in CORE_API
    assert "/portal/graduation/extensions/my" in GRADUATION_EXTENSION_API
    assert "/portal/graduation/defense-delay/apply" in GRADUATION_EXTENSION_API
