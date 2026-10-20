from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_sandbox_early_graduation_rule_keeps_the_canonical_proposal_material():
    """The sandbox must not advertise a proposal form that its real state machine rejects."""
    source = (ROOT / "backend/app/services/sandbox_school_graduation_operational_seed.py").read_text(encoding="utf-8")

    assert "def _ensure_canonical_proposal_report_item" in source
    assert 'material_code="PROPOSAL_REPORT"' in source
    assert 'required_items_json=["TOPIC_FORM", "PROPOSAL_REPORT"]' in source
    assert 'report["proposalReportRuleReady"] = True' in source
