"""A03 pre-authority P0: strict SUBMIT evidence with sealed A01 DRAFT compatibility."""
from __future__ import annotations

import inspect
from pathlib import Path

from fastapi.routing import APIRoute

from app.api.v1 import mobile_internship_selection as mobile_facade
from app.modules.internship.routers import internship_student_selection as registration_shim
from app.modules.internship.services import internship_student_selection_service as selection_svc
from app.modules.internship.services import internship_volunteer_service as volunteer_svc
from app.student_portal import internship_selection_router as portal_facade


def _route_contract(router):
    return {
        (route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"}))
        for route in router.routes
        if isinstance(route, APIRoute)
    }


def test_sealed_a01_draft_direct_call_signature_remains_unchanged_and_v3_free():
    signature = inspect.signature(volunteer_svc.save_or_submit_in_tx)
    assert "expected_profile_version" not in signature.parameters
    assert "preview_hash" not in signature.parameters
    signature.bind(
        object(), tenant_id=1, student_id=2, record_id=3, campaign_id=4,
        volunteers=[{"volunteerNo": 1, "positionId": 5}],
        expected_record_version=0, expected_group_version=0,
        expected_application_versions={}, submit=False,
    )
    draft = inspect.getsource(selection_svc.save_my_draft)
    assert "submit=False" in draft
    assert "expectedProfileVersion" not in draft
    assert "confirmMaterialPreviewHash" not in draft


def test_submit_contract_requires_profile_version_and_preview_hash_before_transaction_mutation():
    source = inspect.getsource(selection_svc.submit_my_saved_volunteers)
    assert 'payload.get("expectedProfileVersion")' in source
    assert 'payload.get("confirmMaterialPreviewHash")' in source
    assert "提交志愿必须提供 expectedProfileVersion + previewHash" in source
    gate_at = source.index('preview["profileVersion"] != expected_profile')
    delegate_at = source.index("volunteer_svc.save_or_submit_in_tx(")
    assert gate_at < delegate_at


def test_submit_lock_order_is_record_group_applications_then_profile():
    source = inspect.getsource(selection_svc.submit_my_saved_volunteers)
    record_at = source.index("InternshipRecord.id")
    group_at = source.index("InternshipVolunteerGroup.tenant_id")
    apps_at = source.index("InternshipApplication.tenant_id")
    profile_at = source.index("StudentInternshipProfile.tenant_id")
    assert record_at < group_at < apps_at < profile_at
    assert source.count(".with_for_update()") >= 4


def test_preview_hash_freezes_material_projection_not_submit_time_contact_choices():
    source = inspect.getsource(selection_svc._material_preview_in_tx)
    assert '"profileSnapshot": profile_snapshot' in source
    assert '"schoolFactSnapshot": school_facts' in source
    assert '"materialPolicySnapshot"' in source
    assert 'f"sha256:{material_svc._snapshot_hash(payload)}"' in source
    assert "contactSharingPolicy" not in source
    assert "consentAt" not in source


def test_consent_and_contact_are_canonical_and_server_timestamped_on_submit():
    source = inspect.getsource(selection_svc.submit_my_saved_volunteers)
    assert 'payload.get("consentPolicyVersion")' in source
    assert "_contact_policy(payload)" in source
    assert "_assert_contact_mode_allowed" in source
    assert "consent_at=datetime.utcnow()" in source
    contact = inspect.getsource(selection_svc._contact_policy)
    assert "normalize_contact_sharing_policy" in contact
    assert '"MASKED_ONLY"' in contact


def test_final_submit_rehydrates_persisted_draft_and_preserves_all_row_versions_for_cas():
    source = inspect.getsource(selection_svc.submit_my_saved_volunteers)
    assert 'rows = [row for row in all_rows if row.status == "DRAFT"]' in source
    assert "expected_apps = {int(row.volunteer_no): int(row.version or 0) for row in all_rows}" in source
    assert "run_with_bounded_mysql_retry" in source
    assert "volunteer_svc.save_or_submit_in_tx(" in source


def test_a03_pc_and_mobile_facades_expose_the_same_p0_authority_paths():
    portal = _route_contract(portal_facade.router)
    mobile = _route_contract(mobile_facade.router)
    suffixes = {
        ("/profile", frozenset({"GET"})),
        ("/profile", frozenset({"PUT"})),
        ("/context/volunteers", frozenset({"GET"})),
        ("/context/volunteers", frozenset({"PUT"})),
        ("/context/volunteers/material-preview", frozenset({"GET"})),
        ("/context/volunteers/submit", frozenset({"POST"})),
    }
    assert {(path.removeprefix("/portal/internship"), methods) for path, methods in portal} == suffixes
    assert {(path.removeprefix("/mobile/internship"), methods) for path, methods in mobile} == suffixes


def test_student_facades_live_on_canonical_surfaces_and_do_not_evade_staff_route_inventory():
    portal_path = Path(inspect.getsourcefile(portal_facade) or "").as_posix()
    mobile_path = Path(inspect.getsourcefile(mobile_facade) or "").as_posix()
    assert "/app/student_portal/" in portal_path
    assert "/app/api/v1/" in mobile_path
    shim_source = inspect.getsource(registration_shim)
    assert "@" not in shim_source
    assert "mobile_internship_selection" in shim_source
    assert "internship_selection_router" in shim_source
    assert "enforce_student_portal_module_access" in inspect.getsource(portal_facade)
    assert 'require_module("internship")' in inspect.getsource(mobile_facade)


def test_facades_are_thin_and_reuse_profile_plus_selection_services():
    for facade in (portal_facade, mobile_facade):
        source = inspect.getsource(facade)
        assert "profile_svc.get_my_profile" in source
        assert "profile_svc.save_my_profile" in source
        assert "selection_svc.save_my_draft" in source
        assert "selection_svc.submit_my_saved_volunteers" in source
        assert "StudentVolunteer" not in source
