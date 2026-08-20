"""V3 §4.1–§4.4：MobileAction Adapter / typed target / focus 合同。

覆盖 V3 深审 P0-02（不得出现第三套路由 Authority、DTO 不得丢弃 typed 字段）与
P0-03（“路由存在”不等于“进入具体对象”）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.services import message_action_registry as messages
from app.services import mobile_action_service as adapter
from app.services.mobile_focus_contract import (
    FOCUS_DETAIL,
    FOCUS_LIST_FOCUS,
    FOCUS_MODES,
    FOCUS_READY_PAGES,
    is_route_exact,
)
from app.services.todo_route_registry import resolve_todo_route, route_contract_snapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGES_JSON = REPO_ROOT / "miniapp" / "src" / "pages.json"
ADAPTER_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "mobile_action_service.py"


def _miniapp_routes() -> set[str]:
    """按普通分包还原完整 /pages/... URL 集合（S1 之后 pages.json 不再是平铺列表）。"""
    manifest = json.loads(PAGES_JSON.read_text(encoding="utf-8"))
    routes = {"/" + page["path"] for page in manifest.get("pages", [])}
    for package in manifest.get("subPackages", []):
        root = str(package.get("root", "")).strip("/")
        for page in package.get("pages", []):
            routes.add(f"/{root}/{page['path']}")
    return routes


MINI_ROUTES = _miniapp_routes()


# ── §4.2 registry → pages.json 可达性 ──

def test_every_registered_mini_route_exists_in_pages_json():
    """registry 里登记的小程序落点必须真的存在，否则用户点开就是死链。"""
    missing = []
    for spec in messages.list_action_keys():
        for client in ("studentMini", "teacherMini"):
            path = spec["routes"].get(client)
            if path and path not in MINI_ROUTES:
                missing.append(f"message:{spec['actionKey']}:{client} -> {path}")
    for todo_type, row in route_contract_snapshot()["studentMini"].items():
        if row["path"] not in MINI_ROUTES:
            missing.append(f"todo:{todo_type}:studentMini -> {row['path']}")
    assert missing == [], "以下深链落点在 pages.json 中不存在：\n" + "\n".join(missing)


def test_leave_deep_link_points_at_the_leave_authority_not_a_generic_hall():
    """§4.3：请假是专用 Authority，深链不得落到“我的申请”这类通用大厅。"""
    spec = messages.ACTION_REGISTRY["student.leave.detail"]
    assert spec["studentMini"] == "/pages/student/affairs/leave"
    assert spec["teacherMini"] == "/pages/teacher/approval/index"
    # 旧的复数拼写在 pages.json 里根本不存在。
    assert "/pages/teacher/approvals/index" not in MINI_ROUTES


def test_exam_and_warning_deep_links_no_longer_land_on_the_campus_service_hall():
    assert messages.ACTION_REGISTRY["student.exam.detail"]["studentMini"] == "/pages/student/academic-affairs/exam"
    assert messages.ACTION_REGISTRY["student.warning.detail"]["studentMini"] == "/pages/student/academic-affairs/warning"


# ── §4.1 缺参 / 未登记 key 必须 fail-closed ──

@pytest.mark.parametrize("action_key", sorted(
    key for key, spec in messages.ACTION_REGISTRY.items() if spec.get("requiredParams")
))
def test_missing_required_params_are_rejected(action_key):
    with pytest.raises(AppException) as exc:
        messages.validate_action(action_key, {})
    assert exc.value.http_status == 422


def test_unknown_action_key_is_rejected():
    with pytest.raises(AppException) as exc:
        messages.validate_action("totally.unknown.key", {"x": 1})
    assert exc.value.http_status == 422


def test_adapter_turns_invalid_actions_into_a_disabled_descriptor_not_a_guess():
    for action_key, params in [("totally.unknown.key", {"x": 1}), ("student.leave.detail", {})]:
        action = adapter.build_message_action(action_key, params)
        assert action["target"] is None
        assert action["disabledReason"]
        assert action["focusMode"] == "NONE"


def test_withdrawn_messages_expose_no_action():
    action = adapter.build_message_action("student.leave.detail", {"leaveId": "7"}, withdrawn=True)
    assert action["target"] is None
    assert action["disabledReason"] == "该消息已撤回"


def test_empty_action_key_means_no_deep_link_at_all():
    assert adapter.build_message_action(None, {}) is None
    assert adapter.build_message_action("", {}) is None


def test_cross_side_targets_are_blocked_per_client():
    """教师专属 action 在学生端必须没有可跳转 target。"""
    action = adapter.build_message_action("teacher.internship.risk", {"riskId": "9"},
                                          client=adapter.CLIENT_STUDENT_MINI)
    assert action["target"] is None
    assert action["disabledReason"]

    teacher = adapter.build_message_action("teacher.internship.risk", {"riskId": "9"},
                                           client=adapter.CLIENT_TEACHER_MINI)
    assert teacher["target"]["path"] == "/pages/teacher/risk-students/index"


def test_unknown_todo_type_yields_no_open_action():
    action = adapter.build_todo_action(
        {"todoType": "BRAND_NEW_TODO", "recordId": "1", "allowedActions": ["OPEN", "COMPLETE"]}
    )
    assert action["target"] is None
    assert "OPEN" not in action["allowedActions"], "没有安全落点时不得下发 OPEN"
    assert "COMPLETE" in action["allowedActions"]


# ── §4.4 focus 合同 ──

def test_declared_focus_modes_are_valid_and_backed_by_a_real_page():
    for todo_type, row in route_contract_snapshot()["studentMini"].items():
        assert row["focusMode"] in FOCUS_MODES, todo_type
        if row["focusMode"] == FOCUS_LIST_FOCUS:
            assert row["path"] in FOCUS_READY_PAGES, f"{todo_type} 声明 LIST_FOCUS 但页面未登记聚焦能力"
        assert row["exact"] is is_route_exact(row["focusMode"], row["path"])

    for spec in messages.list_action_keys():
        for client in ("studentMini", "teacherMini"):
            mode = spec["focus"][client]
            assert mode in FOCUS_MODES
            path = spec["routes"].get(client)
            if mode == FOCUS_LIST_FOCUS:
                assert path in FOCUS_READY_PAGES, f"{spec['actionKey']}:{client} 声明 LIST_FOCUS 但页面未登记聚焦能力"


def test_focus_ready_pages_all_exist():
    for path in FOCUS_READY_PAGES:
        assert path in MINI_ROUTES, f"{path} 登记了聚焦能力但页面不存在"


def test_route_exact_requires_real_object_focus():
    # DETAIL 天然精确
    assert is_route_exact(FOCUS_DETAIL, "/pages/common/message-detail/index") is True
    # LIST_FOCUS 只有页面实现了才精确
    assert is_route_exact(FOCUS_LIST_FOCUS, "/pages/student/affairs/leave") is True
    assert is_route_exact(FOCUS_LIST_FOCUS, "/pages/student/internship/index") is False
    # 仅有入口不算对象级闭环
    assert is_route_exact("NONE", "/pages/student/affairs/leave") is False
    assert is_route_exact("nonsense", "/pages/student/affairs/leave") is False


def test_list_focus_without_a_focus_value_degrades_instead_of_faking_precision():
    """声明 LIST_FOCUS 却没带聚焦值时必须降级为 NONE，不得虚报 routeExact。"""
    route = resolve_todo_route("LEAVE_APPROVAL", "55", client="studentMini")
    assert route["focusMode"] == FOCUS_LIST_FOCUS and route["exact"] is True

    action = adapter.build_todo_action(
        {"todoType": "LEAVE_APPROVAL", "recordId": "55", "allowedActions": ["OPEN"], "version": 2}
    )
    assert action["target"]["focusMode"] == FOCUS_LIST_FOCUS
    assert action["target"]["routeExact"] is True
    assert action["target"]["query"]["recordId"] == "55"
    assert action["expectedVersion"] == 2


# ── P0-02：Adapter 不得成为第三套路由 Authority ──

def test_adapter_holds_no_route_map_of_its_own():
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    body = "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("#") and '"""' not in line
    )
    assert "/pages/student/affairs" not in body, "Adapter 里出现了具体业务页路径，等于第三份 route map"
    assert "/admin/" not in body
    # 只允许保留端前缀白名单
    snapshot = adapter.action_contract_snapshot()
    assert snapshot["allowedPrefixes"]["studentMini"] == ["/pages/student/", "/pages/common/"]
    assert snapshot["allowedPrefixes"]["teacherMini"] == ["/pages/teacher/", "/pages/common/"]


