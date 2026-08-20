"""学生 PC 门户 · Action Projection（V3 施工手册 SP-H03 / SP-H06 / SP-M03 前置）。

只复用共享 Authority，不新建第二份业务路由表：

- 消息动作：复用 :mod:`app.services.message_action_registry`（``studentPc`` client
  已在该表登记，本文件只把它归一成 StudentPcActionDescriptor 形状）。
- 待办动作：复用 :func:`app.services.workbench_todo_service.list_todos` 产出的
  typed todo DTO（内部经 :mod:`app.services.todo_route_registry` 解析路由）。
  该 registry 目前尚未登记 ``studentPc`` client（Owner：PR #183 合并后的共享
  registry owner 统一补齐，见二级模块施工包 SP-M03），因此 routePath 恒为
  ``None``——本函数据此 fail-closed：只给禁用态 + 可解释 disabledReason，
  不在这里另起一张 todoType→路由映射去抢работ。todo_route_registry 一旦补上
  ``studentPc`` 分支，本函数无需改动即自动生效。

DTO 形状固定为 §14.1 StudentPcActionDescriptor：
``{sourceBizType, sourceBizId, recordId, target, allowedActions,
   expectedVersion, focusMode, label, disabledReason}``。
``target`` 为 ``None`` 时表示 fail-closed，前端必须禁用按钮而不是自己猜路由。
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.exceptions import AppException
from app.services import message_action_registry as messages_registry
from app.services import mobile_observability_service as obs
from app.services.mobile_focus_contract import FOCUS_NONE, is_route_exact, normalize_focus_mode

#: 学生 PC 门户端标识；与 message_action_registry 的 client 命名一致。
CLIENT_STUDENT_PC = "studentPc"

_TODO_DISABLED_REASON = "该类待办暂未开通学生 PC 端专属定位入口，请前往消息中心或对应业务模块查看处理"
_NO_TARGET_REASON = "当前端暂无安全处理入口"


def _clean(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _blocked(
    *,
    source_biz_type: Optional[str],
    source_biz_id: Optional[str],
    record_id: Optional[str],
    reason: str,
    label: Optional[str] = None,
    allowed_actions: Optional[list[str]] = None,
    action_key: Optional[str] = None,
) -> dict:
    """有业务对象但当前端没有安全落点：给出可解释的禁用态，不给 target（fail-closed）。"""
    obs.record_unknown_action(action_key or source_biz_type, client=CLIENT_STUDENT_PC)
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


def build_todo_action(todo: dict | None) -> dict | None:
    """把 workbench_todo_service 已生成的 typed todo DTO 归一成 StudentPcActionDescriptor。

    只消费 todo 字典里 todo_route_registry 已经解析出的结论（routePath/routeExact/
    routeName），不在这里判断 todoType 该去哪。
    """
    if not todo:
        return None
    record_id = _clean(todo.get("recordId")) or _clean(todo.get("bizId"))
    source_biz_type = _clean(todo.get("bizType")) or _clean(todo.get("todoType"))
    label = _clean(todo.get("title"))
    expected_version = todo.get("version")
    expected_version = int(expected_version) if isinstance(expected_version, int) else None

    route_path = todo.get("routePath")
    if not route_path:
        return _blocked(
            source_biz_type=source_biz_type, source_biz_id=record_id, record_id=record_id,
            reason=_TODO_DISABLED_REASON, label=label,
            allowed_actions=[], action_key=todo.get("todoType"),
        )

    focus_mode = normalize_focus_mode(FOCUS_NONE)
    focused = is_route_exact(focus_mode, route_path)
    obs.record_focus_result(route_name=todo.get("routeName"), focused=focused)
    return {
        "sourceBizType": source_biz_type,
        "sourceBizId": record_id,
        "recordId": record_id,
        "target": {
            "client": CLIENT_STUDENT_PC,
            "path": str(route_path),
            "query": {k: v for k, v in (todo.get("query") or {}).items() if v not in (None, "")},
            "routeName": todo.get("routeName"),
            "focusMode": focus_mode,
            "focusParam": None,
            "routeExact": focused,
        },
        "allowedActions": ["OPEN"] if "OPEN" in (todo.get("allowedActions") or []) else [],
        "expectedVersion": expected_version,
        "focusMode": focus_mode,
        "label": label,
        "disabledReason": None,
    }


def build_message_action(
    action_key: Optional[str], action_params: Optional[dict] = None, *, withdrawn: bool = False
) -> dict | None:
    """把消息 actionKey + actionParams 归一成 StudentPcActionDescriptor。

    未登记 key / 缺必需参数由 message_action_registry.validate_action() 判定，这里
    转成 fail-closed 的禁用态，而不是让前端拿着一个猜出来的路由乱跳（SP-H06）。
    """
    key = _clean(action_key)
    if not key:
        return None
    if withdrawn:
        return _blocked(
            source_biz_type=None, source_biz_id=None, record_id=None,
            reason="该消息已撤回", action_key=key,
        )

    try:
        key, cleaned = messages_registry.validate_action(key, action_params or {})
    except AppException:
        return _blocked(
            source_biz_type=None, source_biz_id=None, record_id=None,
            reason=_NO_TARGET_REASON, action_key=key,
        )
    if not key:
        return None

    route = messages_registry.resolve_route(key, client=CLIENT_STUDENT_PC)
    focus_key = messages_registry.focus_param_for(key)
    record_id = _clean((cleaned or {}).get(focus_key)) if focus_key else None
    if not route.get("ok") or not route.get("path"):
        # registry 的通用兜底文案是写给"跨端"场景的（"请前往教师 PC / 学生 PC 办理"），
        # 对已经身处学生 PC 的用户是自相矛盾的指路。这里换成本端可理解的说明。
        return _blocked(
            source_biz_type=key, source_biz_id=record_id, record_id=record_id,
            reason=_NO_TARGET_REASON, label=route.get("label"), action_key=key,
        )

    path = str(route["path"])
    query = dict(route.get("staticQuery") or {})
    if record_id:
        query.setdefault("recordId", record_id)
    focus_mode = normalize_focus_mode(route.get("focusMode"))
    focused = is_route_exact(focus_mode, path)
    obs.record_focus_result(route_name=f"message-action:{key}", focused=focused)
    return {
        "sourceBizType": key,
        "sourceBizId": record_id,
        "recordId": record_id,
        "target": {
            "client": CLIENT_STUDENT_PC,
            "path": path,
            "query": query,
            "routeName": f"message-action:{key}",
            "focusMode": focus_mode,
            "focusParam": route.get("focusParam"),
            "routeExact": focused,
        },
        # 消息投影不下发写权限；能不能办由目标页自己的 canonical read 决定。
        "allowedActions": ["OPEN"],
        "expectedVersion": None,
        "focusMode": focus_mode,
        "label": route.get("label"),
        "disabledReason": None,
    }
