"""消息深链注册表：只允许登记过的 actionKey + 参数 schema。

四端根据同一 key 映射本地路由；未登记 key 拒绝入库。
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.exceptions import AppException
from app.services.mobile_focus_contract import (
    FOCUS_DETAIL,
    FOCUS_LIST_FOCUS,
    FOCUS_NONE,
    is_route_exact,
    normalize_focus_mode,
)

# actionKey → 允许角色提示、必需参数、各端路由提示
#
# V3 §4.4：``focus`` 声明该端目标是否真的能落到对象上（DETAIL / LIST_FOCUS / NONE）；
# 缺省视为 NONE。``focusParam`` 指明用哪个 requiredParam 作为聚焦值，缺省用第一个必需参数。
ACTION_REGISTRY: dict[str, dict[str, Any]] = {
    "student.affairs.material": {
        "roles": ["STUDENT", "COUNSELOR", "STAFF"],
        "requiredParams": ["materialRequirementId"],
        "pc": "/admin/student-affairs/material-operations",
        "studentPc": "/materials",
        "studentMini": "/pages/student/affairs/index",
        "teacherMini": "/pages/teacher/affairs/index",
        "focus": {"studentMini": FOCUS_LIST_FOCUS},
        "label": "补交材料",
    },
    "student.leave.detail": {
        "roles": ["STUDENT", "COUNSELOR", "STAFF"],
        "requiredParams": ["leaveId"],
        "pc": "/admin/student-affairs/leave",
        "studentPc": "/leave",
        # V3 §4.3：请假是专用 Authority，深链必须回请假页本身，
        # 不再落到“我的申请”这种通用大厅（旧值 /pages/student/my-applications/index）。
        "studentMini": "/pages/student/affairs/leave",
        # 旧值 /pages/teacher/approvals/index 在 pages.json 里根本不存在（复数拼写），
        # 教师点开这条深链只会得到一个死链。
        "teacherMini": "/pages/teacher/approval/index",
        "focus": {"studentMini": FOCUS_LIST_FOCUS},
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
        # 旧值 /pages/student/campus-service/index 是“在校服务”大厅，跟考试无关；
        # 教务考试页才是真实落点。
        "studentMini": "/pages/student/academic-affairs/exam",
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
        # 消息详情页本身就是按 messageId 打开的对象详情，天然对象级闭环。
        "focus": {"studentMini": FOCUS_DETAIL, "teacherMini": FOCUS_DETAIL},
        "label": "消息详情",
    },
    "student.warning.detail": {
        "roles": ["STUDENT", "COUNSELOR", "STAFF"],
        "requiredParams": ["warningId"],
        "pc": "/admin/academic/warnings",
        "studentPc": "/warnings",
        # 同上：旧值指向“在校服务”大厅，学业预警页才是真实落点。
        "studentMini": "/pages/student/academic-affairs/warning",
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
            "focus": {
                client: focus_mode_for(k, client=client)
                for client in ("pc", "studentPc", "studentMini", "teacherMini")
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


def focus_mode_for(action_key: str, *, client: str) -> str:
    """该 actionKey 在指定端的 focusMode；未声明一律 NONE（fail-closed）。"""
    spec = ACTION_REGISTRY.get(action_key)
    if not spec:
        return FOCUS_NONE
    return normalize_focus_mode((spec.get("focus") or {}).get(client))


def focus_param_for(action_key: str) -> str | None:
    """聚焦值取哪个参数：显式 focusParam 优先，否则用第一个必需参数。"""
    spec = ACTION_REGISTRY.get(action_key)
    if not spec:
        return None
    explicit = spec.get("focusParam")
    if explicit:
        return str(explicit)
    required = spec.get("requiredParams") or []
    return str(required[0]) if required else None


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
    focus_mode = focus_mode_for(action_key, client=client)
    return {
        "ok": True,
        "path": path,
        "label": spec.get("label"),
        "focusMode": focus_mode,
        "focusParam": focus_param_for(action_key),
        "exact": is_route_exact(focus_mode, path),
    }
