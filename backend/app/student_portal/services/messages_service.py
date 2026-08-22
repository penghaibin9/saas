"""学生 PC 门户 · 消息通知 PC 视图（V3 施工手册 SP-M01/M02/M04/M05/M06/M07/M08）。

V3 深审发现：以前这里叫 ``stu.my_messages()`` 拿到一份最多 30+40+10 条的合并列表，
再在 Python 里对这个已经被硬编码 LIMIT 截断过的列表做分页——数据量一旦超过那个上限，
更早的通知/待办/进度记录会静默永久不可见，而不只是"分页慢"。

修法与学生小程序的 :func:`app.services.mobile_performance_service.student_messages_page`
对称：待办/通知/服务进度是三个不同的业务 Authority，各自独立做真实数据库分页，
不再合并成一份"消息列表"再切片：

- 待办 tab  → :func:`app.services.workbench_todo_service.list_todos`（typed reader；仅 PENDING）
- 通知 tab  → :func:`app.services.message_center_service.list_messages`（本人可见性 Authority）
- 进度 tab  → 复用 :func:`app.services.mobile_performance_service._progress_page`
              （CsLeave/CsWorkOrder 真实 UNION 分页；不重写第二份服务进度查询）

三个 tab 分别有自己的"已读/待处理"语义（SP-M07）："全部已读"只影响通知 Authority
（UnifiedMessage），不改写待办/进度的业务状态。

typed action 一律走 :mod:`app.student_portal.services.action_projection_service`
（client=studentPc），不在这里另建 actionKey/todoType → 路由的第二份映射表。
撤回/过期消息在列表和详情都必须投影为不可导航；详情是点击前最新事实，前端不得继续
沿用列表旧快照中的 action。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import message_center_service as message_svc
from app.services import mobile_performance_service as mini_perf
from app.services import mobile_student_service as stu
from app.services import notification_preference_service as notify_pref
from app.services import workbench_todo_service as todo_svc
from app.student_portal.services import action_projection_service as action_proj

_TABS = ("todo", "notice", "progress")


def _todo_item(row: dict) -> dict:
    pending = str(row.get("status") or "").upper() == "PENDING"
    return {
        "id": f"todo-{row.get('todoId')}",
        "messageId": None,
        "kind": "TODO_AGG",
        "title": row.get("title") or "待办事项",
        "module": row.get("sourceModule") or "待办",
        "level": "high" if row.get("priority") == "HIGH" else "normal",
        "time": row.get("createdAt"),
        "deadline": row.get("dueAt"),
        "read": not pending,
        "status": row.get("status"),
        "action": action_proj.build_todo_action(row),
    }


def _notice_item(row: dict) -> dict:
    emergency = bool(row.get("emergency"))
    withdrawn = bool(row.get("withdrawn"))
    expired = bool(row.get("expired"))
    return {
        "id": str(row.get("messageId") or ""),
        "messageId": str(row.get("messageId") or ""),
        "kind": "UNIFIED_MESSAGE",
        "title": row.get("title") or "",
        "content": row.get("summary") or "",
        "module": row.get("category") or row.get("msgType") or "通知",
        "level": "high" if emergency else "normal",
        "time": row.get("createdAt"),
        "deadline": row.get("expireAt"),
        "read": str(row.get("readStatus") or "").upper() == "READ",
        "status": row.get("readStatus"),
        "emergency": emergency,
        "receipt": bool(row.get("requireAck") and not row.get("acked") and not withdrawn and not expired),
        "requireAck": bool(row.get("requireAck")),
        "acked": bool(row.get("acked")),
        "withdrawn": withdrawn,
        "expired": expired,
        "contentVersion": row.get("contentVersion"),
        "action": action_proj.build_message_action(
            row.get("actionKey"), row.get("actionParams"),
            withdrawn=withdrawn, expired=expired,
        ),
    }


def _progress_item(row: dict) -> dict:
    # mobile_performance_service._progress_page 已经产出统一 shape；PC 只补一个
    # 安全但不假装对象聚焦的 action——服务进度当前没有独立详情页，只能落到
    # 在校服务大厅（focusMode=NONE，不假装能定位到具体那条请假/工单）。
    return {
        **row,
        "action": {
            "sourceBizType": "campus-service-progress",
            "sourceBizId": None,
            "recordId": None,
            "target": {
                "client": action_proj.CLIENT_STUDENT_PC,
                "path": "/campus-service",
                "query": {},
                "routeName": "campus-service-progress",
                "focusMode": "NONE",
                "focusParam": None,
                "routeExact": False,
            },
            "allowedActions": ["OPEN"],
            "expectedVersion": None,
            "focusMode": "NONE",
            "label": "服务进度",
            "disabledReason": None,
        },
    }


def inbox_page(user: dict, tab: str = "todo", page: int = 1, page_size: int = 20) -> dict:
    """三 tab 三 Authority 的真实数据库分页（SP-M05/M07）。

    router.py 明确"不挂 require_staff 门禁，由服务层 _require_student 收口"——
    本函数底层复用的 message_center_service/workbench_todo_service 对非学生
    调用者并不天然拒绝（它们同时服务教师/管理端工作台），必须在这里显式收口，
    否则非学生角色会拿到 200（内容多半是空的，但边界本身就是错的）。
    """
    stu._require_student(user)
    key = str(tab or "todo").strip().lower()
    if key not in _TABS:
        raise AppException("VALIDATION_ERROR", "tab 必须是 todo/notice/progress")
    try:
        page = max(1, int(page))
        page_size = min(50, max(1, int(page_size)))
    except (TypeError, ValueError):
        page, page_size = 1, 20

    enabled = notify_pref.enabled_categories(user, list(_TABS))

    if key not in enabled:
        items, total = [], 0
    elif key == "todo":
        # P2-01："待办" tab 与 badge 使用同一个 PENDING Authority。
        # DONE 是历史完成记录，不得混进待处理列表导致 tab total 与 badge 数字分叉。
        rows, total = todo_svc.list_todos(
            user, status="PENDING", page=page, page_size=page_size,
            client=action_proj.CLIENT_STUDENT_PC,
        )
        items = [_todo_item(row) for row in rows]
    elif key == "notice":
        rows, total = message_svc.list_messages(user, page=page, page_size=page_size)
        items = [_notice_item(row) for row in rows]
    else:
        rows, total, _unread = mini_perf._progress_page(user, page, page_size)
        items = [_progress_item(row) for row in rows]

    pending_total = todo_svc.list_todos(user, status="PENDING", page=1, page_size=1)[1] if "todo" in enabled else 0
    message_counts = message_svc.count_messages(user) if "notice" in enabled else {}
    _, _, progress_unread = mini_perf._progress_page(user, 1, 1) if "progress" in enabled else ([], 0, 0)

    badges = {
        "todo": int(pending_total or 0),
        "notice": int(message_counts.get("unread") or 0),
        "progress": int(progress_unread or 0),
    }

    emergency = []
    if "notice" in enabled:
        rows, _ = message_svc.list_messages(
            user, priority="EMERGENCY", pending_ack=True, page=1, page_size=5
        )
        emergency = [_notice_item(row) for row in rows]

    return {
        "tabs": [
            {"key": "todo", "label": "待办", "badge": badges["todo"]},
            {"key": "notice", "label": "通知", "badge": badges["notice"]},
            {"key": "progress", "label": "服务进度", "badge": badges["progress"]},
        ],
        "tab": key,
        "list": items,
        "page": page,
        "pageSize": page_size,
        "total": int(total),
        "hasMore": page * page_size < int(total),
        "emergencyPending": emergency,
    }


def get_detail(user: dict, message_id: str) -> dict:
    """PC 消息详情 facade（SP-M04/M08）：走 message_center canonical reader。

    详情是点击前最新事实：除原始 actionKey/actionParams 外，还必须重新按当前
    withdrawn/expired 状态投影 action。这样列表加载后消息若被撤回/过期，前端拿到的
    detail.action 会变成 target=None，而不是继续沿用旧列表 action 导航。
    """
    stu._require_student(user)
    detail = message_svc.get_message(user, message_id)
    if detail is None:
        raise AppException("DATA_NOT_FOUND", "消息不存在")
    withdrawn = bool(detail.get("withdrawn"))
    expired = bool(detail.get("expired"))
    return {
        **detail,
        "action": action_proj.build_message_action(
            detail.get("actionKey"), detail.get("actionParams"),
            withdrawn=withdrawn, expired=expired,
        ),
    }


def mark_read(user: dict, message_id) -> dict:
    """标记本人某条消息为已读（非本人 404，不泄露存在性）。"""
    return stu.message_mark_read(user, message_id)


def mark_read_all(user: dict) -> dict:
    """学生 PC 全部已读：仅 UnifiedMessage 本人记录；不改写待办/进度业务状态（SP-M07）。

    SP-M06：主 Authority（message_center.read_all）失败必须真失败，不能吞成
    affectedCount=0 冒充"没有未读"——那会让页面弹出"全部已读"，而真实未读仍然存在。
    只有兼容旧写入（receiver_id 命中但从未回填 receiver_user_id 的历史行）的补偿
    扫描允许部分失败，并如实通过 legacyFailures 上报，不静默吞掉。
    """
    stu._require_student(user)
    result = message_svc.read_all(user)  # 失败原样抛出，不在此处兜底成假成功

    extra = 0
    legacy_failures = 0
    try:
        legacy = stu.my_messages(user)
        for m in legacy.get("list") or []:
            if m.get("kind") in ("TODO_AGG", "PROGRESS_AGG"):
                continue
            mid = str(m.get("messageId") or m.get("id") or "").replace("msg-", "")
            if mid.isdigit() and not m.get("read"):
                try:
                    stu.message_mark_read(user, mid)
                    extra += 1
                except Exception:
                    legacy_failures += 1
    except Exception:
        # 兼容扫描本身依赖的旧聚合读取失败，不影响已经成功的主 Authority 结果。
        pass

    return {
        "affectedCount": int(result.get("affectedCount") or 0) + extra,
        "updatedAt": result.get("updatedAt"),
        "legacyFailures": legacy_failures,
        "partial": legacy_failures > 0,
    }


def ack_receipt(user: dict, message_id) -> dict:
    return stu.message_ack(user, message_id)


def get_preferences(user: dict) -> dict:
    return stu.notify_preferences(user)


def set_preference(user: dict, body: dict) -> dict:
    return stu.notify_set_preference(user, body or {})
