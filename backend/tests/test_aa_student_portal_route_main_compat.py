"""教务独立路由不得删除主线学生门户的实习和毕业设计路由合同。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "student-portal/src/router/index.js").read_text(encoding="utf-8")


def test_academic_routes_remain_independent_and_legacy_safe():
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
        assert token in SOURCE


def test_main_internship_routes_are_preserved():
    for path in (
        "internship/agreements",
        "internship/applications",
        "internship/insurance",
        "internship/complaints",
        "internship/visits",
        "internship/process",
        "internship/compliance",
    ):
        assert f"path: '{path}'" in SOURCE
    for name in (
        "internship-agreement-detail",
        "internship-application-detail",
        "internship-insurance-detail",
        "internship-complaint-detail",
        "internship-visit-detail",
    ):
        assert f"name: '{name}'" in SOURCE


def test_main_graduation_routes_are_preserved():
    for path in (
        "graduation/guidance",
        "graduation/task-book",
        "graduation/proposal",
        "graduation/midterm",
        "graduation/outcome",
        "graduation/evaluation",
        "graduation/review",
        "graduation/defense",
        "graduation/grade",
        "graduation/archive",
        "graduation/topic-change",
        "graduation/mentor-change",
        "graduation/defense-apply",
        "graduation/postpone",
        "graduation/midterm-appeal",
        "graduation/defense-appeal",
        "graduation/grade-appeal",
        "graduation/archive-appeal",
    ):
        assert f"path: '{path}'" in SOURCE


def test_long_lived_branch_uses_build_safe_optional_views():
    assert "import.meta.glob('../views/**/*.vue')" in SOURCE
    assert "const optionalView =" in SOURCE
    assert "optionalViews[`../views/${relativePath}.vue`] || fallback" in SOURCE
    # 主线新增页面不得在旧分支上使用会导致 Vite 直接解析失败的静态 import。
    assert "() => import('../views/internship/InternshipAgreementListView.vue')" not in SOURCE
    assert "() => import('../views/graduation/GraduationGuidanceView.vue')" not in SOURCE
