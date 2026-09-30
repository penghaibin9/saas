"""学生 PC 考试与缓考必须使用独立、本人范围、服务器权威的工作区。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_exam_route_uses_dedicated_page():
    router = _read("student-portal/src/router/academicRoutes.js")

    assert "StudentExamView.vue" in router
    assert "academicSection('exam'" not in router


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
    assert "本页面只显示本人正式考试安排；缓考申请不会自动修改考试时间。" in source
    assert "考试信息来自学校本人正式安排。入场证件要求以学校通知为准。" in source


def test_exam_workspace_keeps_schedule_apply_and_records_distinct_in_state():
    source = _read("student-portal/src/views/academic/StudentExamView.vue")

    assert "['schedule', 'apply', 'records'].includes" in source
    assert "? String(route.query.tab) : 'schedule'" in source
    assert "tab === 'apply'" in source
    assert "我的缓考申请" in source
    assert "returnedDeferrals" in source
    assert "String(record.status || '').toUpperCase() === 'RETURNED'" in source
    assert "if (returnedDeferrals.value.length && tab.value === 'schedule') tab.value = 'records'" in source
    assert "window.prompt" not in source
