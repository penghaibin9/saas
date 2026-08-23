"""学生 PC 门户 · HomeProjection v2（V3 施工手册 SP-H01/H02/H03/H04/H05/H07/H08）。

设计原则（与 :mod:`app.services.mobile_student_home_projection` 对称，但不复用它的
Mini DTO 形状与路由，避免两端投影耦合、互相漂移）：

- 只复用共享业务 reader/Authority——
  * 跨域聚合真值：:func:`app.services.mobile_student_service.me_overview`；
  * typed 待办：:func:`app.services.workbench_todo_service.list_todos`；
  * 本人消息 Authority：:mod:`app.services.message_center_service`（不再走
    ``mobile_student_service.my_messages`` 的 Python 内存过滤）；
  * typed action：:mod:`app.student_portal.services.action_projection_service`。
- 不新建业务事实表，不复制 Mini 的 route map。
- 每个独立读取都有自己的异常边界，失败时该分区诚实标 ``ERROR``，不吞成 ``{}``/空数组
  冒充“没有数据”（SP-H02）。``null`` 表示 unknown，只有真正查询成功的空结果才是 0
  （SP-H08）。
- 跨域状态一律在服务端归一成 lifecycleStatus，前端不得再用字符串撞词
  （NOT_STARTED/IN_PROGRESS/BLOCKED/COMPLETED/UNKNOWN/ERROR，SP-H04）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import AppException
from app.services import message_center_service as message_svc
from app.services import mobile_freshness_service as freshness
from app.services import mobile_student_service as stu
from app.services import student_portal_service as portal_cfg
from app.services import workbench_todo_service as todo_svc
from app.services.db_service import _tid
from app.student_portal.services import action_projection_service as action_proj

#: 首页 DTO schema 版本。结构变化时 +1，并进入缓存 key，避免灰度期读到旧结构。
HOME_VERSION = 2

TODO_LIMIT = 5
NOTICE_LIMIT = 5

#: 首页参与的投影域（供 projectionVersion 使用；写路径 bump 与 Mini 共用同一套域名）。
HOME_PROJECTIONS = ("todo", "message")

#: 快捷入口目录：key（与 portal-config.modules 对齐）→ 展示名 + 门户前端路由 path。
_QUICK_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("profile", "我的档案", "profile"),
    ("academic", "教务学业", "academic"),
    ("graduation", "毕业设计", "graduation"),
    ("internship", "岗位实习", "internship"),
    ("employment", "就业服务", "employment"),
    ("orientation", "迎新报到", "orientation"),
    ("campusService", "在校服务", "campus-service"),
    ("messages", "消息通知", "messages"),
)

#: 6 个统一生命周期值中，NOT_STARTED/IN_PROGRESS/BLOCKED/COMPLETED 由本文件产出；
#: UNKNOWN/ERROR 只在 core 分区失败、domains 为空时出现，由前端按分区状态兜底
#: （lifecycle 列表本身为空，前端 journey 找不到匹配项自然落到 UNKNOWN），不在这里
#: 声明常量制造死代码。
_LIFECYCLE_NOT_STARTED = "NOT_STARTED"
_LIFECYCLE_IN_PROGRESS = "IN_PROGRESS"
_LIFECYCLE_BLOCKED = "BLOCKED"
_LIFECYCLE_COMPLETED = "COMPLETED"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lifecycle_status(domain_key: str, has_data: bool, raw_status: str | None) -> str:
    """跨域生命周期归一（SP-H04）：不得用同一份 DONE_STATES 字符串集合一刀切。

    每个域各自定义"什么算完成"，含义不通用的域一律不宣称 COMPLETED——宁可保守显示
    "进行中"，也不能把不同域的同名状态词（如 SIGNED）误判成整体完成。
    """
    if not has_data:
        return _LIFECYCLE_NOT_STARTED
    code = str(raw_status or "").strip().upper()
    if not code or code == "NONE":
        return _LIFECYCLE_NOT_STARTED

    if domain_key == "orientation":
        if code in ("CHECKED_IN", "REPORTED", "DONE", "COMPLETED"):
            return _LIFECYCLE_COMPLETED
        if code == "BLOCKED":
            return _LIFECYCLE_BLOCKED
        return _LIFECYCLE_IN_PROGRESS
    if domain_key == "internship":
        if code in ("DONE", "COMPLETED"):
            return _LIFECYCLE_COMPLETED
        return _LIFECYCLE_IN_PROGRESS
    if domain_key == "academic":
        # "WARNING" 是 me_overview 派生的跨域摘要词（是否有未处理学业预警），不是
        # 教务真实状态机的一个状态值，只能标 BLOCKED，不能宣称 COMPLETED。
        return _LIFECYCLE_BLOCKED if code == "WARNING" else _LIFECYCLE_IN_PROGRESS
    if domain_key == "employment":
        # SP-H04 验收 Gate：材料/去向已提交（如 SIGNED）但核验状态未知时，绝不能显示
        # COMPLETED——PC Home 目前还没有独立 verifyStatus 事实（S4/S5 才引入结构化
        # submission + 核验回填，见 SP-E09），所以这里永不返回 COMPLETED，只区分
        # "还没声明" vs "已声明、待核验"，避免用材料状态冒充去向核验完成。
        return _LIFECYCLE_IN_PROGRESS
    return _LIFECYCLE_IN_PROGRESS


def _quick_services(modules: dict[str, bool]) -> list[dict[str, Any]]:
    """常用服务只做模块级导航（非对象级），target 由服务端按租户开通情况决定（SP-H05）。"""
    rows = []
    for key, label, path in _QUICK_CATALOG:
        if not modules.get(key, False):
            continue
        rows.append({
            "key": key,
            "label": label,
            "path": "/" + path,
            "action": {
                "sourceBizType": f"quick-service:{key}",
                "sourceBizId": None,
                "recordId": None,
                "target": {
                    "client": action_proj.CLIENT_STUDENT_PC,
                    "path": "/" + path,
                    "query": {},
                    "routeName": f"quick-service:{key}",
                    "focusMode": "NONE",
                    "focusParam": None,
                    "routeExact": False,
                },
                "allowedActions": ["OPEN"],
                "expectedVersion": None,
                "focusMode": "NONE",
                "label": label,
                "disabledReason": None,
            },
        })
    return rows


def _todo_items(user: dict) -> tuple[list[dict[str, Any]], int]:
    """复用 typed todo reader；client=studentPc 目前无 registry 落点则各自 fail-closed。"""
    rows, total = todo_svc.list_todos(
        user, status="PENDING", page=1, page_size=TODO_LIMIT, client=action_proj.CLIENT_STUDENT_PC
    )
    items = [{
        "id": row.get("todoId"),
        "todoType": row.get("todoType"),
        "title": row.get("title") or "待办事项",
        "module": row.get("sourceModule") or row.get("bizType") or "待办",
        "dueAt": row.get("dueAt"),
        "status": row.get("status") or "PENDING",
        "priority": row.get("priority") or "NORMAL",
        "action": action_proj.build_todo_action(row),
    } for row in rows]
    return items, int(total or 0)


def _notice_items(user: dict) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """复用 message_center 的本人可见性、排序与真分页，不再自建 receiver 过滤。"""
    rows, _total = message_svc.list_messages(user, page=1, page_size=NOTICE_LIMIT)
    counts = message_svc.count_messages(user)
    items = []
    for row in rows:
        withdrawn = bool(row.get("withdrawn"))
        items.append({
            "id": row.get("messageId"),
            "title": row.get("title") or "",
            "source": row.get("senderOrgName") or row.get("category") or "校园通知",
            "important": bool(row.get("emergency")),
            "read": row.get("readStatus") == "READ",
            "requireAck": bool(row.get("requireAck")),
            "acked": bool(row.get("acked")),
            "withdrawn": withdrawn,
            "time": row.get("createdAt"),
            "action": action_proj.build_message_action(
                row.get("actionKey"), row.get("actionParams"), withdrawn=withdrawn,
            ),
        })
    return items, counts


def _next_action(alerts: list[dict[str, Any]], todos: list[dict[str, Any]]) -> dict[str, Any] | None:
    """“下一步该做什么”优先阻断项，其次最紧的待办；没有可执行 action 就不出这张卡。"""
    by_module: dict[str, dict[str, Any]] = {}
    for todo in todos:
        module = str(todo.get("module") or "").lower()
        if module and module not in by_module:
            by_module[module] = todo
    for alert in alerts or []:
        domain = str(alert.get("domain") or "").lower()
        matched = by_module.get(domain)
        action = matched.get("action") if matched else None
        if action and action.get("target"):
            return action
    for todo in todos:
        action = todo.get("action")
        if action and action.get("target"):
            return action
    return None


def build_home_v2(user: dict) -> dict[str, Any]:
    """首页聚合投影：每个读取分区独立异常边界，失败诚实报 ERROR（SP-H01/H02/H07）。"""
    sections: dict[str, dict[str, str]] = {}

    try:
        base = stu.me_overview(user, include_home=True)
        sections["core"] = {"state": "DATA" if base.get("hasData") else "EMPTY"}
    except AppException:
        # 权限/租户/校验类错误是硬边界（如非学生调用应 403），必须原样冒泡成真实
        # HTTP 错误响应，不能降级成 200 + "ERROR" 分区——那会把拒绝访问伪装成
        # "系统暂时不可用"，是比原样报错更危险的假象。
        raise
    except Exception:
        base = {}
        sections["core"] = {"state": "ERROR"}

    try:
        todos, todo_total = _todo_items(user)
        sections["todo"] = {"state": "DATA" if todos else "EMPTY"}
    except AppException:
        raise
    except Exception:
        todos, todo_total = [], None
        sections["todo"] = {"state": "ERROR"}

    try:
        notices, msg_counts = _notice_items(user)
        sections["message"] = {"state": "DATA" if notices else "EMPTY"}
    except AppException:
        raise
    except Exception:
        notices, msg_counts = [], None
        sections["message"] = {"state": "ERROR"}

    try:
        cfg = portal_cfg.get_config(_tid())
        quick_services = _quick_services(cfg.get("modules") or {})
    except Exception:
        quick_services = []

    student = base.get("student")
    stage = base.get("stage")
    alerts = base.get("alerts") or []
    domains = base.get("domains") or []
    lifecycle = [{
        "key": d.get("key"),
        "label": d.get("label"),
        "hasData": bool(d.get("hasData")),
        "status": _lifecycle_status(str(d.get("key") or ""), bool(d.get("hasData")), d.get("status")),
    } for d in domains]

    alert_count = len(alerts) if sections["core"]["state"] != "ERROR" else None
    unread_count = None
    if sections["message"]["state"] != "ERROR" and msg_counts is not None:
        unread_count = int(msg_counts.get("unread") or 0)

    try:
        projection_version = freshness.projection_version(user, HOME_PROJECTIONS)
    except Exception:
        projection_version = None

    return {
        "homeVersion": HOME_VERSION,
        "asOf": _utc_now_iso(),
        "projectionVersion": projection_version,
        "sections": sections,
        "student": student,
        "stage": stage,
        "summary": {
            "todoCount": todo_total,
            "unreadCount": unread_count,
            "alertCount": alert_count,
        },
        "nextAction": _next_action(alerts, todos),
        "todos": todos,
        "notices": notices,
        "alerts": alerts,
        "domains": domains,
        "lifecycle": lifecycle,
        "quickServices": quick_services,
        "credits": base.get("credits") or {},
    }
