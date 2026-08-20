"""Stage B / P1-07：统一待办 typed deep-link 合同。

规则：
- 后端根据 todo_type + source_biz_id 生成 routeName/routeParams/query；前端不得再按标题或 todoType 自行猜地址。
- 只有仓库已存在真实详情路由的能力才标 exact=True；没有详情页的能力明确返回可处理列表 exact=False，
  并保留 recordId 供后续页面 focus 合同消费，禁止伪造不存在的详情 URL。
- routeName 是稳定业务路由键，不使用 `studentAffairs.xxx` 等权限命名空间，避免与 permission code 混淆；
  path 是当前端可执行落点。CI/合同测试负责证明 exact 路径存在于正式 route index。
"""
from __future__ import annotations

from typing import Any

from app.services.mobile_focus_contract import (
    FOCUS_DETAIL,
    FOCUS_LIST_FOCUS,
    FOCUS_NONE,
    is_route_exact,
)


# PC 管理端已存在真实详情路由的高频待办。
_PC_EXACT: dict[str, tuple[str, str]] = {
    "RISK_HANDLE": ("todo-route:student-affairs-risk-detail", "/admin/student-affairs/risk/{recordId}"),
    "AA_STATUS_APPROVAL": ("todo-route:academic-status-change-detail", "/admin/academic-affairs/status-changes/{recordId}"),
    "GD_PROPOSAL_REVIEW": ("todo-route:graduation-proposal-detail", "/admin/graduation/proposals/{recordId}"),
    "GD_TOPIC_CHANGE_REVIEW": ("todo-route:graduation-topic-change-detail", "/admin/graduation/topic-changes/{recordId}"),
    "INTERN_WEEKLY_REVIEW": ("todo-route:internship-report-detail", "/admin/internship/reports/{recordId}"),
    "INTERN_EXCEPTION_HANDLE": ("todo-route:internship-exception-detail", "/admin/internship/exceptions/{recordId}"),
}

# 尚无详情路由时，只能落到真实可处理列表；仍下发 recordId，不把列表伪装成详情页。
_PC_LIST: dict[str, tuple[str, str, dict[str, str]]] = {
    "LEAVE_APPROVAL": ("todo-route:student-affairs-leave-queue", "/admin/student-affairs/leave", {"status": "PENDING"}),
    "LEAVE_OVERDUE": ("todo-route:student-affairs-leave-ledger", "/admin/student-affairs/leave/ledger", {"status": "OVERDUE"}),
    "LEAVE_CANCEL": ("todo-route:student-affairs-leave-queue", "/admin/student-affairs/leave", {"status": "CANCEL_PENDING"}),
    "LEAVE_EXTENSION": ("todo-route:student-affairs-leave-followup", "/admin/student-affairs/leave/followup", {"status": "PENDING"}),
    "DISCIPLINE_APPROVAL": ("todo-route:student-affairs-discipline-queue", "/admin/student-affairs/discipline", {"status": "PENDING"}),
    "DISCIPLINE_REMOVE": ("todo-route:student-affairs-discipline-queue", "/admin/student-affairs/discipline", {"status": "REMOVE_PENDING"}),
    "AID_APPROVAL": ("todo-route:student-affairs-aid-queue", "/admin/student-affairs/aid", {"status": "PENDING"}),
    "AID_ADJUST": ("todo-route:student-affairs-aid-queue", "/admin/student-affairs/aid", {"status": "ADJUST_PENDING"}),
    "FUNDING_APPROVAL": ("todo-route:student-affairs-funding-queue", "/admin/student-affairs/funding", {"status": "PENDING"}),
    "AA_SCHEDULE_CHANGE_APPROVAL": ("todo-route:academic-schedule-change-queue", "/admin/academic-affairs/schedule-change/approval", {"status": "PENDING"}),
    "ACAD_WARNING_HANDLE": ("todo-route:academic-warning-queue", "/admin/academic-affairs/warnings", {"status": "OPEN"}),
    "AA_GRADE_ENTRY": ("todo-route:academic-grade-entry-queue", "/admin/academic-affairs/grade-entry", {"filter": "pending"}),
    "GD_FINAL_REVIEW": ("todo-route:graduation-final-queue", "/admin/graduation/finals", {"status": "PENDING"}),
    "GD_DEFENSE_SCORE": ("todo-route:graduation-defense-score-queue", "/admin/graduation/defense-grade", {"panel": "defense", "status": "PENDING"}),
    "INTERN_LEAVE_APPROVAL": ("todo-route:internship-leave-queue", "/admin/internship/leaves", {"status": "PENDING"}),
    "INTERN_VISIT_RECTIFY": ("todo-route:internship-guidance-queue", "/admin/internship/guidance", {"status": "RECTIFY"}),
    "DORM_TRANSFER": ("todo-route:student-affairs-dorm-transfer-queue", "/admin/student-affairs/dorm/transfer", {"status": "PENDING"}),
    "DORM_EXCEPTION": ("todo-route:student-affairs-dorm-exception-queue", "/admin/student-affairs/dorm/exception", {"status": "PENDING_HANDLE"}),
    "EMPLOYMENT_FOLLOWUP": ("todo-route:employment-followup-queue", "/admin/employment/followups", {"status": "OPEN"}),
}

