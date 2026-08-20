"""V3 §4.4 对象聚焦（Focus）合同。

“路由存在”不等于“进入具体对象”。V3 深审 P0-03：多个 StudentMini target 其实是列表页，
页面根本不读 recordId，用户点“去处理”后仍要自己在列表里找那条记录。

focusMode 把这件事显式化：

- ``DETAIL``      目标就是该对象的详情页，天然对象级闭环。
- ``LIST_FOCUS``  目标是列表页，但该页面已实现“读取 recordId → 定位/展开该对象”。
- ``NONE``        只有一个安全入口，没有对象聚焦能力。

routeExact 只有 DETAIL，或 LIST_FOCUS 且目标页已登记在 :data:`FOCUS_READY_PAGES` 时才为真。
登记本身不是证据——``miniapp/tests/action-focus-contract.test.mjs`` 会逐页证明它真的消费了
recordId；页面没实现就把它从这里删掉，让 routeExact 掉回 false，而不是让它继续假装精确。
"""
from __future__ import annotations

FOCUS_DETAIL = "DETAIL"
FOCUS_LIST_FOCUS = "LIST_FOCUS"
FOCUS_NONE = "NONE"

FOCUS_MODES = frozenset({FOCUS_DETAIL, FOCUS_LIST_FOCUS, FOCUS_NONE})

#: 已经真正实现对象聚焦的页面 → 该页面消费的 query 参数名。
#: 每条都由 miniapp/tests/action-focus-contract.test.mjs 逐页证明。
FOCUS_READY_PAGES: dict[str, str] = {
    "/pages/student/affairs/leave": "recordId",
    "/pages/student/affairs/aid": "recordId",
    "/pages/student/affairs/funding": "recordId",
    # 补交材料入口早于 V3 就已实现聚焦，沿用它自己的参数名，不为统一而改坏现网深链。
    "/pages/student/affairs/index": "materialRequirementId",
}


def normalize_focus_mode(value: str | None) -> str:
    mode = str(value or "").strip().upper()
    return mode if mode in FOCUS_MODES else FOCUS_NONE


def focus_param(path: str | None) -> str | None:
    """该页面用哪个 query 参数聚焦对象；未登记则返回 None。"""
    return FOCUS_READY_PAGES.get(str(path or ""))


def is_route_exact(focus_mode: str | None, path: str | None) -> bool:
    """只有真的能落到对象上才算 exact。"""
    mode = normalize_focus_mode(focus_mode)
    if mode == FOCUS_DETAIL:
        return True
    if mode == FOCUS_LIST_FOCUS:
        return bool(path) and path in FOCUS_READY_PAGES
    return False


def focus_contract_snapshot() -> dict:
    """供 CI/合同测试枚举，防止有人只改 focusMode 不改页面。"""
    return {
        "focusModes": sorted(FOCUS_MODES),
        "focusReadyPages": dict(sorted(FOCUS_READY_PAGES.items())),
    }
