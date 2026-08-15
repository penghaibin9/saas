"""E-A01 / A01-2 RecruitmentCampaign targeted contracts."""
from __future__ import annotations

from datetime import datetime, timedelta
import inspect

from pydantic import ValidationError
from sqlalchemy import Index, UniqueConstraint

from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.modules.internship.schemas.internship_recruitment_campaign import ApplicationMaterialPolicy
from app.modules.internship.services import internship_recruitment_campaign_service as service


def _unique_sets():
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in InternshipRecruitmentCampaign.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_sets():
    return {
        tuple(column.name for column in index.columns)
        for index in InternshipRecruitmentCampaign.__table__.indexes
        if isinstance(index, Index)
    }


def test_campaign_model_matches_v3_fields_and_does_not_persist_phase():
    columns = set(InternshipRecruitmentCampaign.__table__.columns.keys())
    assert InternshipRecruitmentCampaign.__tablename__ == "t_internship_recruitment_campaign"
    assert {
        "tenant_id",
        "batch_id",
        "campaign_code",
        "campaign_name",
        "round_no",
        "status",
        "invite_start_at",
        "invite_end_at",
        "position_submit_start_at",
        "position_submit_end_at",
        "student_select_start_at",
        "student_select_end_at",
        "enterprise_decision_start_at",
        "enterprise_decision_end_at",
        "school_confirm_start_at",
        "school_confirm_end_at",
        "enterprise_access_end_at",
        "enterprise_confirm_required",
        "teacher_confirm_sla_hours",
        "application_material_policy_json",
        "remark",
        "version",
        "created_at",
        "updated_at",
        "is_deleted",
    } <= columns
    assert "phase" not in columns


def test_campaign_uniques_and_indexes_match_v3_contract():
    assert ("tenant_id", "campaign_code") in _unique_sets()
    assert ("tenant_id", "batch_id", "round_no") in _unique_sets()
    assert ("tenant_id", "batch_id", "status", "is_deleted") in _index_sets()
    assert (
        "tenant_id",
        "status",
        "student_select_start_at",
        "student_select_end_at",
    ) in _index_sets()


def test_phase_is_derived_from_status_and_windows_only():
    now = datetime(2026, 9, 10, 8, 0, 0)
    campaign = InternshipRecruitmentCampaign(
        tenant_id=1,
        batch_id=10,
        campaign_code="2026-A-1",
        campaign_name="2026 第一轮",
        round_no=1,
        status="DRAFT",
    )
    assert service.derive_campaign_phase(campaign, now=now) == "PREPARE"

    campaign.status = "OPEN"
    campaign.student_select_start_at = now - timedelta(hours=1)
    campaign.student_select_end_at = now + timedelta(hours=1)
    assert service.derive_campaign_phase(campaign, now=now) == "STUDENT_SELECTING"

    campaign.enterprise_decision_start_at = now - timedelta(minutes=5)
    campaign.enterprise_decision_end_at = now + timedelta(minutes=5)
    assert service.derive_campaign_phase(campaign, now=now) == "ENTERPRISE_DECIDING"

    campaign.status = "FROZEN"
    assert service.derive_campaign_phase(campaign, now=now) == "FROZEN"
    campaign.status = "CLOSED"
    assert service.derive_campaign_phase(campaign, now=now) == "CLOSED"
    campaign.status = "ARCHIVED"
    assert service.derive_campaign_phase(campaign, now=now) == "ARCHIVED"


def test_window_validation_rejects_half_pairs_reverse_ranges_and_short_access():
    now = datetime(2026, 9, 10, 8, 0, 0)
    try:
        service._validate_windows({"student_select_start_at": now})
        assert False, "half window must fail"
    except Exception as exc:
        assert getattr(exc, "code", None) == "VALIDATION_ERROR"

    try:
        service._validate_windows(
            {
                "student_select_start_at": now + timedelta(hours=1),
                "student_select_end_at": now,
            }
        )
        assert False, "reverse window must fail"
    except Exception as exc:
        assert getattr(exc, "code", None) == "VALIDATION_ERROR"

    try:
        service._validate_windows(
            {
                "student_select_start_at": now,
                "student_select_end_at": now + timedelta(hours=2),
                "enterprise_access_end_at": now + timedelta(hours=1),
            }
        )
        assert False, "enterprise access cannot end before recruitment windows"
    except Exception as exc:
        assert getattr(exc, "code", None) == "VALIDATION_ERROR"


