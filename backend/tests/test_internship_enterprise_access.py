"""E-A01 / A01-5 EnterpriseAccessGrant targeted contracts."""
from __future__ import annotations

from datetime import datetime, timedelta
import inspect

from sqlalchemy import Index, UniqueConstraint

from app.models.internship_enterprise_portal import InternshipEnterpriseAccessGrant
from app.modules.internship.services import internship_enterprise_access_service as service


def _unique_sets():
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in InternshipEnterpriseAccessGrant.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_sets():
    return {
        tuple(column.name for column in index.columns)
        for index in InternshipEnterpriseAccessGrant.__table__.indexes
        if isinstance(index, Index)
    }


def test_access_grant_model_matches_v3_contract():
    columns = set(InternshipEnterpriseAccessGrant.__table__.columns.keys())
    assert InternshipEnterpriseAccessGrant.__tablename__ == "t_internship_enterprise_access_grant"
    assert {
        "tenant_id",
        "member_id",
        "company_id",
        "grant_type",
        "campaign_id",
        "batch_id",
        "valid_from",
        "valid_until",
        "status",
        "revoked_at",
        "revoked_by_user_id",
        "revoke_reason",
        "version",
        "created_at",
        "updated_at",
        "is_deleted",
    } <= columns


def test_access_grant_unique_and_indexes_match_v3():
    assert (
        "tenant_id",
        "member_id",
        "grant_type",
        "campaign_id",
        "batch_id",
    ) in _unique_sets()
    assert ("tenant_id", "member_id", "status", "valid_until") in _index_sets()
    assert ("tenant_id", "company_id", "status", "valid_until") in _index_sets()


def test_effective_status_fails_closed_on_time_and_revocation():
    now = datetime(2026, 9, 10, 8, 0, 0)
    grant = InternshipEnterpriseAccessGrant(
        tenant_id=1,
        member_id=10,
        company_id=20,
        grant_type="RECRUITMENT",
        campaign_id=30,
        batch_id=40,
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=1),
        status="ACTIVE",
    )
    assert service.effective_grant_status(grant, now=now) == "ACTIVE"
    grant.valid_from = now + timedelta(minutes=1)
    assert service.effective_grant_status(grant, now=now) == "NOT_STARTED"
    grant.valid_from = now - timedelta(hours=2)
    grant.valid_until = now - timedelta(minutes=1)
    assert service.effective_grant_status(grant, now=now) == "EXPIRED"
    grant.status = "REVOKED"
    assert service.effective_grant_status(grant, now=now) == "REVOKED"


def test_issue_path_locks_member_first_and_serializes_nullable_scope_duplicates():
    source = inspect.getsource(service.issue_grant_in_tx)
    assert "_get_member(db, member_id, tenant_id=tenant_id, lock=True)" in source
    assert "nullable campaign/batch" in source
    assert "_scope_predicates(" in source
    assert ".with_for_update()" in source
    assert "不可静默覆盖或复活" in source


def test_recruitment_grant_requires_accepted_campaign_participation_and_access_deadline():
    source = inspect.getsource(service._validate_scope_in_tx)
    assert 'grant_type == "RECRUITMENT"' in source
    assert 'campaign.status in {"CLOSED", "ARCHIVED"}' in source
    assert "campaign.enterprise_access_end_at is None" in source
    assert "valid_until > campaign.enterprise_access_end_at" in source
    assert 'InternshipCampaignEnterprise.status == "ACCEPTED"' in source
    assert "member.company_id" in source


def test_active_grant_resolution_checks_member_company_status_and_effective_window():
    source = inspect.getsource(service.resolve_active_grant_in_tx)
    assert 'member.status != "ACTIVE"' in source
    assert "InternshipEnterpriseAccessGrant.company_id == member.company_id" in source
    assert "effective_grant_status(grant, now=now) != \"ACTIVE\"" in source
    assert "已撤销、未生效或已过期" in source


def test_revoke_is_row_locked_version_guarded_and_reasoned():
    source = inspect.getsource(service.revoke_grant)
    assert "lock=True" in source
    assert "expected_version" in source
    assert "撤销授权必须填写原因" in source
    assert 'grant.status = "REVOKED"' in source
