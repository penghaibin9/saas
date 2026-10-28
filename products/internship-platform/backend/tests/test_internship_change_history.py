"""Read projection only: approval history must not be reconstructed from today's record."""
from copy import deepcopy
from types import SimpleNamespace as Obj

import pytest

from app.modules.internship.services import internship_change_service as service


def sample():
    change = Obj(id=1, tenant_id=11, internship_id=18, status="APPROVED",
                 record_version_snapshot=1, change_type="CHANGE_ENTERPRISE", reason="变更原因",
                 target_enterprise_id=7, target_position_id=6, target_enterprise_name="乙企业",
                 target_position_name="乙岗位", review_comment="同意", reviewed_by_name="合成审核人",
                 reviewed_at=None, version=2, created_at=None)
    record = Obj(enterprise_name="丙企业", position_name="丙岗位", status="ONBOARD",
                 version=5, eligibility_status="QUALIFIED")
    before = dict(enterpriseId="9007199254740993006", positionId="5", enterpriseName="甲企业",
                  positionName="甲岗位", recordVersion=1)
    after = dict(enterpriseId="7", positionId="6", enterpriseName="乙企业",
                 positionName="乙岗位", recordVersion=2)
    audit = Obj(id=229, tenant_id=11, target_id=1, target_type="CHANGE_REQ", action="APPROVE",
                detail_json={"atomic": True, "recordBefore": before, "recordAfter": after})
    return change, record, audit


def test_approved_row_keeps_original_route_separate_from_later_current_record():
    change, record, audit = sample()
    history = service._approved_history(change, [audit])
    row = service._row(change, record, None, history)
    assert row["currentEnterprise"] == "丙企业"
    assert row["reviewedBy"] == "合成审核人" and row["reviewedAt"] == ""
    assert row["approvedHistory"]["before"]["enterpriseName"] == "甲企业"
    assert row["approvedHistory"]["before"]["enterpriseId"] == "9007199254740993006"
    assert row["approvedHistory"]["after"]["enterpriseName"] == "乙企业"
    assert row["approvedHistory"]["applicationBasisMatched"] is True
    assert audit.detail_json["recordBefore"]["enterpriseName"] == "甲企业"


@pytest.mark.parametrize("field,value", [("tenant_id", 12), ("target_id", 2),
    ("target_type", "RECORD"), ("action", "REJECT")])
def test_unrelated_audit_cannot_supply_approved_history(field, value):
    change, record, audit = sample()
    setattr(audit, field, value)
    assert service._approved_history(change, [audit]) is None
    assert service._row(change, record, None)["approvedHistory"] is None


@pytest.mark.parametrize("detail", [None, {}, {"atomic": True},
    {"atomic": True, "recordBefore": "bad", "recordAfter": {}}])
def test_missing_or_malformed_history_stays_unrecorded(detail):
    change, _, audit = sample()
    audit.detail_json = detail
    assert service._approved_history(change, [audit]) is None


def test_approval_before_is_not_claimed_as_application_basis_without_version_match():
    change, _, audit = sample()
    change.record_version_snapshot = 3
    assert service._approved_history(change, [audit])["applicationBasisMatched"] is False
    change.status = "PENDING"
    assert service._approved_history(change, [audit]) is None


def test_history_requires_complete_snapshots_and_one_atomic_version_transition():
    change, _, original = sample()
    for altered in [{"recordVersion": 1}, {"recordVersion": "bad"},
                    {"enterpriseId": {}}, {"enterpriseName": None}]:
        audit = deepcopy(original)
        audit.detail_json["recordAfter"].update(altered)
        assert service._approved_history(change, [audit]) is None
    audit = deepcopy(original)
    del audit.detail_json["recordBefore"]["positionName"]
    assert service._approved_history(change, [audit]) is None


def test_first_valid_zero_version_transition_keeps_complete_approval_history():
    change, _, audit = sample()
    change.record_version_snapshot = 0
    audit.detail_json['recordBefore']['recordVersion'] = 0
    audit.detail_json['recordAfter']['recordVersion'] = 1
    history = service._approved_history(change, [audit])
    assert history['before']['recordVersion'] == 0 and history['applicationBasisMatched'] is True
    audit.detail_json['recordBefore']['recordVersion'] = -1
    assert service._approved_history(change, [audit]) is None
