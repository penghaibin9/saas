"""V3 §4.1 MobileAction Adapter —— 只归一 DTO，不保存第三份 route map。

V3 深审 P0-02：如果这里再建一张自己的 route 表，仓库里就会同时存在三套路由 Authority
（todo_route_registry / message_action_registry / 本文件），三者迟早互相漂移。

因此本模块严格只做两件事：

1. 从既有 Authority 取路由 ——
   * 待办：:func:`app.services.todo_route_registry.resolve_todo_route`
   * 消息：:func:`app.services.message_action_registry.resolve_route`
2. 把它们规范成同一个 MobileAction DTO 形状，并补上 §4.4 的 focus 语义。

Fail-closed：未登记 action / 缺必需参数 / 当前端没有安全落点，一律不给可跳转 target，
只给 ``disabledReason``。ActionDescriptor 是只读投影，**不授予任何权限**——
``allowedActions`` 来自 canonical domain read，写命令仍然要回 canonical service
重新校验租户、模块授权、权限、数据范围、业务关系、状态与 version。
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from app.core.exceptions import AppException
from app.services import message_action_registry as _messages
from app.services import mobile_observability_service as obs
from app.services.mobile_focus_contract import (
    FOCUS_DETAIL,
    FOCUS_NONE,
    focus_param,
    is_route_exact,
    normalize_focus_mode,
)
from app.services.todo_route_registry import resolve_todo_route

#: 学生小程序端标识；与 todo_route_registry / message_action_registry 的 client 命名一致。
CLIENT_STUDENT_MINI = "studentMini"
CLIENT_TEACHER_MINI = "teacherMini"

_MINI_CLIENTS = frozenset({CLIENT_STUDENT_MINI, CLIENT_TEACHER_MINI})

#: 每个端只允许跳自己的分包与共享页，越界一律 fail-closed。
_ALLOWED_PREFIXES: dict[str, tuple[str, ...]] = {
    CLIENT_STUDENT_MINI: ("/pages/student/", "/pages/common/"),
    CLIENT_TEACHER_MINI: ("/pages/teacher/", "/pages/common/"),
}

_NO_TARGET_REASON = "当前端暂无安全处理入口"


def _clean(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _client_allows(path: str, client: str) -> bool:
    prefixes = _ALLOWED_PREFIXES.get(client)
    if not prefixes:
        return False
    return any(path.startswith(prefix) for prefix in prefixes)


def _blocked(
    *,
    source_biz_type: Optional[str],
    source_biz_id: Optional[str],
    record_id: Optional[str],
    reason: str,
    label: Optional[str] = None,
    allowed_actions: Optional[Iterable[str]] = None,
    client: Optional[str] = None,
    action_key: Optional[str] = None,
) -> dict:
    """有业务对象但当前端没有安全落点：给出可解释的禁用态，不给 target。"""
    # §13：未解析的 action 必须留痕，否则 P0-02 复发时只能靠用户投诉发现。
    obs.record_unknown_action(action_key or source_biz_type, client=client or "unknown")
    return {
        "sourceBizType": source_biz_type,
        "sourceBizId": source_biz_id,
        "recordId": record_id,
        "target": None,
        "allowedActions": list(allowed_actions or []),
        "expectedVersion": None,
        "focusMode": FOCUS_NONE,
        "label": label,
        "disabledReason": reason,
    }


def _descriptor(
    *,
    client: str,
    path: str,
    query: dict[str, Any],
    route_name: Optional[str],
    focus_mode: str,
    source_biz_type: Optional[str],
    source_biz_id: Optional[str],
    record_id: Optional[str],
    allowed_actions: Iterable[str],
    expected_version: Optional[int],
    label: Optional[str],
) -> dict:
    mode = normalize_focus_mode(focus_mode)
    # 声明 LIST_FOCUS 却没带聚焦值，等于又回到“到了列表自己找”——降级成 NONE，不虚报精确。
    focus_key = focus_param(path)
    if mode not in (FOCUS_DETAIL, FOCUS_NONE):
        if not focus_key or _clean(query.get(focus_key)) is None:
            mode = FOCUS_NONE
    # §13：声明了对象聚焦却没能真的聚焦，是 P0-03 复发的早期信号。
    obs.record_focus_result(route_name=route_name, focused=is_route_exact(mode, path))
    return {
        "sourceBizType": source_biz_type,
        "sourceBizId": source_biz_id,
        "recordId": record_id,
        "target": {
            "client": client,
            "path": path,
            "query": {key: value for key, value in query.items() if value not in (None, "")},
            "routeName": route_name,
            "focusMode": mode,
            "focusParam": focus_key,
            "routeExact": is_route_exact(mode, path),
        },
        "allowedActions": list(allowed_actions or []),
        "expectedVersion": expected_version,
        "focusMode": mode,
        "label": label,
        "disabledReason": None,
    }


def build_todo_action(todo: dict | None, *, client: str = CLIENT_STUDENT_MINI) -> dict | None:
    """把 workbench_todo_service 已生成的 typed todo DTO 归一成 MobileAction。

    只消费 todo_route_registry 的结论，不在这里判断 todoType 该去哪。
    """
    if not todo:
        return None
    if client not in _MINI_CLIENTS:
        raise AppException("VALIDATION_ERROR", f"不支持的移动端 client：{client}")

    todo_type = _clean(todo.get("todoType"))
    record_id = _clean(todo.get("recordId")) or _clean(todo.get("bizId"))
    source_biz_type = _clean(todo.get("bizType")) or todo_type
    allowed_actions = todo.get("allowedActions") or []
    expected_version = todo.get("version")
    expected_version = int(expected_version) if isinstance(expected_version, int) else None

    route = resolve_todo_route(todo_type, record_id, client=client)
    if not route or not route.get("path"):
        return _blocked(
            source_biz_type=source_biz_type,
            source_biz_id=record_id,
            record_id=record_id,
            reason=_NO_TARGET_REASON,
            label=_clean(todo.get("title")),
            # 没有安全落点时不下发 OPEN，避免前端拿着它渲染一个点不动的按钮。
            allowed_actions=[a for a in allowed_actions if a != "OPEN"],
            client=client, action_key=todo_type,
        )

    path = str(route["path"])
    if not _client_allows(path, client):
        return _blocked(
            source_biz_type=source_biz_type,
            source_biz_id=record_id,
            record_id=record_id,
            reason=_NO_TARGET_REASON,
            label=_clean(todo.get("title")),
            allowed_actions=[a for a in allowed_actions if a != "OPEN"],
            client=client, action_key=todo_type,
        )

    return _descriptor(
        client=client,
        path=path,
        query=dict(route.get("query") or {}),
        route_name=route.get("routeName"),
        focus_mode=route.get("focusMode") or FOCUS_NONE,
        source_biz_type=source_biz_type,
        source_biz_id=record_id,
        record_id=record_id,
        allowed_actions=allowed_actions,
        expected_version=expected_version,
        label=_clean(todo.get("title")),
    )


def build_message_action(
    action_key: Optional[str],
    action_params: Optional[dict] = None,
    *,
    client: str = CLIENT_STUDENT_MINI,
    withdrawn: bool = False,
) -> dict | None:
    """把消息 actionKey + actionParams 归一成 MobileAction。

    未登记 key / 缺必需参数由 message_action_registry.validate_action() 判定（422），
    这里把它转成 fail-closed 的禁用态，而不是让前端拿着一个猜出来的路由乱跳。
    """
    if client not in _MINI_CLIENTS:
        raise AppException("VALIDATION_ERROR", f"不支持的移动端 client：{client}")
    key = _clean(action_key)
    if not key:
        return None
    # 已撤回的消息不给任何可执行 action。
    if withdrawn:
        return _blocked(
            source_biz_type=None, source_biz_id=None, record_id=None,
            reason="该消息已撤回", client=client, action_key=key,
        )

    try:
        key, cleaned = _messages.validate_action(key, action_params or {})
    except AppException:
        return _blocked(
            source_biz_type=None, source_biz_id=None, record_id=None,
            reason=_NO_TARGET_REASON, client=client, action_key=key,
        )
    if not key:
        return None

    route = _messages.resolve_route(key, client=client)
    focus_key = _messages.focus_param_for(key)
    record_id = _clean((cleaned or {}).get(focus_key)) if focus_key else None
    if not route.get("ok") or not route.get("path"):
        return _blocked(
            source_biz_type=key, source_biz_id=record_id, record_id=record_id,
            reason=route.get("message") or _NO_TARGET_REASON,
            label=route.get("label"), client=client, action_key=key,
        )

    path = str(route["path"])
    if not _client_allows(path, client):
        return _blocked(
            source_biz_type=key, source_biz_id=record_id, record_id=record_id,
            reason=_NO_TARGET_REASON, label=route.get("label"),
            client=client, action_key=key,
        )

    query = dict(cleaned or {})
    # 目标页面登记的聚焦参数名与消息参数名不一致时补一份，例如列表页统一读 recordId。
    page_focus_key = focus_param(path)
    if page_focus_key and record_id and query.get(page_focus_key) in (None, ""):
        query[page_focus_key] = record_id

    return _descriptor(
        client=client,
        path=path,
        query=query,
        route_name=f"message-action:{key}",
        focus_mode=route.get("focusMode") or FOCUS_NONE,
        source_biz_type=key,
        source_biz_id=record_id,
        record_id=record_id,
        # 消息投影不下发写权限；能不能办由目标页自己的 canonical read 决定。
        allowed_actions=["OPEN"],
        expected_version=None,
        label=route.get("label"),
    )


def action_contract_snapshot() -> dict:
    """供 CI/合同测试枚举：本模块自己没有 route map，只有端前缀白名单。"""
    return {
        "clients": sorted(_MINI_CLIENTS),
        "allowedPrefixes": {client: list(prefixes) for client, prefixes in _ALLOWED_PREFIXES.items()},
        "noTargetReason": _NO_TARGET_REASON,
    }
