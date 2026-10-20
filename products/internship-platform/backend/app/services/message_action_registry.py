"""岗位实习 Standalone 消息动作注册表。"""
from __future__ import annotations

from app.core.exceptions import AppException

_ACTIONS = {
    "student.internship.volunteer-result": {
        "required": ("groupId", "groupVersion"),
        "routes": {
            "studentPc": "/internship/volunteer-result",
            "studentMini": "/pages/student-internship/volunteer-result/index",
        },
    },
    "student.internship.weekly-report": {
        "required": ("reportId", "batchId", "internshipId", "weekNo"),
        "routes": {
            "studentMini": "/pages/student/weekly-report/index",
        },
    },
    "enterprise.internship.application": {
        "required": ("applicationId", "campaignId"),
        "routes": {"enterprise": "/applications/:applicationId"},
    },
    "enterprise.internship.position": {
        "required": ("positionId", "campaignId"),
        "routes": {"enterprise": "/positions/:positionId/edit"},
    },
}


def validate_action(action_key, action_params):
    key = str(action_key or "").strip()
    if not key:
        return None, None
    spec = _ACTIONS.get(key)
    if spec is None:
        raise AppException(
            "MESSAGE_ACTION_NOT_ALLOWED",
            f"未登记的岗位实习消息动作：{key}",
            http_status=422,
        )
    params = dict(action_params or {})
    missing = [name for name in spec["required"] if str(params.get(name) or "").strip() == ""]
    if missing:
        raise AppException(
            "VALIDATION_ERROR",
            f"消息动作缺少参数：{','.join(missing)}",
            http_status=422,
        )
    allowed = set(spec["required"])
    return key, {name: str(params[name]) for name in allowed}


def list_action_keys():
    return [
        {"actionKey": key, "requiredParams": list(spec["required"]), "routes": dict(spec["routes"])}
        for key, spec in sorted(_ACTIONS.items())
    ]


def resolve_route(action_key: str, *, client: str) -> dict:
    spec = _ACTIONS.get(str(action_key or "").strip())
    route = (spec or {}).get("routes", {}).get(client)
    if not route:
        raise AppException("MESSAGE_ACTION_UNAVAILABLE", "当前端暂无安全处理入口", http_status=404)
    return {"path": route}


def focus_mode_for(action_key: str, *, client: str) -> str:
    _ = action_key, client
    return "NONE"


def focus_param_for(action_key: str):
    spec = _ACTIONS.get(str(action_key or "").strip())
    return (spec or {}).get("required", (None,))[0]
