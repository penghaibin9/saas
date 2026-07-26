"""移动端岗位实习前置门。

教师接口逐项登记权限；学生与教师已迁移流程的旧无版本写入口默认拒绝。
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import Header, Request

from app.core.exceptions import AppException, no_permission, unauthorized
from app.core.permissions import enforce_permission
from app.core.security import decode_token

_TEACHER_MARKER = "/mobile/teacher/internship"
_STUDENT_APPLICATION_MARKER = "/mobile/internship/applications"
_STUDENT_LEAVE_MARKER = "/mobile/internship/leave"
_STUDENT_MAKEUP_MARKER = "/mobile/internship/makeup"
_STUDENT_PLAN_MARKER = "/mobile/internship/plan"
_STUDENT_AGREEMENT_MARKER = "/mobile/internship/agreements"

_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("GET", re.compile(r"^$"), "internship.dashboard.view"),
    ("GET", re.compile(r"^context$"), "internship.dashboard.view"),
    ("GET", re.compile(r"^context/scores$"), "internship.score.view"),
    ("GET", re.compile(r"^context/enterprise-evals$"), "internship.eval.enterprise.view"),
    ("POST", re.compile(r"^context/enterprise-evals$"), "internship.eval.enterprise.manage"),
    ("POST", re.compile(r"^context/enterprise-evals/[^/]+/resubmit$"), "internship.eval.enterprise.manage"),
    ("POST", re.compile(r"^context/enterprise-evals/[^/]+/review$"), "internship.eval.enterprise.review"),
    ("GET", re.compile(r"^context/student-evals(?:/[^/]+)?$"), "internship.eval.self.view"),
    ("POST", re.compile(r"^context/student-evals/[^/]+/advisor-comment$"), "internship.eval.advisor.manage"),
    ("POST", re.compile(r"^context/student-evals/[^/]+/review$"), "internship.eval.self.review"),
    ("GET", re.compile(r"^context/makeups$"), "internship.makeup.view"),
    ("POST", re.compile(r"^context/makeups/[^/]+/review$"), "internship.makeup.review"),
    ("GET", re.compile(r"^context/leaves$"), "internship.leave.view"),
    ("GET", re.compile(r"^context/leaves/overdue$"), "internship.leave.view"),
    ("POST", re.compile(r"^context/leaves/[^/]+/review$"), "internship.leave.review"),
    ("POST", re.compile(r"^context/leaves/[^/]+/ack-return$"), "internship.leave.review"),
    ("GET", re.compile(r"^context/process-reports(?:/[^/]+)?$"), "internship.report.view"),
    ("POST", re.compile(r"^context/process-reports/[^/]+/review$"), "internship.report.review"),
    ("GET", re.compile(r"^context/plan-tasks$"), "internship.task.view"),
    ("POST", re.compile(r"^context/plan-tasks/[^/]+/review$"), "internship.task.review"),
    ("GET", re.compile(r"^context/applications$"), "internship.application.view"),
    ("POST", re.compile(r"^context/applications/[^/]+/review$"), "internship.application.review"),
    ("GET", re.compile(r"^visit-plans$"), "internship.visit.view"),
    ("POST", re.compile(r"^visit-plans/record$"), "internship.visit.manage"),
    ("POST", re.compile(r"^weekly/[^/]+/(review|remind)$"), "internship.report.review"),
    ("POST", re.compile(r"^exception/[^/]+/handle$"), "internship.attendance.review"),
    ("GET", re.compile(r"^makeups/pending$"), "internship.makeup.view"),
    ("POST", re.compile(r"^makeups/[^/]+/review$"), "internship.makeup.review"),
    ("GET", re.compile(r"^leaves/(pending|overdue)$"), "internship.leave.view"),
    ("POST", re.compile(r"^leaves/[^/]+/(review|ack-return)$"), "internship.leave.review"),
    ("GET", re.compile(r"^risks$"), "internship.risk.view"),
    ("POST", re.compile(r"^risks/[^/]+/(handle|follow|close)$"), "internship.risk.handle"),
    ("GET", re.compile(r"^my-students$"), "internship.student.view"),
    ("POST", re.compile(r"^guidance$"), "internship.guidance.manage"),
    ("GET", re.compile(r"^student-evals(?:/[^/]+)?$"), "internship.eval.self.view"),
    ("POST", re.compile(r"^student-evals/[^/]+/advisor-comment$"), "internship.eval.advisor.manage"),
    ("POST", re.compile(r"^student-evals/[^/]+/review$"), "internship.eval.self.review"),
    ("GET", re.compile(r"^enterprise-evals$"), "internship.eval.enterprise.view"),
    ("POST", re.compile(r"^enterprise-evals$"), "internship.eval.enterprise.manage"),
    ("POST", re.compile(r"^enterprise-evals/[^/]+/review$"), "internship.eval.enterprise.review"),
    ("GET", re.compile(r"^insurances/pending$"), "internship.insurance.view"),
    ("POST", re.compile(r"^insurances/[^/]+/verify$"), "internship.insurance.verify"),
    ("GET", re.compile(r"^change-requests/pending$"), "internship.change.view"),
    ("POST", re.compile(r"^change-requests/[^/]+/review$"), "internship.change.review"),
    ("GET", re.compile(r"^scores$"), "internship.score.view"),
    ("POST", re.compile(r"^scores/compute$"), "internship.score.manage"),
    ("GET", re.compile(r"^agreements/pending-school$"), "internship.agreement.view"),
    ("GET", re.compile(r"^process-reports(?:/[^/]+)?$"), "internship.report.view"),
    ("POST", re.compile(r"^process-reports/[^/]+/review$"), "internship.report.review"),
    ("GET", re.compile(r"^plan-tasks/pending$"), "internship.task.view"),
    ("POST", re.compile(r"^plan-tasks/[^/]+/review$"), "internship.task.review"),
    ("GET", re.compile(r"^applications/pending$"), "internship.application.view"),
    ("POST", re.compile(r"^applications/[^/]+/review$"), "internship.application.review"),
)


def _legacy_error(label: str) -> None:
    raise AppException(
        "DATA_CONFLICT",
        f"旧版{label}写入口已停用，请刷新客户端后通过当前批次版本化入口办理",
    )


def _reject_legacy_student_write(method: str, path: str) -> None:
    verb = str(method or "").upper()
    if path.startswith(_STUDENT_APPLICATION_MARKER):
        suffix = path[len(_STUDENT_APPLICATION_MARKER):].strip("/")
        if ((verb == "PUT" and not suffix)
                or (verb == "POST" and re.fullmatch(r"[^/]+/(submit|withdraw)", suffix or ""))):
            _legacy_error("正式实习申请")
    if path.startswith(_STUDENT_LEAVE_MARKER):
        suffix = path[len(_STUDENT_LEAVE_MARKER):].strip("/")
        if verb == "POST" and (not suffix or re.fullmatch(r"[^/]+/(withdraw|return)", suffix or "")):
            _legacy_error("请假")
    if path.startswith(_STUDENT_MAKEUP_MARKER):
        suffix = path[len(_STUDENT_MAKEUP_MARKER):].strip("/")
        if verb == "POST" and (not suffix or re.fullmatch(r"[^/]+/withdraw", suffix or "")):
            _legacy_error("补卡")
    if path.startswith(_STUDENT_PLAN_MARKER) and verb == "POST":
        suffix = path[len(_STUDENT_PLAN_MARKER):].strip("/")
        if suffix == "acknowledge" or re.fullmatch(r"tasks/[^/]+/submit", suffix or ""):
            _legacy_error("实习计划")
    if path.startswith(_STUDENT_AGREEMENT_MARKER) and verb == "POST":
        suffix = path[len(_STUDENT_AGREEMENT_MARKER):].strip("/")
        if re.fullmatch(r"[^/]+/confirm", suffix or ""):
            _legacy_error("三方协议确认")


def _reject_legacy_teacher_write(method: str, path: str) -> None:
    if _TEACHER_MARKER not in path or str(method or "").upper() != "POST":
        return
    suffix = path.split(_TEACHER_MARKER, 1)[1].strip("/")
    if re.fullmatch(r"makeups/[^/]+/review", suffix):
        _legacy_error("教师补卡审核")
    if re.fullmatch(r"leaves/[^/]+/review", suffix):
        _legacy_error("教师请假审核")
    if re.fullmatch(r"process-reports/[^/]+/review", suffix):
        _legacy_error("教师过程报告批阅")
    if re.fullmatch(r"plan-tasks/[^/]+/review", suffix):
        _legacy_error("教师计划任务审核")
    if re.fullmatch(r"applications/[^/]+/review", suffix):
        _legacy_error("教师正式实习申请审核")


def resolve_teacher_internship_permission(method: str, path: str) -> str | None:
    if _TEACHER_MARKER not in path:
        return None
    suffix = path.split(_TEACHER_MARKER, 1)[1].strip("/")
    verb = str(method or "").upper()
    for expected_method, pattern, permission in _RULES:
        if verb == expected_method and pattern.fullmatch(suffix):
            return permission
    raise no_permission(
        f"教师移动端岗位实习接口未登记权限规则：{verb} /{suffix or '<root>'}")


def _preflight_user(authorization: Optional[str]) -> dict:
    token = str(authorization or "").strip()
    if token.startswith("Bearer "):
        token = token[7:]
    if not token:
        raise unauthorized("未提供认证令牌")
    claims = decode_token(token)
    from app.core.token_store import jti_blocked
    if jti_blocked(claims.get("jti")):
        raise unauthorized("令牌已登出失效，请重新登录")
    user = {
        "userId": claims.get("userId"), "loginName": claims.get("loginName") or claims.get("username"),
        "realName": claims.get("realName"), "userType": claims.get("userType"),
        "tenantCode": claims.get("tid"), "tenantId": claims.get("tenantId"),
        "activeContextId": claims.get("activeContextId"),
        "currentRoleCode": claims.get("currentRoleCode"),
        "permissionVersion": claims.get("permissionVersion"),
        "studentNo": claims.get("studentNo"), "collegeId": claims.get("collegeId"),
        "collegeIds": claims.get("collegeIds"), "majorId": claims.get("majorId"),
        "majorIds": claims.get("majorIds"), "tokenJti": claims.get("jti"),
        "tokenExp": claims.get("exp"),
    }
    if str(user.get("userId") or "").startswith("db-"):
        from app.services.auth_service_db import validate_token_subject
        validate_token_subject(user)
    return user


def enforce_teacher_internship_mobile_permission(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _reject_legacy_student_write(request.method, request.url.path)
    _reject_legacy_teacher_write(request.method, request.url.path)
    permission = resolve_teacher_internship_permission(request.method, request.url.path)
    if permission is None:
        return None
    user = _preflight_user(authorization)
    enforce_permission(user, permission)
    return user
