"""E-A01 / A01-2 RecruitmentCampaign targeted contracts."""
from __future__ import annotations

from datetime import datetime, timedelta
import inspect

from sqlalchemy import Index, UniqueConstraint

from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
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
