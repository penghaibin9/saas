from __future__ import annotations

import inspect

from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.modules.internship.services import internship_enterprise_application_decision_service as svc


def test_decision_is_side_fact_with_separate_effect_state():
    columns=set(InternshipEnterpriseApplicationDecision.__table__.columns.keys())
    assert {"application_id","material_snapshot_id","decision_status","effect_status","valid_until","superseded_reason"} <= columns
    assert "record_id" not in columns
    assert "placement_result" not in columns


def test_enterprise_scope_comes_from_context_not_company_id_body():
    source=inspect.getsource(svc._owned_application_in_tx)
    assert "InternshipPosition.company_id == context.company_id" in source
    assert "InternshipPosition.campaign_id == context.campaign_id" in source


def test_accept_intent_only_locks_group_and_never_assigns():
    source=inspect.getsource(svc.set_decision_in_tx)
    assert "lock_for_accept_intent_in_tx" in source
    assert "assign_position_in_tx" not in source
    assert "PUBLISH" not in source
    assert 'effect_status = "SUPERSEDED"' in source


def test_consumed_accept_intent_cannot_be_reused():
    source=inspect.getsource(svc.consume_accept_intent_in_tx)
    assert 'decision.effect_status != "ACTIVE"' in source
    assert 'decision.effect_status = "CONSUMED"' in source
