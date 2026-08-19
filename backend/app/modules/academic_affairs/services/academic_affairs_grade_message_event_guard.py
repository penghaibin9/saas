"""Register Academic C grade-entry reminder events on the shared message outbox.

C owns only the event contracts. Delivery, deduplication, retries and
UnifiedMessage materialization remain owned by ``message_event_outbox_service``.
Manual reminder and automatic deadline/overdue scenes use distinct event codes so
operations evidence never conflates a human催录 with scheduled policy execution.
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
        "GRADE.ENTRY_DEADLINE_REMINDER": {
            "source_module": "academic-affairs",
            "category": "REMINDER",
            "priority": "IMPORTANT",
            "message_type": "GRADE_ENTRY_DEADLINE_REMINDER",
            "title": "成绩录入截止提醒",
            "require_ack": False,
        },
        "GRADE.ENTRY_OVERDUE_DIGEST": {
            "source_module": "academic-affairs",
            "category": "REMINDER",
            "priority": "IMPORTANT",
            "message_type": "GRADE_ENTRY_OVERDUE_DIGEST",
            "title": "成绩录入逾期清单",
            "require_ack": False,
        },
    })
    _INSTALLED = True
