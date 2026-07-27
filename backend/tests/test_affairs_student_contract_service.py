from app.services.affairs_student_contract_service import (
    _default_action,
    _merge_materials,
    _next_action,
    _status_group,
)


def test_returned_application_is_grouped_for_student_revision():
    assert _status_group("DRAFT", ["EDIT_RETURNED", "RESUBMIT"]) == "rejected"
    assert _status_group("RETURNED", ["RESUBMIT"]) == "rejected"
    assert _status_group("COUNSELOR_REVIEW", []) == "processing"
    assert _status_group("APPROVED", []) == "done"


def test_next_action_prefers_server_allowed_actions():
    assert _next_action("RETURNED", ["EDIT_RETURNED", "RESUBMIT"])["key"] == "EDIT_RETURNED"
    assert _next_action("PUBLICITY", ["SUBMIT_OBJECTION"])["label"] == "提交异议"
    waiting = _next_action("COUNSELOR_REVIEW", [], "王老师")
    assert waiting == {"key": "WAIT", "label": "等待王老师处理", "actor": "STAFF"}


def test_message_default_actions_are_student_routes_with_record_ids():
    key, params = _default_action("aid", 17)
    assert key == "AFFAIRS_AID"
    assert params == {"bizType": "AID", "recordId": "17"}
    key, params = _default_action("risk", 18)
    assert key is None
    assert params == {}


def test_material_contract_keeps_current_and_history_separate():
    merged = _merge_materials(
        {"current": [{"attachmentId": "1"}], "history": [], "supplementStatus": "NOT_PENDING"},
        {"current": [], "history": [{"attachmentId": "2"}],
         "supplementStatus": "PENDING_STUDENT_EDIT"},
    )
    assert merged["currentCount"] == 1
    assert merged["historyCount"] == 1
    assert merged["missingItemsKnown"] is False
    assert merged["supplementStatus"] == "PENDING_STUDENT_EDIT"
