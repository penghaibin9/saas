"""学生 PC 考试与缓考必须使用独立、本人范围、服务器权威的工作区。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_exam_route_uses_dedicated_page():
    router = _read("student-portal/src/router/index.js")

    assert "StudentExamView.vue" in router
    assert "academicSection('academic/exam'" not in router


def test_exam_workspace_uses_real_exam_and_defer_contracts():
    source = _read("student-portal/src/views/academic/StudentExamView.vue")

    for token in (
        "portalApi.academicExam()",
        "portalApi.academicExamDeferOptions()",
        "portalApi.academicExamDefer()",
        "portalApi.academicExamDeferApply",
        "portalApi.academicExamDeferResubmit",
        "examCourseId:",
        "reasonType:",
        "reason:",
        "await load()",
    ):
        assert token in source
    assert "考试日期、时间、考场、座位和缓考资格均以服务器已发布数据为准" in source


def test_exam_workspace_separates_schedule_apply_and_records():
    source = _read("student-portal/src/views/academic/StudentExamView.vue")

    for tab in ("schedule", "apply", "records"):
        assert f"tab === '{tab}'" in source
    assert "returnedDeferrals" in source
    assert "String(record.status || '').toUpperCase() === 'RETURNED'" in source
    assert "window.prompt" not in source
