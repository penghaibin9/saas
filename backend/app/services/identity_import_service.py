"""师生身份主数据唯一导入入口。

只有本服务允许批量创建登录账号并绑定预设角色。毕设、实习、教务、学工等业务导入
只能引用这里已经存在的学号/工号，不得隐式创建 User。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import school_onboarding_service

_ALLOWED_KEYS = {"tenantId", "atomic", "students", "teachers"}


def run_identity_import(user: dict, body: dict, *, dry_run: bool) -> dict:
    source = body or {}
    unknown = sorted(set(source) - _ALLOWED_KEYS)
    if unknown:
        raise AppException(
            "VALIDATION_ERROR",
            f"师生账号导入不接受这些字段：{','.join(unknown)}")
    if source.get("atomic") is False:
        raise AppException("VALIDATION_ERROR", "师生账号导入必须整批校验、整批提交，不允许跳过错误行")
    payload = {key: value for key, value in source.items() if key in _ALLOWED_KEYS}
    if not (payload.get("students") or payload.get("teachers")):
        raise AppException("VALIDATION_ERROR", "请至少导入一名老师或学生")
    payload["atomic"] = True
    return school_onboarding_service.run_onboarding(
        user, payload, dry_run=dry_run, identity_channel=True)
