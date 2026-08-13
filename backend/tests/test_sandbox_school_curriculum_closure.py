from __future__ import annotations


def test_three_year_curriculum_credit_structure_and_term_truth():
    from app.services.sandbox_school_academic_affairs_seed import PUBLIC_COURSES, MAJOR_COURSE_TEMPLATES
    from app.services.sandbox_school_curriculum_closure import (
        CREDIT_STRUCTURE,
        MAJOR_EXTENSION_LABELS,
        PRACTICE_LABELS,
        PUBLIC_EXPANSION,
        _term_assignments,
    )

    public_credit = sum(float(row[4]) for row in PUBLIC_COURSES) + sum(float(row[2]) for row in PUBLIC_EXPANSION)
    major_credit = (
        sum(float(row[4]) for row in MAJOR_COURSE_TEMPLATES)
        + 3 * 4.0
        + len(MAJOR_EXTENSION_LABELS) * 4.0
    )
    practice_credit = sum(float(row[1]) for row in PRACTICE_LABELS)
    assert public_credit == 30.0
    assert major_credit == 64.0
    assert practice_credit == 46.0
    assert sum(float(value) for _module, value in CREDIT_STRUCTURE) == 140.0

    public_codes = [f"PUB{i:03d}" for i in range(1, 15)]
    major_codes = [f"M-01-{i:02d}" for i in range(1, 24)]

    plan_2025 = _term_assignments("2025", public_codes, major_codes)
    assert {code for code, term in plan_2025.items() if term == 2} == set(major_codes[:4])
    assert {code for code, term in plan_2025.items() if term == 3} == {
        major_codes[4], major_codes[5], "PUB002", "PUB003",
    }

    plan_2024 = _term_assignments("2024", public_codes, major_codes)
    assert {code for code, term in plan_2024.items() if term == 4} == set(major_codes[5:9])
    assert not {code for code, term in plan_2024.items() if term == 5}

    plan_2026 = _term_assignments("2026", public_codes, major_codes)
    assert {code for code, term in plan_2026.items() if term == 1} == {major_codes[0], "PUB004"}

    for plan in (plan_2024, plan_2025, plan_2026):
        assert len(plan) == 37
        assert set(plan) == set(public_codes + major_codes)
        assert all(1 <= term <= 6 for term in plan.values())