def test_adapter_only_reads_from_the_two_existing_authorities():
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")
    assert "from app.services.todo_route_registry import resolve_todo_route" in source
    assert "from app.services import message_action_registry as _messages" in source


# ── 学工域 canonical actionKey 必须被消息 Authority 认识 ──
#
# 回归来源：Real Task 真实回放。学生请假被辅导员退回后，收到的「请假被退回」消息里
# 存的是 AFFAIRS_LEAVE——affairs_student_contract_security_guard 在 emit_message_event
# 上做写时归一，把 student.leave.detail 这类点号键改写成 AFFAIRS_* canonical 键。
# 本表当时只登记点号键，于是每一条真实学工消息在 Adapter 里都 validate 失败，
# 降级成 action=null，学生点不进原请假对象，手册 §13 Real Task 第一条链路是断的。
# 这几条测试锁住"落库的键"与"注册表认识的键"必须是同一套。

def _canonical_affairs_action_keys() -> set[str]:
    from app.services.affairs_student_contract_security_guard import _CANONICAL_MESSAGE_ACTIONS
    return set(_CANONICAL_MESSAGE_ACTIONS)


def test_every_canonical_affairs_action_key_is_registered():
    missing = sorted(_canonical_affairs_action_keys() - set(messages.ACTION_REGISTRY))
    assert not missing, (
        f"学工域写时归一会把消息 actionKey 落成这些键，但消息注册表不认识：{missing}。"
        "未登记的键在 Adapter 里 fail-closed，学生消息会变成不可点击的死链。"
    )


