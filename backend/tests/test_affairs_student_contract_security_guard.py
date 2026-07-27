from pathlib import Path
from types import SimpleNamespace

from app.services.affairs_student_contract_security_guard import (
    _canonical_message_action,
    _safe_status_token,
    _secure_message_producers,
)


SOURCE = (Path(__file__).parents[1] / "app/services/affairs_student_contract_security_guard.py").read_text(
    encoding="utf-8"
)


class _ContractStub:
    _ACTION_KEY_BY_BIZ = {"LEAVE": "AFFAIRS_LEAVE", "AID": "AFFAIRS_AID"}

    @staticmethod
    def _biz(value):
        return str(value or "").strip().upper().replace("-", "_")


def test_internal_audit_payload_is_not_a_student_status_token():
    assert _safe_status_token("COUNSELOR_REVIEW") == "COUNSELOR_REVIEW"
    assert _safe_status_token("reason=家庭经济说明") == ""
    assert _safe_status_token("内部意见：建议重点关注") == ""


def test_student_material_metadata_is_owner_scoped():
    assert "AffairsAttachment.created_by.in_(owner_ids)" in SOURCE
    assert '"visibility": "OWNER_ONLY"' in SOURCE
    assert "无法确认本人时 fail-closed" in SOURCE


def test_discipline_id_is_stable_and_dorm_has_no_fake_resubmit():
    assert 'item["applicationId"] = f"discipline-{case_id}"' in SOURCE
    assert '"SUBMIT_APPEAL" not in (item.get("allowedActions") or [])' in SOURCE
    assert 'item["allowedActions"] = []' in SOURCE
    assert "调宿退回没有真实编辑重提接口时不返回假动作" in SOURCE


def test_legacy_message_action_is_canonicalized_without_losing_parameters():
    item = {
        "actionKey": "student.leave.detail",
        "bizType": "LEAVE",
        "recordId": "12",
        "actionParams": {"leaveId": 12},
    }
    _canonical_message_action(item, _ContractStub)
    assert item["actionKey"] == "AFFAIRS_LEAVE"
    assert item["actionParams"] == {
        "leaveId": 12,
        "bizType": "LEAVE",
        "recordId": "12",
    }


def test_existing_canonical_message_action_is_not_rewritten():
    item = {
        "actionKey": "AFFAIRS_AID",
        "bizType": "AID",
        "recordId": "9",
        "actionParams": {"recordId": "custom"},
    }
    _canonical_message_action(item, _ContractStub)
    assert item["actionKey"] == "AFFAIRS_AID"
    assert item["actionParams"] == {"recordId": "custom"}


def test_outbox_write_canonicalizes_leave_and_appeal_actions():
    calls = []

    def original(db, **kwargs):
        calls.append(kwargs)
        return kwargs

    outbox = SimpleNamespace(emit_message_event=original)
    _secure_message_producers(outbox)

    outbox.emit_message_event(
        object(),
        event_code="LEAVE.RETURNED",
        source_module="student-affairs",
        source_biz_type="leave_request",
        source_biz_id=31,
        recipient_refs=[{"studentId": 8}],
        action_key="student.leave.detail",
        action_params={"leaveId": 31},
    )
    assert calls[-1]["action_key"] == "AFFAIRS_LEAVE"
    assert calls[-1]["action_params"] == {
        "leaveId": 31,
        "bizType": "LEAVE_REQUEST",
        "recordId": "31",
    }

    outbox.emit_message_event(
        object(),
        event_code="AID.NOTICE",
        source_module="student-affairs",
        source_biz_type="aid_objection",
        source_biz_id=32,
        recipient_refs=[{"studentId": 8}],
    )
    assert calls[-1]["action_key"] == "AFFAIRS_AID"
    assert calls[-1]["action_params"] == {
        "bizType": "AID_OBJECTION",
        "recordId": "32",
    }


def test_outbox_does_not_create_sensitive_risk_deep_link():
    calls = []

    def original(db, **kwargs):
        calls.append(kwargs)
        return kwargs

    outbox = SimpleNamespace(emit_message_event=original)
    _secure_message_producers(outbox)
    outbox.emit_message_event(
        object(),
        event_code="RISK.STATUS",
        source_module="student-affairs",
        source_biz_type="risk",
        source_biz_id=99,
        recipient_refs=[{"studentId": 8}],
    )
    assert calls[-1].get("action_key") is None
    assert calls[-1].get("action_params") is None
