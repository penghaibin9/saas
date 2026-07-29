"""宿舍调宿消息事件登记。

调宿节点服务通过统一消息 Outbox 通知学生；事件码必须先进入全局白名单，
否则终审业务会在通知阶段被 422 回滚。这里只登记调宿执行成功与驳回两种终态，
不绕过消息底座的事件码校验与幂等机制。
"""
from __future__ import annotations


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import message_event_outbox_service as outbox

    outbox._EVENT_TEMPLATES.update({
        "DORM.TRANSFER.EXECUTED": {
            "source_module": "student-affairs",
            "category": "BUSINESS",
            "priority": "NORMAL",
            "message_type": "WORKFLOW_RESULT",
            "title": "调宿已完成",
            "require_ack": False,
        },
        "DORM.TRANSFER.REJECTED": {
            "source_module": "student-affairs",
            "category": "BUSINESS",
            "priority": "IMPORTANT",
            "message_type": "RETURNED_NOTICE",
            "title": "调宿申请未通过",
            "require_ack": False,
        },
    })
    _INSTALLED = True