# 学生小程序当前真实业务页。query.recordId 用于页面 focus。
# V3 §4.4：第三项是 focusMode——页面真的会读 recordId 定位对象才写 LIST_FOCUS，
# 只是个安全入口就写 NONE；exact 由 mobile_focus_contract.is_route_exact() 统一判定，
# 不再由本表自行宣称。
_STUDENT_MINI: dict[str, tuple[str, str, str]] = {
    "LEAVE_APPROVAL": ("todo-route:student-mini-leave", "/pages/student/affairs/leave", FOCUS_LIST_FOCUS),
    "LEAVE_OVERDUE": ("todo-route:student-mini-leave", "/pages/student/affairs/leave", FOCUS_LIST_FOCUS),
    "LEAVE_CANCEL": ("todo-route:student-mini-leave", "/pages/student/affairs/leave", FOCUS_LIST_FOCUS),
    "LEAVE_EXTENSION": ("todo-route:student-mini-leave", "/pages/student/affairs/leave", FOCUS_LIST_FOCUS),
    "AID_APPROVAL": ("todo-route:student-mini-aid", "/pages/student/affairs/aid", FOCUS_LIST_FOCUS),
    "AID_ADJUST": ("todo-route:student-mini-aid", "/pages/student/affairs/aid", FOCUS_LIST_FOCUS),
    "FUNDING_APPROVAL": ("todo-route:student-mini-funding", "/pages/student/affairs/funding", FOCUS_LIST_FOCUS),
    "DISCIPLINE_APPROVAL": ("todo-route:student-mini-discipline", "/pages/student/affairs/discipline", FOCUS_NONE),
    "DISCIPLINE_REMOVE": ("todo-route:student-mini-discipline", "/pages/student/affairs/discipline", FOCUS_NONE),
    "ACAD_WARNING_HANDLE": ("todo-route:student-mini-academic-warning", "/pages/student/academic-affairs/warning", FOCUS_NONE),
    "INTERN_WEEKLY_REVIEW": ("todo-route:student-mini-internship", "/pages/student/internship/index", FOCUS_NONE),
    "INTERN_LEAVE_APPROVAL": ("todo-route:student-mini-internship", "/pages/student/internship/index", FOCUS_NONE),
    "INTERN_EXCEPTION_HANDLE": ("todo-route:student-mini-internship", "/pages/student/internship/index", FOCUS_NONE),
}


def _record_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def resolve_todo_route(todo_type: str | None, record_id: Any, *, client: str) -> dict | None:
    """返回统一 typed route；无法证明真实落点时返回 None，而不是猜 URL。"""
    type_code = str(todo_type or "").strip().upper()
    rid = _record_id(record_id)
    if not type_code or not rid:
        return None

    if client == "pc":
        exact = _PC_EXACT.get(type_code)
        if exact:
            route_name, template = exact
            params = {"recordId": rid}
            return {
                "routeName": route_name,
                "routeParams": params,
                "query": {},
                "path": template.format(**params),
                "focusMode": FOCUS_DETAIL,
                "exact": True,
            }
        fallback = _PC_LIST.get(type_code)
        if fallback:
            route_name, path, query = fallback
            return {
                "routeName": route_name,
                "routeParams": {"recordId": rid},
                "query": {**query, "recordId": rid},
                "path": path,
                "focusMode": FOCUS_NONE,
                "exact": False,
            }
        return None

    if client == "studentMini":
        target = _STUDENT_MINI.get(type_code)
        if not target:
            return None
        route_name, path, focus_mode = target
        return {
            "routeName": route_name,
            "routeParams": {"recordId": rid},
            "query": {"recordId": rid},
            "path": path,
            "focusMode": focus_mode,
            "exact": is_route_exact(focus_mode, path),
        }

    return None


def route_contract_snapshot() -> dict[str, dict[str, Any]]:
    """供 CI/合同测试枚举，防新增 todoType 后又回到前端猜路由。"""
    return {
        "pcExact": {key: {"routeName": value[0], "pathTemplate": value[1]} for key, value in _PC_EXACT.items()},
        "pcList": {key: {"routeName": value[0], "path": value[1]} for key, value in _PC_LIST.items()},
        "studentMini": {
            key: {
                "routeName": value[0],
                "path": value[1],
                "focusMode": value[2],
                "exact": is_route_exact(value[2], value[1]),
            }
            for key, value in _STUDENT_MINI.items()
        },
    }
