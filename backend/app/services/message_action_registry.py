"""消息深链注册表：只允许登记过的 actionKey + 参数 schema。

四端根据同一 key 映射本地路由；未登记 key 拒绝入库。
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.exceptions import AppException

# actionKey → 允许角色提示、必需参数、各端路由提示
ACTION_REGISTRY: dict[str, dict[str, Any]] = {
    "student.leave.detail": {
        "roles": ["STUDENT", "COUNSELOR", "STAFF"],
        "requiredParams": ["leaveId"],
        "pc": "/admin/campus-service/leave",
        "studentPc": "/leave",
        "studentMini": "/pages/student/my-applications/index",
        "teacherMini": "/pages/teacher/approvals/index",
        "label": "请假详情",
    },
    "teacher.internship.risk": {
        "roles": ["TEACHER", "COUNSELOR", "STAFF"],
        "requiredParams": ["riskId"],
        "pc": "/admin/internship/risk",
        "studentPc": None,
        "studentMini": None,
        "teacherMini": "/pages/teacher/risk-students/index",
        "label": "实习风险处置",
    },
    "student.exam.detail": {
        "roles": ["STUDENT"],
        "requiredParams": ["examId"],
        "pc": None,
        "studentPc": "/exams",
        "studentMini": "/pages/student/campus-service/index",
        "teacherMini": None,
        "label": "考试详情",
    },
    "teacher.grad.defense": {
        "roles": ["TEACHER", "STAFF"],
        "requiredParams": ["defenseId"],
        "pc": "/admin/graduation/defense",
        "studentPc": None,
        "studentMini": None,
        "teacherMini": "/pages/teacher/graduation-guide/index",
        "label": "答辩安排",
    },
    "message.detail": {
        "roles": ["STUDENT", "TEACHER", "STAFF"],
        "requiredParams": ["messageId"],
        "pc": "/admin/messages/inbox",
        "studentPc": "/messages",
        "studentMini": "/pages/common/message-detail/index",
        "teacherMini": "/pages/common/message-detail/index",
        "label": "消息详情",
    },
    "student.warning.detail": {
        "roles": ["STUDENT", "COUNSELOR", "STAFF"],
        "requiredParams": ["warningId"],
        "pc": "/admin/academic/warnings",
        "studentPc": "/warnings",
        "studentMini": "/pages/student/campus-service/index",
        "teacherMini": "/pages/teacher/risk-students/index",
        "label": "学业预警",
    },
}


def list_action_keys() -> list[dict]:
    return [
        {
            "actionKey": k,
            "label": v.get("label"),
            "requiredParams": v.get("requiredParams") or [],
            "roles": v.get("roles") or [],
            "routes": {
                "pc": v.get("pc"),
                "studentPc": v.get("studentPc"),
                "studentMini": v.get("studentMini"),
                "teacherMini": v.get("teacherMini"),
            },
        }
        for k, v in sorted(ACTION_REGISTRY.items())
    ]


def validate_action(action_key: Optional[str], action_params: Optional[dict]) -> tuple[str | None, dict | None]:
    """校验并规范化；空 key 允许（无深链）。非法 key/缺参抛 422。"""
    key = (action_key or "").strip()
    if not key:
        return None, None
    if key not in ACTION_REGISTRY:
        raise AppException(
            "MESSAGE_ACTION_NOT_ALLOWED",
            f"未登记的深链 actionKey：{key}",
            http_status=422,
            details={"actionKey": key},
        )
    spec = ACTION_REGISTRY[key]
    params = dict(action_params or {})
    missing = [p for p in (spec.get("requiredParams") or []) if params.get(p) in (None, "")]
    if missing:
        raise AppException(
            "VALIDATION_ERROR",
            f"深链缺少参数：{', '.join(missing)}",
            http_status=422,
            details={"missing": missing, "actionKey": key},
        )
    # 只保留登记参数 + 透传已知字段
    allowed = set(spec.get("requiredParams") or []) | {"campaignId", "ackDeadline"}
    cleaned = {k: v for k, v in params.items() if k in allowed or k in (spec.get("requiredParams") or [])}
    for p in spec.get("requiredParams") or []:
        cleaned[p] = params[p]
    return key, cleaned


def resolve_route(action_key: str, *, client: str) -> dict:
    """client: pc | studentPc | studentMini | teacherMini"""
    spec = ACTION_REGISTRY.get(action_key)
    if not spec:
        return {"ok": False, "message": "请前往对应端办理", "path": None}
    path = spec.get(client)
    if not path:
        return {
            "ok": False,
            "message": "当前端暂无对应页面，请前往教师 PC / 学生 PC 办理",
            "path": None,
            "label": spec.get("label"),
        }
    return {"ok": True, "path": path, "label": spec.get("label")}
