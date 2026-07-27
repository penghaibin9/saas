"""教务分支不得覆盖 main 的岗位实习与毕设任务书小程序契约。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STUDENT_API = (ROOT / "miniapp/src/services/studentApi.js").read_text(encoding="utf-8")
COMPAT = (ROOT / "miniapp/src/services/internshipApiCompat.js").read_text(encoding="utf-8")


def test_main_internship_student_api_contracts_are_preserved():
    for method in (
        "getInternshipCompliance",
        "getInternshipConsentDetail",
        "viewInternshipConsent",
        "confirmInternshipConsent",
        "rejectInternshipConsent",
        "getInternshipSafetyCourseDetail",
        "startInternshipSafetyCourse",
        "submitInternshipSafetyCourse",
        "commitInternshipSafety",
    ):
        assert method in STUDENT_API


def test_optional_internship_module_does_not_break_old_branch_build():
    assert "import.meta.glob('./*.js')" in COMPAT
    assert "optionalServiceModules['./internshipApi.js']" in COMPAT
    assert "callOptionalInternship" in STUDENT_API
    assert "loadInternshipDashboard" in STUDENT_API
    assert "import * as internship from './internshipApi'" not in STUDENT_API


def test_graduation_taskbook_confirmation_carries_visible_version():
    assert "confirmGraduationTaskbook: (taskbookVersion)" in STUDENT_API
    assert "data: { taskbookVersion }" in STUDENT_API
    assert "confirmGraduationTaskbook: () => real.gdTaskbookConfirm()" not in STUDENT_API
