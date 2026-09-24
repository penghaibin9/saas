"""学工异议/申诉结果消息事件登记。

统一申诉待办服务会按 ``{biz_type}.RESULT`` 发学生结果通知。事件必须进入
消息 Outbox 的白名单，否则业务复核虽然已经提交成功，后续结果通知会被
422 拦截并只能进入补偿队列。这里只登记统一申诉服务实际产生的缺失事件，
不绕过 Outbox 的事件码校验、事务边界或幂等机制。
"""
from __future__ import annotations


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import message_event_outbox_service as outbox

    outbox._EVENT_TEMPLATES.update({
        "AID_OBJECTION.RESULT": {
            "source_module": "student-affairs",
            "category": "BUSINESS",
            "priority": "IMPORTANT",
            "message_type": "WORKFLOW_RESULT",
            "title": "困难认定异议复核结果",
            "require_ack": False,
        },
        "FUNDING_APPEAL.RESULT": {
            "source_module": "student-affairs",
            "category": "BUSINESS",
            "priority": "IMPORTANT",
            "message_type": "WORKFLOW_RESULT",
            "title": "资助公示申诉复核结果",
            "require_ack": False,
        },
        "SECOND_CLASS_APPEAL.RESULT": {
            "source_module": "student-affairs",
            "category": "BUSINESS",
            "priority": "NORMAL",
            "message_type": "WORKFLOW_RESULT",
            "title": "第二课堂积分申诉审核结果",
            "require_ack": False,
        },
    })
    _INSTALLED = True
