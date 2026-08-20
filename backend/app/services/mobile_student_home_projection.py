"""V3 §5.2–§5.4 学生首页 V3 投影。

为什么单独一个文件：``mobile_student_service`` 已经 2300+ 行，继续往里塞聚合逻辑只会让
身份解析、缓存、业务读取搅在一起。这里只做 **投影**——

- 复用 :mod:`app.services.message_center_service` 的本人可见性与消息读取（V3 深审 P1-11：
  禁止再复制一套 receiver 判定）；
- 复用 :mod:`app.services.workbench_todo_service` 的 typed todo reader（同上，禁止把
  sourceModule/title 转成裸 route）；
- 复用 :mod:`app.services.mobile_action_service` 把每条待办/消息归一成 MobileAction；
- 不复制课程/请假/毕设状态机，不新建任何业务事实表。

首页只消费 canonical server truth：拿不到真值就返回 ``None``，由前端显示“—”，
绝不用 0、100% 或 mock 骨架冒充（V3 §5.1）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.student_lifecycle import STUDENT_LIFECYCLE_STAGES, student_stage_label
from app.services import message_center_service as message_svc
from app.services import mobile_action_service as action_svc
from app.services import mobile_freshness_service as freshness
from app.services import workbench_todo_service as todo_svc

#: 首页 DTO schema 版本。结构变化时 +1，并进入缓存 key，避免灰度期读到旧结构。
HOME_VERSION = 2

#: §5.1 首屏各区块条数上限——首页是“下一步该做什么”，不是全量列表。
TODAY_LIMIT = 3
TODO_LIMIT = 3
NOTICE_LIMIT = 3
BLOCKER_LIMIT = 2
QUICK_SERVICE_LIMIT = 8

#: 首页参与的投影域（§5.4）。
HOME_PROJECTIONS = ("todo", "message", "schedule", "grade", "internship", "graduation", "case")


# ── §4.3 Service Entry Registry ────────────────────────────────────────────
# 只登记真实存在、且学生自己能办的入口。SELECTION 故意缺席：Academic 选课尚未进入
# latest main（见 miniapp/docs/miniapp-v3-s0-freeze.json 的 GATE-146-SELECTION），
# 在它真正合入前不得下发入口，否则就是给学生一个点不动的按钮。
SERVICE_ENTRIES: tuple[dict[str, Any], ...] = (
    {"key": "LEAVE", "label": "请假", "icon": "假", "path": "/pages/student/affairs/leave",
     "stages": ("ENROLLED", "GRADUATING", "INTERN")},
    {"key": "AID", "label": "困难认定", "icon": "困", "path": "/pages/student/affairs/aid",
     "stages": ("ENROLLED", "GRADUATING", "INTERN")},
    {"key": "FUNDING", "label": "奖助申请", "icon": "助", "path": "/pages/student/affairs/funding",
     "stages": ("ENROLLED", "GRADUATING", "INTERN")},
    {"key": "EXAM_DEFER", "label": "缓考申请", "icon": "考", "path": "/pages/student/academic-affairs/exam",
     "stages": ("ENROLLED", "GRADUATING")},
    {"key": "SCHEDULE", "label": "我的课表", "icon": "课", "path": "/pages/student/academic-affairs/schedule",
     "stages": ("ENROLLED", "GRADUATING")},
    {"key": "ORIENTATION", "label": "迎新报到", "icon": "迎", "path": "/pages/student/orientation/index",
     "stages": ("ADMITTED", "PRE_STUDENT_VERIFIED", "REGISTERED_PENDING_ENROLLMENT")},
    {"key": "INTERNSHIP", "label": "岗位实习", "icon": "习", "path": "/pages/student/internship/index",
     "stages": ("INTERN", "GRADUATING")},
    {"key": "GRADUATION", "label": "毕业设计", "icon": "毕", "path": "/pages/student/graduation/index",
     "stages": ("GRADUATING", "INTERN")},
    {"key": "GENERIC_SERVICE", "label": "服务申请", "icon": "服", "path": "/pages/student/service-apply/index",
     "stages": ()},  # 空 stages = 所有阶段可见
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stage_progress(stage_code: str | None) -> int | None:
    """阶段进度 = 当前阶段在生命周期序列中的位置。

    这是一个明确定义的派生投影，不是编造的百分比：口径写在这里，
    阶段值不在 STUDENT_LIFECYCLE_STAGES 里就返回 None，让前端显示“—”。
    """
    code = str(stage_code or "").strip().upper()
    if code not in STUDENT_LIFECYCLE_STAGES:
        return None
    index = STUDENT_LIFECYCLE_STAGES.index(code)
    return int(round((index + 1) / len(STUDENT_LIFECYCLE_STAGES) * 100))


def _credit_rate(earned: float | None, required: float | None) -> int | None:
    """学分完成率。培养方案未解析（required=None）时必须返回 None，不得按 0 或 100 猜。"""
    if earned is None or required is None:
        return None
    try:
        required_value = float(required)
        if required_value <= 0:
            return None
        return max(0, min(100, int(round(float(earned) / required_value * 100))))
    except (TypeError, ValueError):
        return None


def _service_entry_action(entry: dict[str, Any]) -> dict[str, Any]:
    """常用服务是固定入口，不指向具体对象，因此 focusMode 恒为 NONE。"""
    return {
        "sourceBizType": f"service-entry:{entry['key']}",
        "sourceBizId": None,
        "recordId": None,
        "target": {
            "client": action_svc.CLIENT_STUDENT_MINI,
            "path": entry["path"],
            "query": {},
            "routeName": f"service-entry:{entry['key']}",
            "focusMode": "NONE",
            "focusParam": None,
            "routeExact": False,
        },
        "allowedActions": ["OPEN"],
        "expectedVersion": None,
        "focusMode": "NONE",
        "label": entry["label"],
        "disabledReason": None,
    }


def quick_services(stage_code: str | None) -> list[dict[str, Any]]:
    """按当前阶段过滤常用服务（§5.1）。"""
    code = str(stage_code or "").strip().upper()
    rows = []
    for entry in SERVICE_ENTRIES:
        stages = entry["stages"]
        if stages and code and code not in stages:
            continue
        rows.append({
            "key": entry["key"],
            "label": entry["label"],
            "icon": entry["icon"],
            "action": _service_entry_action(entry),
        })
        if len(rows) >= QUICK_SERVICE_LIMIT:
            break
    return rows


def _todo_rows(user: dict) -> tuple[list[dict[str, Any]], int]:
    """复用 typed todo reader；不在这里重新判定可见性，也不猜路由。"""
    rows, total = todo_svc.list_todos(
        user, status="PENDING", page=1, page_size=TODO_LIMIT, client="studentMini"
    )
    items = []
    for row in rows:
        items.append({
            "id": str(row.get("todoId") or ""),
            "todoType": row.get("todoType"),
            "title": row.get("title") or "待办事项",
            "module": row.get("sourceModule") or "待办",
            "deadline": row.get("dueAt"),
            "status": row.get("status") or "PENDING",
            "priority": row.get("priority") or "NORMAL",
            "action": action_svc.build_todo_action(row, client=action_svc.CLIENT_STUDENT_MINI),
        })
    return items, int(total or 0)


def _notice_rows(user: dict) -> tuple[list[dict[str, Any]], int]:
    """复用 message_center 的本人可见性与排序，不再自建 receiver 过滤。"""
    rows, _ = message_svc.list_messages(user, page=1, page_size=NOTICE_LIMIT)
    counts = message_svc.count_messages(user)
    items = []
    for row in rows:
        withdrawn = bool(row.get("withdrawn"))
        items.append({
            "id": str(row.get("messageId") or ""),
            "messageId": str(row.get("messageId") or ""),
            "title": row.get("title") or "",
            "source": row.get("senderOrgName") or row.get("category") or "校园通知",
            "important": bool(row.get("emergency")) or str(row.get("priority") or "").upper() == "IMPORTANT",
            "requireAck": bool(row.get("requireAck")),
            "acked": bool(row.get("acked")),
            "withdrawn": withdrawn,
            "time": row.get("createdAt"),
            "action": action_svc.build_message_action(
                row.get("actionKey"), row.get("actionParams"),
                client=action_svc.CLIENT_STUDENT_MINI, withdrawn=withdrawn,
            ),
        })
    return items, int(counts.get("unread") or 0)


def _blocker_rows(alerts: list[dict[str, Any]] | None, todos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """阻断项：每条自己带 action，不再统一丢去 my-applications（§5.1）。

    alerts 来自 me_overview 的跨域告警（学业预警 / 报到卡点），它们本身没有 typed action；
    能不能处理由对应待办决定，所以这里只在同域待办里找 action，找不到就明确禁用。
    """
    by_module: dict[str, dict[str, Any]] = {}
    for todo in todos:
        module = str(todo.get("module") or "").lower()
        if module and module not in by_module:
            by_module[module] = todo
    rows = []
    for index, alert in enumerate(alerts or []):
        domain = str(alert.get("domain") or "").lower()
        matched = by_module.get(domain)
        action = matched.get("action") if matched else None
        if action is None:
            action = {
                "sourceBizType": f"alert:{domain or 'unknown'}",
                "sourceBizId": None, "recordId": None, "target": None,
                "allowedActions": [], "expectedVersion": None, "focusMode": "NONE",
                "label": None,
                "disabledReason": "该提醒暂无可直接办理的入口，请留意后续通知",
            }
        rows.append({
            "id": alert.get("domain") or f"alert-{index}",
            "title": alert.get("title") or "有事项需要处理",
            "reason": alert.get("title") or "",
            "level": alert.get("level") or "MEDIUM",
            "action": action,
        })
        if len(rows) >= BLOCKER_LIMIT:
            break
    return rows


def _next_action(blockers: list[dict[str, Any]], todos: list[dict[str, Any]]) -> dict[str, Any] | None:
    """“下一步该做什么”：优先阻断项，其次最紧的待办。

    §5.1：第一优先卡只接 action，不接裸 route——拿不到可执行 action 就不出这张卡，
    而不是给一个指向大厅的假按钮。
    """
    for candidate in blockers:
        action = candidate.get("action")
        if action and action.get("target"):
            return action
    for todo in todos:
        action = todo.get("action")
        if action and action.get("target"):
            return action
    return None


def build_home_v2(user: dict, *, overview: dict[str, Any], credits: dict[str, Any] | None = None,
                  today: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """在既有 overview 之上叠加 V3 首页投影。

    ``overview`` 由 mobile_student_service.me_overview() 提供（身份解析与跨域状态仍归它管），
    本函数只负责把它投影成 §5.2 的 DTO，并补齐 action / 阶段进度 / 学分完成率 / 常用服务。
    """
    student = (overview or {}).get("student") or {}
    stage = (overview or {}).get("stage") or {}
    stage_code = stage.get("code") or student.get("stage")

    todos, todo_total = _todo_rows(user)
    notices, unread = _notice_rows(user)
    blockers = _blocker_rows((overview or {}).get("alerts"), todos)

    credits = credits or {}
    return {
        "homeVersion": HOME_VERSION,
        "asOf": _utc_now_iso(),
        "projectionVersion": freshness.projection_version(user, HOME_PROJECTIONS),
        "stage": {
            "code": stage_code,
            "label": stage.get("label") or student_stage_label(stage_code),
        },
        "summary": {
            # 真值拿不到就是 None，前端显示“—”，不允许 0/100 冒充（§5.1）。
            "stageProgress": _stage_progress(stage_code),
            "todoCount": todo_total,
            "unreadCount": unread,
            "creditRate": _credit_rate(credits.get("earnedCredits"), credits.get("requiredCredits")),
        },
        "nextAction": _next_action(blockers, todos),
        "today": list(today or [])[:TODAY_LIMIT],
        "blockers": blockers,
        "quickServices": quick_services(stage_code),
        "todos": todos,
        "notices": notices,
    }


def home_projection_snapshot() -> dict[str, Any]:
    """供 CI/合同测试枚举。"""
    return {
        "homeVersion": HOME_VERSION,
        "limits": {
            "today": TODAY_LIMIT, "todos": TODO_LIMIT,
            "notices": NOTICE_LIMIT, "blockers": BLOCKER_LIMIT,
            "quickServices": QUICK_SERVICE_LIMIT,
        },
        "serviceEntries": [
            {"key": e["key"], "path": e["path"], "stages": list(e["stages"])} for e in SERVICE_ENTRIES
        ],
        "projections": list(HOME_PROJECTIONS),
    }