def test_material_policy_schema_is_strict_versioned_and_uses_final_contact_modes():
    policy = ApplicationMaterialPolicy(
        profileRequired=True,
        requiredSections=["SELF_INTRO", "SKILLS"],
        requiredItemTypes=["PROJECT", "CERTIFICATE"],
        applicationStatementRequired=True,
        minStatementLength=20,
        allowedContactSharingModes=["MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT"],
    )
    data = policy.model_dump()
    assert data["schemaVersion"] == "V1"
    assert data["minStatementLength"] == 20
    assert data["allowedContactSharingModes"] == ["MASKED_ONLY", "AFTER_INTERVIEW", "AFTER_ACCEPT_INTENT"]
    try:
        ApplicationMaterialPolicy(schemaVersion="V2")
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown policy schema version must fail closed")
    try:
        ApplicationMaterialPolicy(unknownField=True)
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown material policy fields must be rejected")


def test_service_exposes_and_validates_material_policy_and_teacher_sla():
    values = service._body_values({
        "teacherConfirmSlaHours": 24,
        "applicationMaterialPolicy": {
            "schemaVersion": "V1",
            "profileRequired": True,
            "requiredSections": ["SELF_INTRO"],
            "requiredItemTypes": ["PROJECT"],
            "applicationStatementRequired": True,
            "minStatementLength": 12,
            "resumePdfEnabled": True,
            "allowedContactSharingModes": ["MASKED_ONLY", "AFTER_INTERVIEW"],
        },
    })
    assert values["teacher_confirm_sla_hours"] == 24
    assert values["application_material_policy_json"]["schemaVersion"] == "V1"
    assert values["application_material_policy_json"]["requiredSections"] == ["SELF_INTRO"]
    service._validate_identity(values)
    try:
        service._validate_identity({"teacher_confirm_sla_hours": 169})
    except Exception as exc:
        assert getattr(exc, "code", None) == "VALIDATION_ERROR"
    else:
        raise AssertionError("teacher SLA above 168h must fail closed")
    try:
        service._normalize_material_policy({"schemaVersion": "V1", "unknown": True})
    except Exception as exc:
        assert getattr(exc, "code", None) == "VALIDATION_ERROR"
    else:
        raise AssertionError("unknown service policy fields must fail closed")


def test_campaign_read_contract_returns_sla_and_material_policy():
    campaign = InternshipRecruitmentCampaign(
        id=8,
        tenant_id=1,
        batch_id=10,
        campaign_code="2026-A-2",
        campaign_name="2026 第二轮",
        round_no=2,
        status="DRAFT",
        teacher_confirm_sla_hours=48,
        application_material_policy_json={"schemaVersion": "V1", "profileRequired": True},
    )
    row = service._row(campaign)
    assert row["teacherConfirmSlaHours"] == 48
    assert row["applicationMaterialPolicy"]["schemaVersion"] == "V1"
    assert row["applicationMaterialPolicy"]["profileRequired"] is True


def test_mutations_lock_rows_and_require_expected_version():
    get_source = inspect.getsource(service._get_campaign)
    update_source = inspect.getsource(service.update_campaign)
    transition_source = inspect.getsource(service.transition_campaign)
    version_source = inspect.getsource(service._require_expected_version)

    assert "with_for_update()" in get_source
    assert "lock=True" in update_source
    assert "lock=True" in transition_source
    assert "expectedVersion" in version_source
    assert 'campaign.status != "DRAFT"' in update_source


def test_campaign_list_is_sql_paginated_not_full_materialized():
    source = inspect.getsource(service.list_campaigns)
    assert ".offset(" in source
    assert ".limit(page_size + 1)" in source
    assert "page_size = min(200" in source
