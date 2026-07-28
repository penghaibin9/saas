"""教务独立路由不得覆盖当前 main 已存在的学生门户路由与接口。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "student-portal/src/router/index.js").read_text(encoding="utf-8")
ACADEMIC_ROUTES = (ROOT / "student-portal/src/router/academicRoutes.js").read_text(encoding="utf-8")
MAIN_ENTRY = (ROOT / "student-portal/src/main.js").read_text(encoding="utf-8")
PORTAL_API = (ROOT / "student-portal/src/services/portalApi.js").read_text(encoding="utf-8")
COMPLIANCE_API = (ROOT / "student-portal/src/services/internshipComplianceApi.js").read_text(encoding="utf-8")
CORE_API = (ROOT / "student-portal/src/services/internshipCoreApi.js").read_text(encoding="utf-8")
GRADUATION_EXTENSION_API = (
    ROOT / "student-portal/src/services/graduationExtensionApi.js"
).read_text(encoding="utf-8")


def test_academic_routes_are_installed_from_an_independent_module():
    assert "installAcademicRoutes(router)" in MAIN_ENTRY
    assert "router.removeRoute('academic')" in ACADEMIC_ROUTES
    assert "router.addRoute(academicRoute)" in ACADEMIC_ROUTES
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
        assert token in ACADEMIC_ROUTES


def test_current_main_portal_router_is_preserved_without_academic_rewrite():
    assert "academic-home" not in SOURCE
    assert "optionalView" not in SOURCE
    for path in (
        "profile",
        "academic",
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
        "academic",
        "internship-compliance",
        "graduation-workbench",
    ):
        assert f"name: '{name}'" in SOURCE


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
