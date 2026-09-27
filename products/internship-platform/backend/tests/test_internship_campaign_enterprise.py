"""E-A01 / A01-3 CampaignEnterprise targeted contracts."""
from __future__ import annotations

import inspect

from sqlalchemy import Index, UniqueConstraint

from app.models.internship_enterprise_portal import InternshipCampaignEnterprise
from app.modules.internship.services import internship_campaign_enterprise_service as service


def _unique_sets():
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in InternshipCampaignEnterprise.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_sets():
    return {
        tuple(column.name for column in index.columns)
        for index in InternshipCampaignEnterprise.__table__.indexes
        if isinstance(index, Index)
    }


def test_campaign_enterprise_model_only_owns_participation_fact():
    columns = set(InternshipCampaignEnterprise.__table__.columns.keys())
    assert InternshipCampaignEnterprise.__tablename__ == "t_internship_campaign_enterprise"
    assert {
        "tenant_id", "campaign_id", "company_id", "status", "invite_source",
        "invited_by_user_id", "invited_at", "accepted_at", "declined_at",
        "revoked_at", "revoke_reason", "version", "created_at", "updated_at", "is_deleted",
    } <= columns
    assert not {"qualification_status", "blacklist", "coop_status", "access_valid_until"} & columns


def test_campaign_enterprise_unique_and_indexes_are_tenant_scoped():
    assert ("tenant_id", "campaign_id", "company_id") in _unique_sets()
    assert ("tenant_id", "campaign_id", "status", "is_deleted") in _index_sets()
    assert ("tenant_id", "company_id", "status", "is_deleted") in _index_sets()


def test_company_admission_reads_emp_company_instead_of_copying_statuses():
    source = inspect.getsource(service._get_company)
    assert "EmpCompany.tenant_id == tenant_id" in source
    assert "company.blacklist" in source
    assert 'company.coop_status != "ACTIVE"' in source
    assert 'company.qualification_status != "PASSED"' in source
    assert "company.access_valid_until" in source


def test_invite_is_campaign_locked_tenant_scoped_and_uses_shared_invite_window():
    source = inspect.getsource(service.invite_company)
    assert "lock=True" in source
    assert 'assert_campaign_operation_window(campaign, "INVITE", now=now)' in source
    assert "require_admission=True" in source
    assert "InternshipCampaignEnterprise.tenant_id == tenant_id" in source
    assert ".with_for_update()" in source
    assert "终态参与记录" in source


def test_participation_transition_requires_version_revoke_reason_and_invite_window_for_accept_decline():
    source = inspect.getsource(service.transition_participation)
    version_source = inspect.getsource(service._expected_version)
    assert "lock=True" in source
    assert "expectedVersion" in version_source
    assert 'campaign.status in {"CLOSED", "ARCHIVED"}' in source
    assert 'target in {"ACCEPTED", "DECLINED"}' in source
    assert 'assert_campaign_operation_window(campaign, "INVITE", now=now)' in source
    assert 'target == "REVOKED"' in source
    assert "撤销原因" in source


def test_campaign_enterprise_list_is_sql_paginated():
    source = inspect.getsource(service.list_campaign_enterprises)
    assert ".join(" in source
    assert ".offset(" in source
    assert ".limit(page_size + 1)" in source
    assert "page_size = min(200" in source
