"""E-A01 / A01-4 EnterpriseMember targeted contracts."""
from __future__ import annotations

import inspect

from sqlalchemy import Index, UniqueConstraint

import app.models as models
from app.models.internship_enterprise_portal import InternshipEnterpriseMember
from app.modules.internship.services import internship_enterprise_member_service as service


def _unique_sets():
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in InternshipEnterpriseMember.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_sets():
    return {
        tuple(column.name for column in index.columns)
        for index in InternshipEnterpriseMember.__table__.indexes
        if isinstance(index, Index)
    }


def test_enterprise_member_model_reuses_t_user_and_matches_v3_contract():
    columns = set(InternshipEnterpriseMember.__table__.columns.keys())
    assert InternshipEnterpriseMember.__tablename__ == "t_internship_enterprise_member"
    assert {
        "tenant_id",
        "company_id",
        "user_id",
        "contact_id",
        "member_role",
        "status",
        "is_primary",
        "invited_phone_hash",
        "invite_token_hash",
        "invite_expires_at",
        "invited_at",
        "accepted_at",
        "last_active_at",
        "version",
        "created_at",
        "updated_at",
        "is_deleted",
    } <= columns
    assert not hasattr(models, "EnterpriseUser")


def test_enterprise_member_unique_and_indexes_are_tenant_scoped():
    assert ("tenant_id", "company_id", "user_id") in _unique_sets()
    assert ("tenant_id", "user_id", "status", "is_deleted") in _index_sets()
    assert ("tenant_id", "company_id", "status", "is_deleted") in _index_sets()


def test_member_creation_resolves_existing_user_company_and_optional_contact():
    source = inspect.getsource(service.create_member)
    assert "_get_company(" in source
    assert "_get_user(" in source
    assert 'user.user_type != "ENTERPRISE_MENTOR"' in source
    assert "_get_contact(" in source
    assert "InternshipEnterpriseMember.user_id == user.id" in source
    assert ".with_for_update()" in source


def test_member_resolution_fails_closed_for_user_and_member_status():
    source = inspect.getsource(service.resolve_member_for_user)
    assert 'user.status != "ACTIVE"' in source
    assert 'member.status == "ACTIVE"' in source
    assert "当前账号没有有效企业成员身份" in source
    assert "关联多个企业" in source


def test_member_status_change_is_row_locked_and_version_guarded():
    source = inspect.getsource(service.set_member_status)
    assert "lock=True" in source
    assert "expected_version" in source
    assert 'target not in {"ACTIVE", "DISABLED"}' in source
    assert 'member.status == "ACTIVE" and target == "DISABLED"' in source
