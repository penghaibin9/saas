"""教务分支不得覆盖 main 的岗位实习、毕业设计与共享小程序契约。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STUDENT_API = (ROOT / "miniapp/src/services/studentApi.js").read_text(encoding="utf-8")
INTERNSHIP_API = (ROOT / "miniapp/src/services/internshipApi.js").read_text(encoding="utf-8")
ACADEMIC_API = (ROOT / "miniapp/src/services/academicStudentApi.js").read_text(encoding="utf-8")
SESSION_STORE = (ROOT / "miniapp/src/stores/session.js").read_text(encoding="utf-8")
SESSION_PLUGIN = (ROOT / "miniapp/src/stores/sessionAcademicPlugin.js").read_text(encoding="utf-8")
MINIAPP_MAIN = (ROOT / "miniapp/src/main.js").read_text(encoding="utf-8")
EXAM_PAGE = (
    ROOT / "miniapp/src/pages/student/academic-affairs/exam.vue"
).read_text(encoding="utf-8")


def test_main_internship_student_api_contracts_are_preserved():
    assert "import * as internship from './internshipApi'" in STUDENT_API
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

    for token in (
        "teacherInternshipContext",
        "studentInternshipDashboard",
        "studentInternshipCompliance",
        "studentInternshipConsentConfirm",
        "studentInternshipSafetyCommit",
        "studentInternshipApplicationSubmit",
        "studentInternshipLeaveReturn",
        "studentInternshipMakeupWithdraw",
        "studentInternshipPlanTaskSubmit",
    ):
        assert token in INTERNSHIP_API
    assert "data: body || {}" in INTERNSHIP_API


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


def test_graduation_taskbook_confirmation_carries_visible_version():
    assert "confirmGraduationTaskbook: (taskbookVersion)" in STUDENT_API
    assert "data: { taskbookVersion }" in STUDENT_API
    assert "confirmGraduationTaskbook: () => real.gdTaskbookConfirm()" not in STUDENT_API


def test_academic_exam_v2_is_isolated_from_shared_student_api():
    assert "'/mobile/academic/exam-v2/my'" not in STUDENT_API
    assert "'/mobile/academic/exam-v2/defer-options'" not in STUDENT_API
    assert "'/mobile/academic/exam-v2/defer/apply'" not in STUDENT_API
    assert "...baseStudentApi" in ACADEMIC_API
    assert "'/mobile/academic/exam-v2/my'" in ACADEMIC_API
    assert "'/mobile/academic/exam-v2/defer-options'" in ACADEMIC_API
    assert "'/mobile/academic/exam-v2/defer/apply'" in ACADEMIC_API
    assert "data: { examCourseId, reasonType, reason }" in ACADEMIC_API
    assert "academicStudentApi as studentApi" in EXAM_PAGE


def test_main_session_business_context_and_role_rollback_are_preserved():
    for token in (
        "useInternshipContextStore",
        "clearBusinessContexts()",
        "STUDENT_INTERNSHIP_BATCH_KEY",
        "const previousRole = this.currentRole",
        "const previousIdentity = { ...this.identity }",
        "this.currentRole = previousRole",
        "this.identity = previousIdentity",
    ):
        assert token in SESSION_STORE
    assert "clearSensitiveLocalDrafts" not in SESSION_STORE
    assert "tenantId:" not in SESSION_STORE
    assert "activeContextId:" not in SESSION_STORE


def test_academic_identity_enhancement_is_isolated_in_pinia_plugin():
    assert "pinia.use(academicSessionPlugin)" in MINIAPP_MAIN
    assert "store.$id !== 'session'" in SESSION_PLUGIN
    for token in (
        "tenantId",
        "activeContextId",
        "studentId",
        "clearSensitiveLocalDrafts()",
        "baseApplyRealUser",
        "baseSetStudentIdentity",
        "baseHydrateStudentProfile",
        "baseLogout",
    ):
        assert token in SESSION_PLUGIN


def test_student_evaluation_contract_remains_available_to_current_pages():
    assert "getMyEvaluationTasks: () => real.acadEvaluationTasks()" in STUDENT_API
    assert "submitEvaluation: (body) => real.acadEvaluationSubmit(body)" in STUDENT_API
