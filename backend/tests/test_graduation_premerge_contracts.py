"""毕业设计合并前最小静态合同。

锁定本轮复审发现的回归点，并确认专项工作流持续覆盖 MySQL 迁移、
毕业设计测试与三端构建；不替代真实页面验收。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_extension_models_are_registered_in_alembic_metadata():
    source = read("backend/app/db/base.py")
    ast.parse(source, filename="backend/app/db/base.py")
    assert "from app.models import graduation_extension as _graduation_extension" in source


def test_teacher_mobile_lists_use_sql_current_page_instead_of_collect_all():
    source = read(
        "backend/app/modules/graduation/services/graduation_mobile_teacher_query_service.py"
    )
    router = read("backend/app/api/v1/mobile_graduation_teacher_context.py")
    ast.parse(
        source,
        filename=(
            "backend/app/modules/graduation/services/"
            "graduation_mobile_teacher_query_service.py"
        ),
    )
    ast.parse(router, filename="backend/app/api/v1/mobile_graduation_teacher_context.py")

    assert "def _collect" not in source
    assert "_MAX_PAGES" not in source
    assert "def taskbooks_page" in source
    assert "def midterms_page" in source
    assert "def grades_page" in source
    assert "select(func.count(" in source
    assert ".offset(" in source and ".limit(" in source
    assert "GraduationMidterm.status.in_(_ACTIONABLE_MIDTERM_STATUSES)" in source
    assert '_ACTIONABLE_MIDTERM_STATUSES = ("PENDING", "RECTIFY_SUBMITTED")' in source
    assert 'status="CALCULATED"' in source
    assert "mobile_queries.taskbooks_page" in router
    assert "mobile_queries.midterms_page" in router
    assert "mobile_queries.grades_page" in router


def test_targeted_workflow_covers_all_premerge_commands():
    workflow = read(".github/workflows/graduation-targeted-repair.yml")
    for command in (
        "alembic heads",
        "alembic upgrade head",
        "pytest tests/test_graduation*.py",
        "npm run lint",
        "npm run build",
        "npm run build:h5",
        "npm run build:mp-weixin",
    ):
        assert command in workflow
    assert "working-directory: student-portal" in workflow
    assert "MySQL 毕设核心行锁并发验证" in workflow