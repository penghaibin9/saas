"""P0-10/P0-11：有效成绩策略欠账必须进入归档门禁。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_archive_grade_policy_guard_is_installed():
    init_source = (
        ROOT / "backend/app/modules/academic_affairs/services/__init__.py"
    ).read_text(encoding="utf-8")
    guard_source = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_archive_grade_policy_guard.py"
    ).read_text(encoding="utf-8")

    assert "academic_affairs_archive_grade_policy_guard" in init_source
    assert "_evaluator.evaluate_grade = evaluate_grade" in guard_source


def test_policy_debt_changes_grade_archive_result_to_blocked():
    source = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_archive_grade_policy_guard.py"
    ).read_text(encoding="utf-8")

    assert 'result["result"] = "BLOCKED"' in source
    assert 'result["ruleCode"] = "GRADE_EFFECTIVE_POLICY_DEBT"' in source
    assert "missingPolicySnapshot" in source
    assert "legacyNameKey" in source
    assert "/admin/academic-affairs/grade-identity-debt" in source


def test_historical_debt_is_not_auto_backfilled():
    migration = (
        ROOT / "backend/alembic/versions/0132_aa_effective_grade_policy_snapshot.py"
    ).read_text(encoding="utf-8")
    policy = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_effective_grade_policy_service.py"
    ).read_text(encoding="utf-8")

    assert "历史成绩不回填、不按课程名猜测" in migration
    assert "只读欠账：历史成绩不自动补快照" in policy
