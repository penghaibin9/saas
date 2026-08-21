from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_t7_teacher_employment_routes_require_existing_employment_permissions():
    route = _src("backend/app/api/v1/teacher_mobile_employment.py")
    assert 'require_module("employment")' in route
    assert 'require_permission("employment.student.view")' in route
    assert 'require_permission("employment.unemployed.manage")' in route
    assert 'require_permission("employment.material.view")' in route
    assert route.count('require_permission("employment.material.approve")') >= 2
    assert "require_staff" not in route


def test_t7_overview_kpis_are_exact_scoped_sql_not_first_page_sample_counts():
    route = _src("backend/app/api/v1/teacher_mobile_employment.py")
    stats = _src("backend/app/services/teacher_mobile_employment_stats_service.py")
    assert 'payload["stats"] = stats_svc.exact_stats(user=user)' in route
    assert 'select(func.count()).select_from(EmpStudent)' in stats
    assert 'scope = runtime._scope_condition(db, user)' in stats
    assert 'EmpStudent.destination_type != "UNEMPLOYED"' in stats
