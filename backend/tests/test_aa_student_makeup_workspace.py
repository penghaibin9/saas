"""学生 PC 补考重修与免修必须走独立真实工作区。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_makeup_route_uses_dedicated_page_not_legacy_subtab():
    router = _read("student-portal/src/router/index.js")

    assert "StudentMakeupView.vue" in router
    assert "academicSection('academic/makeup'" not in router


def test_makeup_workspace_reads_and_writes_only_real_portal_contracts():
    source = _read("student-portal/src/views/academic/StudentMakeupView.vue")

    for token in (
        "portalApi.academicMakeup()",
        "portalApi.academicMakeupOptions()",
        "portalApi.academicRetakeApply",
        "portalApi.academicExemptionApply",
        "sourceType:",
        "sourceId:",
        "acadGradeId:",
        "courseCode:",
        "await load()",
    ):
        assert token in source
    assert "接口失败时显示假成功" in source
    assert "window.prompt" not in source


def test_makeup_workspace_separates_result_retake_and_exemption():
    source = _read("student-portal/src/views/academic/StudentMakeupView.vue")

    for tab in ("overview", "retake", "exemption"):
        assert f"tab === '{tab}'" in source
    assert "retakeOptions" in source
    assert "exemptionOptions" in source
    assert "报名资格、时间冲突和收费规则以服务器最终校验为准" in source
