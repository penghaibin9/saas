"""售前演示沙箱 20K 学校数据规格合同。

这里不创建 20K 数据库，保持普通 CI 轻量；只锁住规模、组织、专业班级分布与 2026-08 时点生命周期。
真正数据库行数/跨表关系由 scripts/check_sandbox_20k_school.py 在标准沙箱重建后验收。
"""
from collections import Counter

from app.services.sandbox_school_blueprint import (
    COLLEGE_MAJOR_BLUEPRINT,
    EXPECTED_CLASS_COUNT,
    EXPECTED_CLASSES_PER_GRADE,
    EXPECTED_COLLEGE_COUNT,
    EXPECTED_MAJOR_COUNT,
    EXPECTED_STAFF_ACCOUNT_COUNT,
    EXPECTED_STUDENT_COUNT,
    GRADE_STUDENT_COUNTS,
    MAJOR_CLASS_COUNTS_PER_GRADE,
    REFERENCE_DATE,
    STAFF_ACCOUNT_COUNTS,
    blueprint_summary,
    iter_class_specs,
    lifecycle_stage,
    student_name,
    student_no,
)


def test_20k_school_scale_contract():
    summary = blueprint_summary()
    assert REFERENCE_DATE == "2026-08-13"
    assert summary["students"] == EXPECTED_STUDENT_COUNT == 20_000
    assert summary["colleges"] == EXPECTED_COLLEGE_COUNT == 8
    assert summary["majors"] == EXPECTED_MAJOR_COUNT == 32
    assert summary["classes"] == EXPECTED_CLASS_COUNT == 384
    assert summary["classesPerGrade"] == EXPECTED_CLASSES_PER_GRADE == 128
    assert summary["staffAccounts"] == EXPECTED_STAFF_ACCOUNT_COUNT == 1280
    assert sum(GRADE_STUDENT_COUNTS.values()) == 20_000
    assert sum(STAFF_ACCOUNT_COUNTS.values()) == 1280
    assert STAFF_ACCOUNT_COUNTS["COUNSELOR"] == 96


def test_org_distribution_is_real_school_shaped_not_artificially_uniform():
    classes = list(iter_class_specs())
    by_grade = Counter(x.grade for x in classes)
    by_college = Counter(x.college_code for x in classes)
    by_major = Counter(x.major_code for x in classes)

    assert by_grade == {"2024": 128, "2025": 128, "2026": 128}
    assert by_college == {
        "C01": 57, "C02": 51, "C03": 48, "C04": 54,
        "C05": 39, "C06": 45, "C07": 54, "C08": 36,
    }
    assert by_major == {
        major_code: annual_classes * 3
        for major_code, annual_classes in MAJOR_CLASS_COUNTS_PER_GRADE.items()
    }
    # 热门/长尾专业必须同时存在；不允许回退成每专业每届固定 4 班的“压测型假学校”。
    assert min(MAJOR_CLASS_COUNTS_PER_GRADE.values()) == 2
    assert max(MAJOR_CLASS_COUNTS_PER_GRADE.values()) == 8
    assert len(set(MAJOR_CLASS_COUNTS_PER_GRADE.values())) >= 5
    assert min(x.target_students for x in classes) >= 50
    assert max(x.target_students for x in classes) <= 55
    assert sum(x.target_students for x in classes) == 20_000
    assert len({x.class_code for x in classes}) == 384
    assert len(COLLEGE_MAJOR_BLUEPRINT) == 8


def test_professional_enrollment_distribution_matches_20k_school_shape():
    summary = blueprint_summary()
    # 三届累计学院人数：信息/经管/医药更大，艺设/文旅较小，符合专业热度差异。
    assert summary["studentsByCollege"] == {
        "C01": 2983,
        "C02": 2669,
        "C03": 2512,
        "C04": 2826,
        "C05": 2030,
        "C06": 2330,
        "C07": 2790,
        "C08": 1860,
    }
    assert sum(summary["studentsByCollege"].values()) == 20_000
    assert summary["classesByCollegePerGrade"] == {
        "C01": 19, "C02": 17, "C03": 16, "C04": 18,
        "C05": 13, "C06": 15, "C07": 18, "C08": 12,
    }


def test_august_2026_lifecycle_distribution_matches_school_calendar():
    grade24 = Counter(lifecycle_stage("2024", seq) for seq in range(1, 6401))
    grade25 = Counter(lifecycle_stage("2025", seq) for seq in range(1, 6601))
    grade26 = Counter(lifecycle_stage("2026", seq) for seq in range(1, 7001))

    assert grade24 == {"INTERN": 5600, "ENROLLED": 800}
    assert grade25 == {"ENROLLED": 6600}
    assert grade26 == {
        "ADMITTED": 2100,
        "PRE_STUDENT_VERIFIED": 3150,
        "REGISTERED_PENDING_ENROLLMENT": 1750,
    }


def test_sales_story_students_are_stable_and_background_ids_are_unique():
    assert student_no("2026", 1) == "2026S0001"
    assert student_name("2026", 1) == "李体验"
    assert student_name("2025", 1) == "陈思雨"
    assert student_name("2024", 1) == "周启航"

    ids = {
        student_no(grade, seq)
        for grade, total in GRADE_STUDENT_COUNTS.items()
        for seq in range(1, total + 1)
    }
    assert len(ids) == 20_000
