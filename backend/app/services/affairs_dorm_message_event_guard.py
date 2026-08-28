"""学工补充消息事件启动登记入口。

历史上本入口只登记宿舍调宿事件，因此保留原文件名和 router 安装点以避免扩大
启动期 patch graph。现在同时安装统一异议/申诉结果事件白名单；各子 guard 仍独立
幂等，且都不绕过消息 Outbox 的事件码校验、事务边界与幂等机制。
"""
from __future__ import annotations


_INSTALLED = False


def install() -> None:
    global _INSTALLED

    # 统一申诉结果通知与宿舍事件共享现有学工消息启动边界，避免为了补三个事件码
    # 再向全局 router 增加一个 installer。即使本 guard 已安装，子 guard 仍可幂等补齐。
    from app.services.affairs_appeal_message_event_guard import install as install_appeal_events
    install_appeal_events()

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
