"""W7.6 graduation review message event/action contracts.

Only event/action metadata is registered here. Delivery, deduplication, retries and
UnifiedMessage materialization remain owned by the shared messaging platform.
"""
from __future__ import annotations

_INSTALLED = False
EVENT_PROPOSAL_SUBMITTED = "GRADUATION_DESIGN.PROPOSAL_SUBMITTED"
EVENT_REVIEW_REJECTED = "GRADUATION_DESIGN.REVIEW_REJECTED"
EVENT_REVIEW_APPROVED = "GRADUATION_DESIGN.REVIEW_APPROVED"
ACTION_TEACHER_PROPOSAL_REVIEW = "teacher.graduation.proposal-review"
ACTION_STUDENT_REVIEW_FEEDBACK = "student.graduation.review-feedback"


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import message_event_outbox_service as outbox
    from app.services.message_action_registry import ACTION_REGISTRY

    outbox._EVENT_TEMPLATES.update({
        EVENT_PROPOSAL_SUBMITTED: {
            "source_module": "graduation",
            "category": "TODO",
            "priority": "IMPORTANT",
            "message_type": "GRADUATION_PROPOSAL_SUBMITTED",
            "title": "开题报告待批阅",
            "require_ack": False,
        },
        EVENT_REVIEW_REJECTED: {
            "source_module": "graduation",
            "category": "BUSINESS",
            "priority": "IMPORTANT",
            "message_type": "GRADUATION_REVIEW_REJECTED",
            "title": "毕业设计材料退回整改",
            "require_ack": False,
        },
        EVENT_REVIEW_APPROVED: {
            "source_module": "graduation",
            "category": "BUSINESS",
            "priority": "NORMAL",
            "message_type": "GRADUATION_REVIEW_APPROVED",
            "title": "毕业设计材料已通过",
            "require_ack": False,
        },
    })
    ACTION_REGISTRY.setdefault(ACTION_TEACHER_PROPOSAL_REVIEW, {
        "roles": ["TEACHER", "STAFF"],
        "requiredParams": ["recordId", "batchId"],
        "optionalParams": ["kind", "gdStudentId"],
        "pc": "/admin/graduation/review-center",
        "studentPc": None,
        "studentMini": None,
        "teacherMini": "/pages/teacher/graduation-guide/index",
        "focus": {"teacherMini": "LIST_FOCUS"},
        "focusParam": "recordId",
        "label": "批阅开题报告",
    })
    ACTION_REGISTRY.setdefault(ACTION_STUDENT_REVIEW_FEEDBACK, {
        "roles": ["STUDENT"],
        "requiredParams": [],
        "optionalParams": ["recordId", "stage"],
        "pc": None,
        "studentPc": "/graduation/feedback",
        "studentMini": "/pages/student/graduation/index",
        "teacherMini": None,
        "label": "查看毕设评阅反馈并整改重交",
    })
    _INSTALLED = True


__all__ = [
    "ACTION_STUDENT_REVIEW_FEEDBACK",
    "ACTION_TEACHER_PROPOSAL_REVIEW",
    "EVENT_PROPOSAL_SUBMITTED",
    "EVENT_REVIEW_APPROVED",
    "EVENT_REVIEW_REJECTED",
    "install",
]
