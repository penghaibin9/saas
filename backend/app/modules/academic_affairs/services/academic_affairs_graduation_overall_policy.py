"""毕业正式预审 overall 策略收口。

Stage C3 不可变 Run 必须沿用毕业域既有阻断政策：任何 FAIL 都阻断；关键业务项 UNKNOWN
也阻断；就业、归档、费用等明确标记为人工复核/提醒项的 UNKNOWN 只保留证据，不把所有学生
永久卡成 SYSTEM_ABNORMAL。
"""
from __future__ import annotations

from . import academic_affairs_graduation_service as graduation_service


def strict_overall(items) -> str:
    rows = [item for item in (items or []) if isinstance(item, dict)]
    if not rows:
        return "SYSTEM_ABNORMAL"

    blocking_unknown = set(graduation_service._BLOCKING_UNKNOWN_ITEMS)
    for item in rows:
        result = str(item.get("result") or "UNKNOWN").upper()
        code = str(item.get("item") or "").upper()
        if result == "FAIL":
            return "SYSTEM_ABNORMAL"
        if result == "UNKNOWN" and code in blocking_unknown:
            return "SYSTEM_ABNORMAL"
    return "SYSTEM_PASSED"


def install(target_module) -> None:
    target_module._strict_overall = strict_overall