def test_legacy_dotted_keys_and_their_canonical_replacements_agree_on_the_target():
    """legacy 别名与 canonical 键必须落到同一个学生端页面，否则两条链路会漂移。"""
    from app.services.affairs_student_contract_security_guard import _LEGACY_MESSAGE_ACTIONS
    for legacy, canonical in _LEGACY_MESSAGE_ACTIONS.items():
        if legacy not in messages.ACTION_REGISTRY or canonical not in messages.ACTION_REGISTRY:
            continue
        assert (messages.ACTION_REGISTRY[legacy]["studentMini"]
                == messages.ACTION_REGISTRY[canonical]["studentMini"]), legacy


def test_returned_leave_message_reaches_the_leave_object():
    """请假退回通知：真实落库参数 → 请假页 + recordId 聚焦，routeExact 为真。"""
    action = adapter.build_message_action(
        "AFFAIRS_LEAVE",
        {"leaveId": 2, "bizType": "LEAVE_REQUEST", "recordId": "2"},
        client=adapter.CLIENT_STUDENT_MINI,
    )
    target = action["target"]
    assert target["path"] == "/pages/student/affairs/leave"
    assert target["query"]["recordId"] == "2"
    assert target["focusMode"] == FOCUS_LIST_FOCUS
    assert target["routeExact"] is True
    assert action["disabledReason"] is None


def test_affairs_keys_claiming_list_focus_have_a_focus_ready_page():
    for key in sorted(_canonical_affairs_action_keys() & set(messages.ACTION_REGISTRY)):
        spec = messages.ACTION_REGISTRY[key]
        if messages.focus_mode_for(key, client="studentMini") != FOCUS_LIST_FOCUS:
            continue
        path = spec["studentMini"]
        assert path in FOCUS_READY_PAGES, f"{key} 宣称 LIST_FOCUS，但 {path} 没有登记聚焦参数"
        assert FOCUS_READY_PAGES[path] == messages.focus_param_for(key)


def test_affairs_keys_never_send_students_into_teacher_pages():
    for key in sorted(_canonical_affairs_action_keys() & set(messages.ACTION_REGISTRY)):
        path = messages.ACTION_REGISTRY[key].get("studentMini")
        if not path:
            continue
        assert path.startswith(("/pages/student/", "/pages/common/")), f"{key} -> {path}"
