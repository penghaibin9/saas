"""W7.6 graduation review message event contracts.

Only event metadata is registered here. Delivery, deduplication, retries and
UnifiedMessage materialization remain owned by ``message_event_outbox_service``.
"""
from __future__ import annotations

_INSTALLED = False
EVENT_REVIEW_REJECTED = "GRADUATION_DESIGN.REVIEW_REJECTED"


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import message_event_outbox_service as outbox

    outbox._EVENT_TEMPLATES.update({
        EVENT_REVIEW_REJECTED: {
            "source_module": "graduation",
            "category": "BUSINESS",
            "priority": "IMPORTANT",
            "message_type": "GRADUATION_REVIEW_REJECTED",
            "title": "毕业设计材料退回整改",
            "require_ack": False,
        },
    })
    _INSTALLED = True


__all__ = ["EVENT_REVIEW_REJECTED", "install"]
