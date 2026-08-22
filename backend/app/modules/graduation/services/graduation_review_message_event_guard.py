"""W7.6 graduation review message event/action contracts.

Only event/action metadata is registered here. Delivery, deduplication, retries and
UnifiedMessage materialization remain owned by the shared messaging platform.
"""
from __future__ import annotations

_INSTALLED = False
EVENT_REVIEW_REJECTED = "GRADUATION_DESIGN.REVIEW_REJECTED"
ACTION_STUDENT_REVIEW_FEEDBACK = "student.graduation.review-feedback"


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import message_event_outbox_service as outbox
    from app.services.message_action_registry import ACTION_REGISTRY

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
    ACTION_REGISTRY.setdefault(ACTION_STUDENT_REVIEW_FEEDBACK, {
        "roles": ["STUDENT"],
        "requiredParams": [],
        "pc": None,
        "studentPc": "/graduation/feedback",
        "studentMini": None,
        "teacherMini": None,
        "label": "查看毕设评阅反馈并整改重交",
    })
    _INSTALLED = True


__all__ = ["EVENT_REVIEW_REJECTED", "ACTION_STUDENT_REVIEW_FEEDBACK", "install"]
