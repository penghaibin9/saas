"""Register Academic C grade-entry reminder on the shared message outbox.

This follows the repository's established guard-install pattern: C owns only the
new event contract while delivery, deduplication, retries and UnifiedMessage
materialization remain owned by ``message_event_outbox_service``.
"""
from __future__ import annotations

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import message_event_outbox_service as outbox

    outbox._EVENT_TEMPLATES.update({
        "GRADE.ENTRY_REMINDED": {
            "source_module": "academic-affairs",
            "category": "REMINDER",
            "priority": "IMPORTANT",
            "message_type": "GRADE_ENTRY_REMIND",
            "title": "成绩录入提醒",
            "require_ack": False,
        },
    })
    _INSTALLED = True
