"""学生 PC 补考重修与免修必须走独立真实工作区。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_makeup_route_uses_dedicated_page_not_legacy_subtab():
    router = _read("student-portal/src/router/academicRoutes.js")

    assert "StudentMakeupView.vue" in router
    assert "academicSection('makeup'" not in router


def test_makeup_workspace_reads_and_writes_only_real_portal_contracts():
    source = _read("student-portal/src/views/academic/StudentMakeupView.vue")

    for token in (
        "portalApi.academicMakeup()",
        "portalApi.academicMakeupOptions()",
        "portalApi.academicRetakeApply",
        "portalApi.academicExemptionApply",
        "gradeId: command.gradeId",
        "courseId: command.courseId",
        "sameOrigin && persistentCommandCleared(persistent)",
        "sameCourse && persistentCommandCleared(persistent)",
        "await load()",
    ):
        assert token in source
    assert "receiptTone.value = 'waiting'" in source
    assert "studentAcademicWriteErrorKind(e)" in source
    assert "window.prompt" not in source


def test_makeup_workspace_separates_result_retake_and_exemption():
    source = _read("student-portal/src/views/academic/StudentMakeupView.vue")

    for tab in ("overview", "retake"):
        assert f"tab === '{tab}'" in source
    assert "tab = 'exemption'" in source
    assert "retakeOptions" in source
    assert "exemptionOptions" in source
    assert "提交后由学校按各自规则审核，不直接生成正式成绩" in source
