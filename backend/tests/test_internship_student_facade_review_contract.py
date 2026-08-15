"""Regression seals for PR #132 Student Catalog/Profile and enterprise position search review."""
from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from app.api.v1 import mobile_internship_selection as mobile_facade
from app.modules.internship.routers import internship_enterprise_portal as enterprise_router
from app.modules.internship.services import internship_enterprise_position_search_service as enterprise_search
from app.modules.internship.services import internship_student_catalog_facade_service as catalog_svc
from app.modules.internship.services import internship_student_profile_facade_service as profile_facade_svc
from app.student_portal import internship_selection_router as portal_facade


def _paths(router):
    return {
        (route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"}))
        for route in router.routes
        if isinstance(route, APIRoute)
    }


def test_pc_and_mobile_register_catalog_and_profile_facades_instead_of_404():
    for router, prefix in (
        (portal_facade.router, "/portal/internship"),
        (mobile_facade.router, "/mobile/internship"),
    ):
        paths = _paths(router)
        for suffix, method in (
            ("/catalog/context", "GET"),
            ("/catalog/positions", "GET"),
            ("/catalog/positions/{position_id}", "GET"),
            ("/catalog/companies/{company_id}", "GET"),
            ("/profile/completeness", "GET"),
            ("/profile/items", "GET"),
            ("/profile/items", "POST"),
            ("/profile/items/{item_id}", "PUT"),
            ("/profile/items/{item_id}", "DELETE"),
            ("/profile/preview", "GET"),
            ("/profile/pdf-preview", "POST"),
        ):
            assert (f"{prefix}{suffix}", frozenset({method})) in paths


def test_catalog_is_fail_closed_to_current_tenant_campaign_published_and_accepted_enterprises():
    source = inspect.getsource(catalog_svc._base_query)
    assert "InternshipPosition.tenant_id == tenant_id" in source
    assert "InternshipPosition.batch_id == campaign.batch_id" in source
    assert "InternshipPosition.campaign_id == campaign.id" in source
    assert 'InternshipPosition.status == "PUBLISHED"' in source
    assert "InternshipPosition.allocated_count < InternshipPosition.headcount" in source
    assert "EmpCompany.tenant_id == tenant_id" in source
    assert 'EmpCompany.qualification_status == "PASSED"' in source
    assert "EmpCompany.blacklist.is_(False)" in source
    assert 'InternshipCampaignEnterprise.status == "ACCEPTED"' in source


def test_catalog_reuses_canonical_eligibility_and_never_returns_failed_positions():
    source = inspect.getsource(catalog_svc._eligible_rows)
    assert "eligibility_svc.evaluate_position_for_student_in_tx(" in source
    assert "except AppException:" in source
    assert "continue" in source
    assert source.index("evaluate_position_for_student_in_tx") < source.index("result.append")
    list_source = inspect.getsource(catalog_svc.list_catalog_positions)
    assert "_eligible_rows(" in list_source
    detail = inspect.getsource(catalog_svc.get_catalog_position)
    assert "eligibility_svc.evaluate_position_for_student_in_tx(" in detail


def test_profile_mutations_delegate_existing_profile_authorities_and_pdf_is_private_file_center_delivery():
    assert "profile_svc.add_my_item" in inspect.getsource(profile_facade_svc.add_profile_item)
    assert "item_svc.update_my_item" in inspect.getsource(profile_facade_svc.update_profile_item)
    assert "item_svc.delete_my_item" in inspect.getsource(profile_facade_svc.delete_profile_item)
    pdf = inspect.getsource(profile_facade_svc.create_profile_pdf_preview)
    assert 'payload.get("materialPreviewHash")' in pdf
    assert "expected_hash != str(preview.get(\"previewHash\") or \"\")" in pdf
    assert "file_service.store_bytes(" in pdf
    assert '"INTERNSHIP"' in pdf
    assert 'visibility="PRIVATE"' in pdf
    assert "object_key" not in pdf
    assert "file_key" not in pdf
    for facade in (portal_facade, mobile_facade):
        route_source = inspect.getsource(facade.create_profile_pdf_preview)
        assert "file_contract.url_contract" in route_source
        assert "object_key" not in route_source
        assert "file_key" not in route_source


def test_enterprise_position_keyword_is_server_side_literal_filter_before_count_and_paging():
    route = inspect.getsource(enterprise_router.enterprise_positions)
    assert "keyword: str | None" in route
    assert "position_search_svc.list_positions_in_tx" in route
    assert "keyword=keyword" in route
    assert enterprise_search._escape_like(r"100%_A\B") == r"100\%\_A\\B"
    source = inspect.getsource(enterprise_search.list_positions_in_tx)
    assert "position_svc._position_query(context)" in source
    assert 'InternshipPosition.title.like(pattern, escape="\\\\")' in source
    assert "select(func.count()).select_from(q.subquery())" in source
    assert source.index("if text:") < source.index("total =") < source.index(".offset(")
    assert "position_svc._position_row(row)" in source
