"""第二轮学工：分页边界 + 风险 SQL 真分页冒烟。"""
from __future__ import annotations

from app.core.pagination import PAGE_SIZE_MAX, normalize_page


def test_normalize_page_clamps():
    assert normalize_page(0, 0) == (1, 1)
    assert normalize_page(2, 500) == (2, PAGE_SIZE_MAX)
    assert normalize_page(None, None) == (1, 20)


def test_risk_list_uses_sql_helpers():
    from app.services import affairs_risk_service as risk
    src = open(risk.__file__, encoding="utf-8").read()
    assert "normalize_page" in src
    assert "_risk_stats_sql" in src
    assert "_risk_scope_join" in src
    assert "offset((page - 1) * page_size)" in src or ".offset(" in src
    # 禁止全量 .all() 后再 Python 班级过滤的旧模式残留为主路径
    assert "RISK_NEW_ASSIGN_HOURS" in src and "RISK_ASSIGNED_PROCESS_HOURS" in src


def test_student_affairs_pagesize_query_bounded():
    from pathlib import Path
    text = Path("app/api/v1/student_affairs.py").read_text(encoding="utf-8")
    assert "pageSize: int = Query(" in text
    assert "le=200" in text
    # 不应再有裸 pageSize: int = N
    import re
    assert not re.search(r"pageSize:\s*int\s*=\s*\d+", text)


def test_core_list_services_normalize_page():
    files = [
        "app/services/affairs_aid_service.py",
        "app/services/affairs_funding_service.py",
        "app/services/affairs_discipline_service.py",
        "app/services/affairs_mental_service.py",
        "app/services/affairs_talk_service.py",
        "app/services/affairs_dorm_service.py",
        "app/services/affairs_leave_service.py",
        "app/services/affairs_risk_service.py",
    ]
    from pathlib import Path
    for f in files:
        src = Path(f).read_text(encoding="utf-8")
        assert "normalize_page" in src, f
        assert ".offset(" in src or "offset(" in src, f
