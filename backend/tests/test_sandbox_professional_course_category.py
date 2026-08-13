from __future__ import annotations


def test_professional_course_category_matches_final_three_year_modules():
    from app.services.sandbox_school_professional_runner import _canonical_major_course_category

    assert [_canonical_major_course_category(index) for index in range(17)] == ["MAJOR_CORE"] * 17
    assert [_canonical_major_course_category(index) for index in range(17, 23)] == ["PRACTICE"] * 6
