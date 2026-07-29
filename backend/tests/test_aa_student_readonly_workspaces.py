"""学生 PC 查询类教务页面必须独立读取本人数据，不再加载旧综合页全量接口。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readonly_routes_use_shared_fail_closed_view():
    router = _read("student-portal/src/router/index.js")

    for model in ("attendance", "calendar", "clearance", "credits", "warning", "graduation"):
        assert f"academicReadModel: '{model}'" in router
    assert router.count("StudentAcademicReadOnlyView.vue") >= 6
    for path in ("attendance", "calendar", "clearance", "credits", "warning", "graduation"):
        assert f"academicSection('academic/{path}'" not in router


def test_readonly_view_has_explicit_api_allowlist():
    source = _read("student-portal/src/views/academic/StudentAcademicReadOnlyView.vue")

    for method in (
        "portalApi.academicAttendance()",
        "portalApi.academicCalendar()",
        "portalApi.academicClearance()",
        "portalApi.academicCredits()",
        "portalApi.academicWarning()",
        "portalApi.academicGraduationAudit()",
    ):
        assert method in source
    assert "if (!config.value.loader) throw new Error" in source
    assert "当前路由未绑定允许的教务读取接口" in source


def test_readonly_views_do_not_invent_authoritative_conclusions():
    source = _read("student-portal/src/views/academic/StudentAcademicReadOnlyView.vue")

    assert "客户端不自行推算节假日或考试周" in source
    assert "毕业资格、证书和结业结论只能由学校正式审核发布" in source
    assert "考勤状态来自教师提交的正式课堂考勤场次" in source
    assert "最终有效成绩以成绩查询件和教务归档为准" in source
    assert "window.prompt" not in source
