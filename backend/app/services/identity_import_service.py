"""师生身份主数据唯一导入入口。

只有本服务允许批量创建登录账号并绑定预设角色。毕设、实习、教务、学工等业务导入
只能引用这里已经存在的学号/工号，不得隐式创建 User。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import school_onboarding_service

_ALLOWED_KEYS = {"tenantId", "atomic", "students", "teachers"}


def preview_identity_import(user: dict, body: dict, *, pre_errors: list[dict] | None = None) -> dict:
    """文件入口预检；即使所有文件行都因账号类型错误而无法归类，也返回统一预检报告。"""
    source = body or {}
    if source.get("students") or source.get("teachers"):
        report = run_identity_import(user, source, dry_run=True)
    else:
        operator = school_onboarding_service._require_operator(user)
        tenant_id = school_onboarding_service._resolve_target_tenant(operator, source)
        report = school_onboarding_service._blank_report(True, tenant_id)
    report["errors"] = list(pre_errors or []) + list(report.get("errors") or [])
    return report


def run_identity_import(user: dict, body: dict, *, dry_run: bool) -> dict:
    if not dry_run and not school_onboarding_service.db_enabled():
        raise AppException("SERVER_ERROR", "数据库未启用，禁止确认创建师生账号")
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
