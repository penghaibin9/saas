"""Stage C3 毕业正式预审 overall 的 fail-closed 策略。

不可变 GraduationEvaluationRun 是后续毕业终审的事实锚点，因此正式评估只有在所有证据项
明确 PASS 时才允许 SYSTEM_PASSED。任何 FAIL、UNKNOWN、缺失/异常 result 都必须保持
SYSTEM_ABNORMAL；就业、归档、费用等可人工复核项可以在旧工作队列/展示层继续保留提示语义，
但不得覆盖 Stage C3 不可变 evaluator 的严格判定。
"""
from __future__ import annotations


def strict_overall(items) -> str:
    rows = [item for item in (items or []) if isinstance(item, dict)]
    if not rows:
        return "SYSTEM_ABNORMAL"

    return (
        "SYSTEM_PASSED"
        if all(str(item.get("result") or "").upper() == "PASS" for item in rows)
        else "SYSTEM_ABNORMAL"
    )


def install(target_module) -> None:
    target_module._strict_overall = strict_overall
