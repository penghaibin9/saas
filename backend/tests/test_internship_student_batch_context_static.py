"""Regression seal for explicit student batch context across the PC/Mini facades."""
from __future__ import annotations

import inspect

from app.api.v1 import mobile_internship_selection
from app.modules.internship.services import internship_student_catalog_facade_service as catalog_svc
from app.modules.internship.services import internship_student_selection_actions_service as action_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc
from app.student_portal import internship_selection_router


def test_explicit_batch_resolution_precedes_historical_group_pinning():
    source = inspect.getsource(selection_svc._resolve_context_in_tx)
    explicit_batch = 'if batch_id not in (None, ""):'
    group_lookup = "group = db.scalar(select(InternshipVolunteerGroup)"

    assert explicit_batch in source
    assert group_lookup in source
    assert source.index(explicit_batch) < source.index(group_lookup)
    assert "InternshipRecord.batch_id == selected_batch_id" in source
    assert "InternshipRecruitmentCampaign.batch_id == selected_batch_id" in source


def test_pc_and_mobile_read_facades_bind_the_same_batch_header():
    for router_module in (internship_selection_router, mobile_internship_selection):
        source = inspect.getsource(router_module)
        assert 'alias="X-Internship-Batch-Id"' in source
        assert "catalog_svc.get_catalog_context(user=user, batch_id=batch_id)" in source
        assert "catalog_svc.list_catalog_positions(user=user, batch_id=batch_id" in source
        assert "selection_svc.get_my_volunteers(\n        user=user, batch_id=batch_id)" in source
        assert "selection_svc.get_my_material_preview(user=user, batch_id=batch_id)" in source
        assert "action_svc.list_my_submissions(user=user, batch_id=batch_id)" in source
        assert "selection_svc.submit_my_saved_volunteers(\n        user=user, body=body or {}, batch_id=batch_id)" in source
        assert "action_svc.withdraw_my_submission(\n        user=user, body=body or {}, batch_id=batch_id)" in source
        assert "action_svc.request_my_unlock(\n        user=user, body=body or {}, batch_id=batch_id)" in source
        assert "action_svc.revoke_my_contact_consent(\n        user=user, body=body or {}, batch_id=batch_id)" in source


def test_all_selection_read_services_forward_explicit_batch_context():
    catalog_source = inspect.getsource(catalog_svc)
    action_source = inspect.getsource(action_svc)
    selection_source = inspect.getsource(selection_svc)

    assert catalog_source.count("student_id=student_id, batch_id=batch_id") >= 4
    assert action_source.count("student_id=student_id, batch_id=batch_id") >= 2
    assert selection_source.count("student_id=student_id, batch_id=batch_id") >= 2
    assert "payload[\"batchId\"] = selected_batch_id" in action_source
    assert "payload[\"batchId\"] = selected_batch_id" in selection_source
