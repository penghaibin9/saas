from __future__ import annotations


def test_all_unified_student_affairs_appeal_result_events_are_registered():
    # Importing the canonical router installs the approved student-affairs message guards
    # exactly as production startup does.
    import app.api.v1.router  # noqa: F401
    from app.services import affairs_appeal_todo_service as appeal
    from app.services import message_event_outbox_service as outbox

    expected = {f"{spec['biz_type']}.RESULT" for spec in appeal._SPECS.values()}

    assert expected == {
        "AID_OBJECTION.RESULT",
        "FUNDING_APPEAL.RESULT",
        "DISCIPLINE_APPEAL.RESULT",
        "SECOND_CLASS_APPEAL.RESULT",
    }
    assert expected.issubset(outbox._EVENT_TEMPLATES)
    for code in expected:
        template = outbox._EVENT_TEMPLATES[code]
        assert template["source_module"] == "student-affairs"
        assert template["message_type"] == "WORKFLOW_RESULT"
        assert template["title"]


def test_appeal_result_event_install_is_idempotent():
    from app.services import affairs_appeal_message_event_guard as guard
    from app.services import message_event_outbox_service as outbox

    guard.install()
    before = {code: dict(outbox._EVENT_TEMPLATES[code]) for code in (
        "AID_OBJECTION.RESULT",
        "FUNDING_APPEAL.RESULT",
        "SECOND_CLASS_APPEAL.RESULT",
    )}
    guard.install()
    after = {code: dict(outbox._EVENT_TEMPLATES[code]) for code in before}

    assert after == before
