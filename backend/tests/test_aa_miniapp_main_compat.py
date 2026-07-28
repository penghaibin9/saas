"""教务分支不得覆盖 main 的岗位实习、毕业设计与共享小程序契约。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STUDENT_API = (ROOT / "miniapp/src/services/studentApi.js").read_text(encoding="utf-8")
COMPAT = (ROOT / "miniapp/src/services/internshipApiCompat.js").read_text(encoding="utf-8")


def test_main_internship_student_api_contracts_are_preserved():
    for method in (
        "getInternship",
        "getInternshipCompliance",
        "getInternshipConsents",
        "getInternshipConsentDetail",
        "viewInternshipConsent",
        "confirmInternshipConsent",
        "rejectInternshipConsent",
        "getInternshipSafetyCourses",
        "getInternshipSafetyCompletions",
        "getInternshipSafetyCourseDetail",
        "startInternshipSafetyCourse",
        "submitInternshipSafetyCourse",
        "commitInternshipSafety",
        "getInternshipAgreements",
        "getInternshipAgreementDetail",
        "confirmInternshipAgreement",
        "getInternshipLeaves",
        "applyInternshipLeave",
        "withdrawInternshipLeave",
        "returnInternshipLeave",
        "reportInternshipHelp",
        "getInternshipMakeups",
        "applyInternshipMakeup",
        "withdrawInternshipMakeup",
        "getInternshipSelfEval",
        "submitInternshipSelfEval",
        "getInternshipIntention",
        "saveInternshipIntention",
        "submitInternshipIntention",
        "withdrawInternshipIntention",
        "getInternshipChangeRequests",
        "applyInternshipChange",
        "getInternshipApplications",
        "saveInternshipApplication",
        "submitInternshipApplication",
        "withdrawInternshipApplication",
        "getInternshipInsurance",
        "submitInternshipInsurance",
        "getInternshipPlan",
        "getInternshipPlanTasks",
        "ackInternshipPlan",
        "submitInternshipPlanTask",
        "submitProcessReport",
    ):
        assert f"{method}:" in STUDENT_API


def test_main_graduation_student_api_contracts_are_preserved():
    for method in (
        "getGraduation",
        "getGraduationActiveRound",
        "getGraduationTopics",
        "getMyGraduationChangeRequests",
        "submitGraduationChoices",
        "withdrawGraduationChoices",
        "requestGraduationTopicChange",
        "getGraduationProposal",
        "submitGraduationProposal",
        "getGraduationFinal",
        "submitGraduationFinal",
        "getGraduationTaskbook",
        "confirmGraduationTaskbook",
        "getGraduationMidterm",
        "submitGraduationMidtermRectify",
        "getGraduationDefense",
        "getGraduationGrade",
        "appealGraduationGrade",
        "getGraduationPeerTasks",
        "submitGraduationPeer",
        "rectifyGraduationPeer",
        "getGraduationArchive",
    ):
        assert f"{method}:" in STUDENT_API


def test_optional_internship_module_does_not_break_old_branch_build():
    assert "import.meta.glob('./*.js')" in COMPAT
    assert "optionalServiceModules['./internshipApi.js']" in COMPAT
    assert "callOptionalInternship" in STUDENT_API
    assert "loadInternshipDashboard" in STUDENT_API
    assert "import * as internship from './internshipApi'" not in STUDENT_API
    assert "INTERNSHIP_API_NOT_AVAILABLE" in COMPAT


def test_graduation_taskbook_confirmation_carries_visible_version():
    assert "confirmGraduationTaskbook: (taskbookVersion)" in STUDENT_API
    assert "data: { taskbookVersion }" in STUDENT_API
    assert "confirmGraduationTaskbook: () => real.gdTaskbookConfirm()" not in STUDENT_API


def test_academic_exam_pages_use_identity_safe_v2_endpoints():
    assert "'/mobile/academic/exam-v2/my'" in STUDENT_API
    assert "'/mobile/academic/exam-v2/defer-options'" in STUDENT_API
    assert "'/mobile/academic/exam-v2/defer/apply'" in STUDENT_API
    assert "data: { examCourseId, reasonType, reason }" in STUDENT_API


def test_student_evaluation_contract_remains_available_to_current_pages():
    assert "getMyEvaluationTasks: () => real.acadEvaluationTasks()" in STUDENT_API
    assert "submitEvaluation: (body) => real.acadEvaluationSubmit(body)" in STUDENT_API
