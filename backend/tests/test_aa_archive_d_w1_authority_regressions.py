"""Academic D-W1 authority regression tests.

Four-state semantics may harden the public archive contract, but must not replace the
mature domain authorities that already existed on the frozen main baseline.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_archive_domain_policy.py"


@pytest.fixture(autouse=True)
def _tenant_context():
    from app.core.context import set_tenant

    set_tenant({"tenantId": "1"})
    try:
        yield
    finally:
        set_tenant(None)


def _policy_source() -> str:
    return POLICY.read_text(encoding="utf-8")


def test_d_w1_domain_orchestration_keeps_mature_authority_chain():
    """W1 must wrap the existing authority chain, not call partial semantic helpers directly."""
    source = _policy_source()

    for token in (
        "base = _core._evaluate_domains(db, term_id, term_code, college_ids)",
        "results = _semantic.evaluate_first_batch(",
        "db, term_id, term_code, base, college_ids=college_ids",
        'results["GRADE"] = _safe(',
        'apply_effective_grade_policy_debt(db, term_code, results["GRADE"])',
    ):
        assert token in source, f"missing mature archive orchestration token: {token}"

    # These functions do not belong to academic_affairs_archive_rule_evaluator; calling
    # them through _safe only converts AttributeError into UNKNOWN and makes the gate unusable.
    for forbidden in (
        "_semantic.evaluate_student_status(",
        "_semantic.evaluate_registration(",
        "_semantic.evaluate_exam(",
        "_semantic.evaluate_schedule(db, term_id, college_ids)",
        "_semantic.evaluate_grade(db, term_code, college_ids)",
    ):
        assert forbidden not in source, f"invalid D-W1 semantic wiring remains: {forbidden}"


def test_d_w1_effective_grade_policy_debt_gate_still_exists():
    """Historical grade-policy debt is an established archive blocker and cannot disappear in W1."""
    source = _policy_source()

    for token in (
        "def apply_effective_grade_policy_debt",
        "policy_snapshot_debt(db, term=term_code)",
        '"ruleCode": "GRADE_EFFECTIVE_POLICY_DEBT"',
        "missingPolicySnapshot",
        "legacyNameKey",
        "/admin/academic-affairs/grade-identity-debt",
    ):
        assert token in source, f"missing effective-grade debt authority token: {token}"


def test_d_w1_textbook_gate_keeps_distribution_and_fee_ledger_authority():
    """N/A is a state wrapper; it must not collapse the textbook lifecycle to legacy order/fee tables."""
    source = _policy_source()

    for token in (
        "AaTextbookOrderBatch",
        "AaTextbookOrderItem",
        "AaTextbookDistributionBatch",
        "AaTextbookDistributionRecord",
        "AaTextbookFeeLedger",
        "missing_distribution",
        "unfinished_distributions",
        "pending_records",
        "missing_fees",
        "unsettled",
    ):
        assert token in source, f"missing textbook archive authority token: {token}"

    assert "from app.models import AaTextbookFee, AaTextbookOrder" not in source
    assert '"TEXTBOOK", "NOT_APPLICABLE"' in source
    assert '"TEXTBOOK", "UNKNOWN"' in source


class _FakeQuery:
    def __init__(self, *, rows=None, first=None):
        self._rows = list(rows or [])
        self._first = first

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._first


class _StatusChangeDb:
    def __init__(self, *, term, rows):
        self.term = term
        self.rows = list(rows)

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "AaTerm":
            return _FakeQuery(first=self.term)
        if name == "AaStatusChange":
            return _FakeQuery(rows=self.rows)
        raise AssertionError(f"unexpected model: {name}")


def test_d_w1_unscoped_status_change_is_unknown_not_pass():
    """A record with neither term nor usable date cannot be silently excluded from the term gate."""
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    term = SimpleNamespace(
        id=9,
        tenant_id=1,
        start_date=datetime(2026, 2, 20),
        end_date=datetime(2026, 7, 10),
        is_deleted=False,
    )
    unresolved = SimpleNamespace(
        term_code=None,
        effective_date=None,
        created_at=None,
        updated_at=None,
        status="APPROVED",
    )
    result = policy.evaluate_status_change(
        _StatusChangeDb(term=term, rows=[unresolved]),
        9,
        "2025-2026-2",
    )

    assert result["result"] == "UNKNOWN"
    assert result["present"] is False
    assert int(result["blockingCount"]) >= 1
    assert result["ruleCode"] == "STATUS_CHANGE_SCOPE_UNKNOWN"
    assert "无法确定" in result["summary"] or "待迁移" in result["summary"]
