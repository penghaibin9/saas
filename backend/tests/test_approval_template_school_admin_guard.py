import pytest

from app.core.exceptions import AppException
from app.services import approval_template_service as service


def test_only_school_admin_may_maintain_templates(monkeypatch):
    monkeypatch.setattr(service, "has_permission", lambda *_: True)
    with pytest.raises(AppException) as exc:
        service._require_manage({"currentRoleCode": "ACADEMIC_ADMIN"})
    assert exc.value.code == "NO_PERMISSION"

    service._require_manage({"currentRoleCode": "SCHOOL_ADMIN"})


def test_draft_origin_survives_a_draft_save_snapshot():
    definition = type("Definition", (), {
        "policy_snapshot_json": {"draftOfWorkflowCode": "CS_LEAVE_007", "baseDefinitionId": "9"},
        "definition_version": "2026.2", "workflow_name": "请假", "source_biz_type": "CsLeave", "status": "DRAFT",
    })()
    node = type("Node", (), {"node_code": "N1", "node_name": "审核", "approver_role_code": "SCHOOL_ADMIN", "timeout_hours": 48, "sequence_no": 1, "status": "ACTIVE"})()
    service._store_snapshot(definition, [node])
    assert definition.policy_snapshot_json["draftOfWorkflowCode"] == "CS_LEAVE_007"
    assert definition.policy_snapshot_json["baseDefinitionId"] == "9"


def test_next_definition_version_increments_once_per_new_draft():
    assert service._next_definition_version("2026.1") == "2026.2"
    assert service._next_definition_version("1") == "2"
