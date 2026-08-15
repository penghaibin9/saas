from __future__ import annotations

import inspect

from app.models.internship_placement_snapshot import InternshipPlacementSnapshot
from app.modules.internship.services import internship_assignment_snapshot_authority as authority
from app.modules.internship.services import internship_placement_snapshot_service as svc


def test_snapshot_is_append_only_and_complete():
    columns=set(InternshipPlacementSnapshot.__table__.columns.keys())
    assert not {"updated_at","updated_by","is_deleted","version"} & columns
    assert {"record_id","placement_seq","application_id","enterprise_decision_id","campaign_id","batch_id","company_id","position_id","snapshot_json","snapshot_sha256","position_version","captured_at"} <= columns


def test_sha_is_stable_canonical_json():
    a={"b":2,"a":{"x":[1,2]}}
    b={"a":{"x":[1,2]},"b":2}
    assert svc.snapshot_sha256(a)==svc.snapshot_sha256(b)
    assert len(svc.snapshot_sha256(a))==64


def test_wrapper_preserves_existing_assignment_authority_and_same_transaction_snapshot():
    source=inspect.getsource(authority._wrapped_assign_position_in_tx)
    assert "result = _ORIGINAL(" in source
    assert "capture_placement_snapshot_in_tx(" in source
    assert "db.commit" not in source
    assert 'decision.effect_status = "CONSUMED"' in source
    assert "teacher_mark_approved_in_tx" in source


def test_enterprise_confirm_required_is_fail_closed():
    source=inspect.getsource(authority._source_for_campaign_in_tx)
    assert "campaign.enterprise_confirm_required" in source
    assert 'group.status == "LOCKED"' in source
    assert "group.locked_application_id == application.id" in source
    assert 'decision.decision_status == "ACCEPT_INTENT"' in source
    assert 'decision.effect_status == "ACTIVE"' in source
    assert "企业尚未确认拟接收" in source
