"""Regression seals for PR #132 Student Catalog/Profile and enterprise position search review."""
from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from app.api.v1 import mobile_internship_selection as mobile_facade
from app.modules.internship.routers import internship_enterprise_portal as enterprise_router
from app.modules.internship.services import internship_enterprise_position_search_service as enterprise_search
from app.modules.internship.services import internship_student_catalog_facade_service as catalog_svc
from app.modules.internship.services import internship_student_position_eligibility_service as eligibility_svc
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


def test_catalog_reuses_canonical_eligibility_and_never_silently_drops_paged_rows():
    source = inspect.getsource(catalog_svc._eligible_rows)
    assert "eligibility_svc.evaluate_position_for_student_in_tx(" in source
    assert "except AppException:" in source
    assert "if strict:" in source
    assert "raise" in source
    assert "continue" in source
    assert source.index("evaluate_position_for_student_in_tx") < source.index("result.append")
    list_source = inspect.getsource(catalog_svc.list_catalog_positions)
    assert "_eligible_rows(" in list_source
    assert "strict=True" in list_source
    detail = inspect.getsource(catalog_svc.get_catalog_position)
    assert "eligibility_svc.evaluate_position_for_student_in_tx(" in detail


def test_catalog_major_match_filter_and_company_name_filter_are_real_server_side_filters():
    assert catalog_svc._major_hit("软件技术", "软件技术/计算机") is True
    assert catalog_svc._major_hit("护理", "软件技术") is False
    assert catalog_svc._major_hit("护理", "") is True
    assert catalog_svc._true_filter(True) is True
    assert catalog_svc._true_filter("true") is True
    assert catalog_svc._true_filter("false") is False
    assert catalog_svc._escape_like(r"跃科%_A\B") == r"跃科\%\_A\\B"

    list_source = inspect.getsource(catalog_svc.list_catalog_positions)
    assert 'only_major_matched=_true_filter(params.get("majorMatched"))' in list_source
    major_sql = inspect.getsource(eligibility_svc._major_sql_predicate)
    assert "func.locate(major, requirement) > 0" in major_sql
    assert "func.locate(requirement, major) > 0" in major_sql
    assert "func.length(func.trim(requirement)) == 0" in major_sql
    row_source = inspect.getsource(catalog_svc._public_row)
    assert '"POSSIBLE_MISMATCH"' in row_source
    assert '"MATCHED" if major_matched' in row_source

    filter_source = inspect.getsource(catalog_svc._filtered)
    assert "company_filter.isdigit()" in filter_source
    assert "InternshipPosition.company_id == _as_id(company_filter)" in filter_source
    assert 'EmpCompany.name.like(pattern, escape="\\\\")' in filter_source
    for facade in (portal_facade, mobile_facade):
        route_source = inspect.getsource(facade.list_catalog_positions)
        assert "companyId: str | None" in route_source
        assert "majorMatched: bool | None" in route_source
        assert '"companyId": companyId' in route_source
        assert '"majorMatched": majorMatched' in route_source


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


def test_student_catalog_applies_canonical_sql_predicates_before_count_and_page_boundaries():
    source = inspect.getsource(catalog_svc.list_catalog_positions)
    eligibility_at = source.index("apply_catalog_query_eligibility_filters_in_tx(")
    count_at = source.index("select(func.count()).select_from(q.order_by(None).subquery())")
    page_at = source.index("page_q = q.offset((page - 1) * page_size).limit(page_size)")
    eval_at = source.index("_eligible_rows(")
    assert eligibility_at < count_at < page_at < eval_at
    assert "strict=True" in source
    assert "rows[start:start + page_size]" not in source

    sql_guard = inspect.getsource(eligibility_svc.apply_catalog_query_eligibility_filters_in_tx)
    for required in (
        "InternshipBatchParticipant",
        "func.length(func.trim(InternshipPosition.work_content)) > 0",
        "InternshipPosition.daily_hours <= max_daily",
        "InternshipPosition.weekly_hours <= max_weekly",
        "InternshipPosition.hazardous_flag.is_(False)",
        "_latest_approved_inspection_predicates",
        "_major_sql_predicate(major_name)",
    ):
        assert required in sql_guard
    assert 'rights_cfg.get("requireEnterpriseAccess", True)' in sql_guard
    assert 'only_major_matched' in sql_guard


def test_catalog_context_stats_use_same_sql_projected_eligibility_set():
    stats = inspect.getsource(catalog_svc._candidate_stats_in_tx)
    assert "apply_catalog_query_eligibility_filters_in_tx(" in stats
    assert "select(func.count()).select_from(candidate)" in stats
    assert "func.count(func.distinct(candidate.c.company_id))" in stats
    context = inspect.getsource(catalog_svc.get_catalog_context)
    assert "_candidate_stats_in_tx(" in context
    assert "record=record" in context
    assert "_eligible_rows(" not in context
