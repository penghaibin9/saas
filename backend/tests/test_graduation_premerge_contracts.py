"""毕业设计合并前最小静态合同。

只锁定本轮复审发现的两个回归点；不替代 MySQL、pytest、构建和真实页面验收。
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


def test_teacher_mobile_lists_are_collected_before_batch_pagination():
    source = read(
        "backend/app/modules/graduation/services/graduation_mobile_taskbook_bridge.py"
    )
    ast.parse(
        source,
        filename=(
            "backend/app/modules/graduation/services/"
            "graduation_mobile_taskbook_bridge.py"
        ),
    )
    assert "def _collect" in source
    assert "mobile.graduation_taskbook_list = taskbooks" in source
    assert "mobile.graduation_midterm_queue = midterms" in source
    assert "mobile.graduation_grade_queue = grades" in source
    assert 'status="CALCULATED"' in source
    assert '{"PENDING", "RECTIFY_SUBMITTED"}' in source
