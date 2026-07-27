"""学生 PC 等级考试报名必须使用独立本人工作区。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_level_exam_route_uses_dedicated_page():
    router = _read("student-portal/src/router/index.js")

    assert "StudentLevelExamView.vue" in router
    assert "academicSection('academic/level-exam'" not in router


def test_level_exam_workspace_uses_real_registration_contracts():
    source = _read("student-portal/src/views/academic/StudentLevelExamView.vue")

    assert "portalApi.academicLevelExam()" in source
    assert "portalApi.academicLevelRegister(id)" in source
    assert "portalApi.academicLevelCancel(id)" in source
    assert "await load()" in source
    assert "报名成功不等同于缴费完成或准考资格确认" in source
    assert "允许代替他人报名" in source
    assert "window.prompt" not in source


def test_level_exam_workspace_blocks_cancel_after_locked_statuses():
    source = _read("student-portal/src/views/academic/StudentLevelExamView.vue")

    for status in ("PAID", "CONFIRMED", "APPROVED"):
        assert status in source
    assert "!withinWindow(exam)" in source
    assert "exam.canRegister === false" in source
    assert "exam.canCancel === false" in source
