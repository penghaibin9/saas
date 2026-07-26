"""教师移动端任务书历史 DTO 兼容桥。

旧 Service 返回 {list,total}，新批次分页门禁统一消费 list。只在路由安装期包一层，
不改变任务书状态机、权限或持久化逻辑。
"""
from __future__ import annotations

_INSTALLED = False


def install_mobile_taskbook_list_bridge() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from app.services import mobile_teacher_service as mobile

    original = mobile.graduation_taskbook_list

    def normalized(user: dict) -> list:
        value = original(user)
        if isinstance(value, dict):
            rows = value.get("items") if isinstance(value.get("items"), list) else value.get("list")
            return rows if isinstance(rows, list) else []
        return value if isinstance(value, list) else []

    mobile.graduation_taskbook_list = normalized
