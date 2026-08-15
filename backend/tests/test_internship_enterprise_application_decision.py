from __future__ import annotations

import inspect

from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.modules.internship.services import internship_enterprise_application_decision_service as svc


def test_decision_is_side_fact_with_separate_effect_state():
    columns = set(InternshipEnterpriseApplicationDecision.__table__.columns.keys())
    assert {
        "application_id", "material_snapshot_id", "decision_status", "effect_status",
        "valid_until", "superseded_reason",
    } <= columns
    assert "record_id" not in columns
    assert "placement_result" not in columns


def test_enterprise_scope_comes_from_context_not_company_id_body():
    source = inspect.getsource(svc._owned_application_in_tx)
    assert "InternshipPosition.company_id == context.company_id" in source
    assert "InternshipPosition.campaign_id == context.campaign_id" in source


def test_enterprise_list_is_sql_paginated_and_never_exposes_sibling_preferences_or_phone():
    source = inspect.getsource(svc.list_owned_applications_in_tx)
    assert "func.count" in source
    assert ".offset(" in source and ".limit(" in source
    assert 'InternshipApplication.status == "PENDING_REVIEW"' in source
    assert "context.company_id" in source and "context.campaign_id" in source
    assert "contactPhone" not in source
    assert "phone" not in source.lower()
    assert "siblings" not in source.lower()


def test_decision_writes_only_submitted_current_material_and_respects_campaign_window():
    source = inspect.getsource(svc.set_decision_in_tx)
    guard = inspect.getsource(svc._assert_decision_write_window)
    assert 'application.status != "PENDING_REVIEW"' in source
    assert "group.current_material_snapshot_id != application.material_snapshot_id" in source
    assert "enterprise_decision_start_at" in guard
    assert "enterprise_decision_end_at" in guard
    assert 'campaign.status != "OPEN"' in guard
    assert '{"OPEN", "FROZEN"}' in guard  # withdraw-accept safety path only


def test_accept_intent_only_locks_group_and_never_assigns():
    source = inspect.getsource(svc.set_decision_in_tx)
    assert "lock_for_accept_intent_in_tx" in source
    assert "assign_position_in_tx" not in source
    assert "PUBLISH" not in source
    assert 'decision.effect_status = "SUPERSEDED"' in source
    assert "ENTERPRISE_APPLICATION_WITHDRAW_ACCEPT" in source
    assert "decision.valid_until is not None and decision.valid_until <= now" in source


def test_decision_transitions_are_audited_with_real_enterprise_actor():
    source = inspect.getsource(svc.set_decision_in_tx)
    assert "internship_audit_service.add_audit" in source
    assert 'target_type="INTERNSHIP_ENTERPRISE_APPLICATION_DECISION"' in source
    assert "context.member_id" in source
    assert "context.user_id" in source


def test_expired_superseded_or_consumed_decision_cannot_be_overwritten():
    source = inspect.getsource(svc.set_decision_in_tx)
    assert 'decision.effect_status != "ACTIVE"' in source
    consume = inspect.getsource(svc.consume_accept_intent_in_tx)
    assert 'decision.effect_status != "ACTIVE"' in consume
    assert 'decision.effect_status = "CONSUMED"' in consume


def test_contact_view_reads_current_verified_contact_never_snapshot_pii_and_audits_reveal():
    source = inspect.getsource(svc.contact_view_in_tx)
    assert "StudentContact" in source
    assert 'StudentContact.verified_status == "VERIFIED"' in source
    assert 'StudentContact.contact_type.in_(("PHONE", "EMAIL"))' in source
    assert "decrypt_field" in source
    assert "group.contact_consent_revoked_at" in source
    assert 'mode == "MASKED_ONLY"' in source
    assert 'mode == "AFTER_INTERVIEW"' in source
    assert 'mode == "AFTER_ACCEPT_INTENT"' in source
    assert 'mode == "IMMEDIATE"' in source
    assert 'action="CONTACT_VIEW"' in source
    assert "revealedTypes" in source
    assert 'snapshot.profile_snapshot_json' not in source
    assert 'snapshot.school_fact_snapshot_json' not in source


def test_contact_view_stage_gate_is_fail_closed():
    source = inspect.getsource(svc.contact_view_in_tx)
    assert 'decision.decision_status in {"INTERVIEW", "ACCEPT_INTENT"}' in source
    assert 'decision.decision_status == "ACCEPT_INTENT"' in source
    assert 'decision.effect_status in {"ACTIVE", "CONSUMED"}' in source
    assert 'raise AppException("NO_PERMISSION"' in source
