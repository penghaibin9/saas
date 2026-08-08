"""Stage B / P1-07：统一待办 typed deep-link 合同。

规则：
- 后端根据 todo_type + source_biz_id 生成 routeName/routeParams/query；前端不得再按标题或 todoType 自行猜地址。
- 只有仓库已存在真实详情路由的能力才标 exact=True；没有详情页的能力明确返回可处理列表 exact=False，
  并保留 recordId 供后续页面 focus 合同消费，禁止伪造不存在的详情 URL。
- routeName 是稳定业务路由键；path 是当前端可执行落点。CI/合同测试负责证明 exact 路径存在于正式 route index。
"""
from __future__ import annotations

from typing import Any


# PC 管理端已存在真实详情路由的高频待办。
_PC_EXACT: dict[str, tuple[str, str]] = {
    "RISK_HANDLE": ("studentAffairs.risk.detail", "/admin/student-affairs/risk/{recordId}"),
    "AA_STATUS_APPROVAL": ("academicAffairs.statusChange.detail", "/admin/academic-affairs/status-changes/{recordId}"),
    "GD_PROPOSAL_REVIEW": ("graduation.proposal.detail", "/admin/graduation/proposals/{recordId}"),
    "GD_TOPIC_CHANGE_REVIEW": ("graduation.topicChange.detail", "/admin/graduation/topic-changes/{recordId}"),
    "INTERN_WEEKLY_REVIEW": ("internship.report.detail", "/admin/internship/reports/{recordId}"),
    "INTERN_EXCEPTION_HANDLE": ("internship.exception.detail", "/admin/internship/exceptions/{recordId}"),
}

# 尚无详情路由时，只能落到真实可处理列表；仍下发 recordId，不把列表伪装成详情页。
_PC_LIST: dict[str, tuple[str, str, dict[str, str]]] = {
    "LEAVE_APPROVAL": ("studentAffairs.leave.queue", "/admin/student-affairs/leave", {"status": "PENDING"}),
    "LEAVE_OVERDUE": ("studentAffairs.leave.ledger", "/admin/student-affairs/leave/ledger", {"status": "OVERDUE"}),
    "LEAVE_CANCEL": ("studentAffairs.leave.queue", "/admin/student-affairs/leave", {"status": "CANCEL_PENDING"}),
    "LEAVE_EXTENSION": ("studentAffairs.leave.followup", "/admin/student-affairs/leave/followup", {"status": "PENDING"}),
    "DISCIPLINE_APPROVAL": ("studentAffairs.discipline.queue", "/admin/student-affairs/discipline", {"status": "PENDING"}),
    "DISCIPLINE_REMOVE": ("studentAffairs.discipline.queue", "/admin/student-affairs/discipline", {"status": "REMOVE_PENDING"}),
    "AID_APPROVAL": ("studentAffairs.aid.queue", "/admin/student-affairs/aid", {"status": "PENDING"}),
    "AID_ADJUST": ("studentAffairs.aid.queue", "/admin/student-affairs/aid", {"status": "ADJUST_PENDING"}),
    "FUNDING_APPROVAL": ("studentAffairs.funding.queue", "/admin/student-affairs/funding", {"status": "PENDING"}),
    "AA_SCHEDULE_CHANGE_APPROVAL": ("academicAffairs.scheduleChange.queue", "/admin/academic-affairs/schedule-change/approval", {"status": "PENDING"}),
    "ACAD_WARNING_HANDLE": ("academicAffairs.warning.queue", "/admin/academic-affairs/warnings", {"status": "OPEN"}),
    "AA_GRADE_ENTRY": ("academicAffairs.gradeEntry.queue", "/admin/academic-affairs/grade-entry", {"filter": "pending"}),
    "GD_FINAL_REVIEW": ("graduation.final.queue", "/admin/graduation/finals", {"status": "PENDING"}),
    "GD_DEFENSE_SCORE": ("graduation.defenseScore.queue", "/admin/graduation/defense-grade", {"panel": "defense", "status": "PENDING"}),
    "INTERN_LEAVE_APPROVAL": ("internship.leave.queue", "/admin/internship/leaves", {"status": "PENDING"}),
    "INTERN_VISIT_RECTIFY": ("internship.guidance.queue", "/admin/internship/guidance", {"status": "RECTIFY"}),
    "DORM_TRANSFER": ("studentAffairs.dormTransfer.queue", "/admin/student-affairs/dorm/transfer", {"status": "PENDING"}),
    "DORM_EXCEPTION": ("studentAffairs.dormException.queue", "/admin/student-affairs/dorm/exception", {"status": "PENDING_HANDLE"}),
    "EMPLOYMENT_FOLLOWUP": ("employment.followup.queue", "/admin/employment/followups", {"status": "OPEN"}),
}

# 学生小程序当前真实业务页。query.recordId 用于页面 focus；页面尚未实现 focus 时 exact=False。
_STUDENT_MINI: dict[str, tuple[str, str]] = {
    "LEAVE_APPROVAL": ("student.affairs.leave", "/pages/student/affairs/leave"),
    "LEAVE_OVERDUE": ("student.affairs.leave", "/pages/student/affairs/leave"),
    "LEAVE_CANCEL": ("student.affairs.leave", "/pages/student/affairs/leave"),
    "LEAVE_EXTENSION": ("student.affairs.leave", "/pages/student/affairs/leave"),
    "AID_APPROVAL": ("student.affairs.aid", "/pages/student/affairs/aid"),
    "AID_ADJUST": ("student.affairs.aid", "/pages/student/affairs/aid"),
    "FUNDING_APPROVAL": ("student.affairs.funding", "/pages/student/affairs/funding"),
    "DISCIPLINE_APPROVAL": ("student.affairs.discipline", "/pages/student/affairs/discipline"),
    "DISCIPLINE_REMOVE": ("student.affairs.discipline", "/pages/student/affairs/discipline"),
    "ACAD_WARNING_HANDLE": ("student.academic.overview", "/pages/student/academic-affairs/index"),
    "INTERN_WEEKLY_REVIEW": ("student.internship.overview", "/pages/student/internship/index"),
    "INTERN_LEAVE_APPROVAL": ("student.internship.overview", "/pages/student/internship/index"),
    "INTERN_EXCEPTION_HANDLE": ("student.internship.overview", "/pages/student/internship/index"),
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
                "exact": False,
            }
        return None

    if client == "studentMini":
        target = _STUDENT_MINI.get(type_code)
        if not target:
            return None
        route_name, path = target
        return {
            "routeName": route_name,
            "routeParams": {"recordId": rid},
            "query": {"recordId": rid},
            "path": path,
            "exact": False,
        }

    return None


def route_contract_snapshot() -> dict[str, dict[str, Any]]:
    """供 CI/合同测试枚举，防新增 todoType 后又回到前端猜路由。"""
    return {
        "pcExact": {key: {"routeName": value[0], "pathTemplate": value[1]} for key, value in _PC_EXACT.items()},
        "pcList": {key: {"routeName": value[0], "path": value[1]} for key, value in _PC_LIST.items()},
        "studentMini": {key: {"routeName": value[0], "path": value[1]} for key, value in _STUDENT_MINI.items()},
    }
