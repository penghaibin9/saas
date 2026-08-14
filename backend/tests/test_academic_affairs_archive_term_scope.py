from __future__ import annotations


def test_archive_cohort_term_scope_distinguishes_future_from_invalid():
    from app.modules.academic_affairs.services.academic_affairs_archive_term_scope import cohort_term_scope

    assert cohort_term_scope("2025-2026", 2, "2025") == {
        "state": "IN_SCOPE", "planTerm": 2, "rawPlanTerm": 2,
    }
    assert cohort_term_scope("2025-2026", 2, "2024") == {
        "state": "IN_SCOPE", "planTerm": 4, "rawPlanTerm": 4,
    }
    assert cohort_term_scope("2025-2026", 2, "2026") == {
        "state": "OUT_OF_SCOPE", "planTerm": None, "rawPlanTerm": 0,
    }
    assert cohort_term_scope("2025-2026", 2, "2019") == {
        "state": "OUT_OF_SCOPE", "planTerm": None, "rawPlanTerm": 14,
    }
    assert cohort_term_scope("2025-2026", 2, "20X6")["state"] == "INVALID"
    assert cohort_term_scope("bad", 2, "2025")["state"] == "INVALID"
    assert cohort_term_scope("2025-2026", 3, "2025")["state"] == "INVALID"
