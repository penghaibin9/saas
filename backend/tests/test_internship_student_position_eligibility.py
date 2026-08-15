from __future__ import annotations

import inspect

from app.modules.internship.services import internship_student_application_context_service as legacy_context
from app.modules.internship.services import internship_student_position_eligibility_service as eligibility


def test_campaign_position_eligibility_is_fail_closed_on_student_company_and_window_state():
    source = inspect.getsource(eligibility.evaluate_position_for_student_in_tx)
    window = inspect.getsource(eligibility.assert_student_selection_window)
    assert 'assert_campaign_operation_window(campaign, "STUDENT_SELECT"' in window
    assert 'record.status not in {"PREPARING", "READY"}' in source
    assert 'record.eligibility_status != "QUALIFIED"' in source
    assert 'company.status or ""' in source and '!= "ACTIVE"' in source
    assert 'company.qualification_status != "PASSED"' in source
    assert 'company.coop_status != "ACTIVE"' in source
    assert "company.blacklist" in source
    assert "company.access_valid_until" in source
    assert 'InternshipCampaignEnterprise.status == "ACCEPTED"' in source
    assert "evaluate_position_publishability" in source


def test_legacy_single_application_write_cannot_bypass_atomic_campaign_volunteers():
    guard = inspect.getsource(legacy_context._reject_campaign_position)
    save_source = inspect.getsource(legacy_context.save)
    submit_source = inspect.getsource(legacy_context.submit)
    withdraw_source = inspect.getsource(legacy_context.withdraw)
    assert 'getattr(position, "campaign_id", None)' in guard
    assert "三志愿原子接口" in guard
    assert "_reject_campaign_position(position)" in save_source
    assert "_reject_campaign_position(position)" in submit_source
    assert "_reject_campaign_position(position)" in withdraw_source
