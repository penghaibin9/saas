"""学工统计范围静态合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_disbursement_stats_uses_student_scope_and_replaces_base_service():
    source = (ROOT / "backend/app/services/affairs_stats_integrity_guard.py").read_text(encoding="utf-8")
    assert "def disbursement_stats(user):" in source
    assert "StudentProfile.id == FundingDisbursement.student_id" in source
    assert "*student_conds" in source
    assert "funding.disbursement_stats = disbursement_stats" in source
