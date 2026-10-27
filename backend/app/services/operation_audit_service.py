"""
审计服务
────────────────────────────────────────────────────────────
普通运行留痕：record() fire-and-forget，失败不阻断主业务。
高危审计：record_critical() / audit_insert_in_session() 必须成功，
与业务同事务或独立提交失败即抛错。

认证入口现在是 tenant-neutral。登录成功时请求上下文不能再借 DEFAULT_TENANT_CODE 伪装学校；
当 target_id 是真实 ``db-<user_id>`` 时，本服务按真实 User 行解析 tenant_id 后写审计。
"""
from __future__ import annotations

import re
import uuid

from app.core.context import current_tenant_id, get_current_user_ctx, get_trace_id
from app.core.response import paginate

_MAX = 500
_BUFFER: list[dict] = []

ACTION_LABELS = {
    "JOB_RETRY": "重试后台任务", "JOB_CANCEL": "取消后台任务",
    "LOGIN": "登录", "LOGIN_FAIL": "登录失败", "LOGIN_LOCKED": "账号锁定", "LOGOUT": "登出",
    "TOKEN_REFRESH": "会话刷新", "RATE_LIMITED": "访问频率拦截", "LOGIN_NO_ACTIVE_ROLE": "没有有效岗位",
    "ROLE_COPY": "复制本校角色", "ROLE_ADOPT": "转为本校维护",
    "EXPORT": "导出", "IMPORT": "导入", "IDENTITY_IMPORT": "师生导入", "GRANT": "授权变更",
    "CONFIG": "配置变更", "CONFIG_CHANGE": "配置变更", "BRAND_CONFIG": "品牌配置",
    "DISABLE": "停用/作废", "ENABLE": "启用", "USER_DISABLE": "停用/作废", "USER_ENABLE": "启用",
    "USER_ROLE_ASSIGN": "分配角色", "RESET_PASSWORD": "重置密码", "PERMISSION_DENIED": "越权拦截",
    "MODULE_DENIED": "模块越权", "SENSITIVE_VIEW": "敏感查看", "FILE_UPLOAD": "文件上传",
    "ROLE_CREATE": "新建角色", "ROLE_UPDATE": "编辑角色", "ROLE_PERMISSION_SAVE": "保存角色权限",
    "ORG_NODE_SAVE": "组织维护",
}


RESULT_BUCKETS = {"SUCCESS": ("SUCCESS", "成功"), "FAIL": ("FAILED", "失败"),
                  "FAILED": ("FAILED", "失败"), "DENIED": ("DENIED", "越权拦截"),
                  "BLOCKED": ("BLOCKED", "已拦截"), "UNKNOWN": ("UNKNOWN", "结果未确认")}
EVENT_RESULTS = {"PERMISSION_DENIED": "DENIED", "MODULE_DENIED": "DENIED",
                 "LOGIN_NO_ACTIVE_ROLE": "DENIED", "LOGIN_FAIL": "FAILED",
                 "LOGIN_LOCKED": "BLOCKED", "RATE_LIMITED": "BLOCKED"}


def present_result(action: str, recorded_result: str | None) -> dict:
    raw_bucket = RESULT_BUCKETS.get(str(recorded_result or "").upper(), ("UNKNOWN", ""))[0]
    bucket = EVENT_RESULTS.get(str(action or "").upper(), raw_bucket)
    label = ACTION_LABELS.get(action, action if re.search(r"[\u3400-\u9fff]", str(action or "")) else "未识别的历史操作")
    return {"actionLabel": label, "result": bucket, "resultLabel": RESULT_BUCKETS[bucket][1], "recordedResult": recorded_result,
            "resultNote": "事件与原记录结果不一致；按事件展示，原记录未修改" if bucket != raw_bucket else ""}


def present_target(resource: str | None, action: str | None = None) -> str:
    if action in {"LOGIN_FAIL", "LOGIN_LOCKED", "LOGIN_NO_ACTIVE_ROLE"}:
        return "登录尝试（身份未确认）"
    value = str(resource or "").strip()
    if not value:
        return "未记录对象"
    if re.search(r"[\u3400-\u9fff]", value):
        return value
    if value in {"auth", "authz"}:
        return "登录账号" if value == "auth" else "身份上下文"
    for prefix, label in (("role:", "角色配置"), ("user:", "账号"), ("tenant:", "学校"), ("perm:", "权限校验"), ("job:", "后台任务"),
                          ("/api/v1/academic-affairs", "教务中心接口访问"), ("/api/v1/student-affairs", "学工中心接口访问"),
                          ("/api/v1/graduation", "毕业设计接口访问"), ("/api/v1/internship", "岗位实习接口访问"),
                          ("/api/v1/system", "系统管理接口访问")):
        if value.startswith(prefix):
            return label
    return "未识别的历史对象"


def _event_result(action: str, status_code: int | None) -> str:
    fallback = "DENIED" if status_code == 403 else "FAIL" if status_code and status_code >= 400 else "SUCCESS"
    return EVENT_RESULTS.get(str(action or "").upper(), fallback)

CRITICAL_ACTIONS = {
    "角色授权", "权限变更", "修改角色权限", "分配角色",
    "敏感导出", "SENSITIVE_EXPORT", "明文查看",
    "处分决定", "处分下达", "成绩发布", "成绩终审",
    "密码重置", "强制下线", "作废学生", "删除学生",
    "审批通过", "审批驳回", "资助发放", "发放确认",
}


def _now_iso() -> str:
    from app.core.timeutil import iso_utc, utc_now
    return iso_utc(utc_now()) or ""


def _is_critical(action: str) -> bool:
    a = (action or "").strip()
    if a in CRITICAL_ACTIONS:
        return True
    return any(k in a for k in ("授权", "敏感导出", "密码重置", "作废学生", "成绩发布", "资助发放"))


def _resolved_tenant_id(target_id: str | None = None) -> int | None:
    """Use request tenant when real; otherwise resolve a db-user target without guessing."""
    try:
        context_tid = str(current_tenant_id() or "")
    except Exception:
        context_tid = ""
    if context_tid.isdigit():
        return int(context_tid)

    raw = str(target_id or "")
    if not raw.startswith("db-") or not raw[3:].isdigit():
        return None
    try:
        from sqlalchemy import select
        from app.db.session import db_enabled, get_sessionmaker
        if not db_enabled():
            return None
        from app.models import User
        db = get_sessionmaker()()
        try:
            user = db.scalars(select(User).where(User.id == int(raw[3:])).limit(1)).first()
            return int(user.tenant_id) if user is not None else None
        finally:
            db.close()
    except Exception:
        return None


def record(action: str, *, method: str | None = None, path: str | None = None,
           status_code: int | None = None, target_type: str | None = None,
           target_id: str | None = None, detail: dict | None = None) -> None:
    """普通审计：失败不阻断。命中高危关键字时尽力强写；仍失败只告警（同事务请用 record_critical(db=...)）。"""
    if _is_critical(action):
        try:
            record_critical(action, method=method, path=path, status_code=status_code,
                            target_type=target_type, target_id=target_id, detail=detail)
            return
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger("app.audit").error(
                "CRITICAL_AUDIT_MISSING action=%s target=%s", action, target_id)
            _record_memory(action, method=method, path=path, status_code=status_code,
                           target_type=target_type, target_id=target_id, detail=detail)
            return
    _record_soft(action, method=method, path=path, status_code=status_code,
                 target_type=target_type, target_id=target_id, detail=detail)


def record_authenticated_event(result: dict, *, path: str, action: str = "登录") -> None:
    """Use verified login results or refresh claims, not submitted account identifiers."""
    from sqlalchemy import select
    from app.core.context import get_request_meta
    from app.core.timeutil import utc_now_naive
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import SecurityAuditLog, User

    user_id = str(result.get("userId") or "")
    if not db_enabled():
        record(action, path=path, target_type="auth", target_id=user_id, status_code=200)
        return
    if not user_id.startswith("db-") or not user_id[3:].isdigit():
        raise ValueError("登录审计缺少已认证账号")
    tenant_id = int(result["tenantId"])
    with get_sessionmaker()() as db:
        account = db.scalar(select(User).where(User.id == int(user_id[3:]), User.tenant_id == tenant_id).with_for_update())
        if account is None:
            raise ValueError("登录审计账号与学校不一致")
        occurred_at = utc_now_naive()
        meta = get_request_meta()
        if action in {"登录", "LOGIN", "微信登录", "微信登录-选择学校", "微信绑定"}:
            account.last_login_at = occurred_at
        db.add(SecurityAuditLog(
            tenant_id=tenant_id, operator_id=account.id, operator_name=account.real_name,
            current_role=result.get("currentRoleCode") or (result.get("currentRole") or {}).get("roleCode"),
            action=action, resource="auth", resource_id=user_id, result="SUCCESS",
            created_at=occurred_at, ip=meta.get("ip"), user_agent=meta.get("userAgent"),
            request_method=meta.get("method") or "POST", request_path=meta.get("path") or path,
            trace_id=get_trace_id(), detail_json={"moduleCode": "systemAdmin"},
        ))
        db.commit()


def record_critical(action: str, *, method: str | None = None, path: str | None = None,
                    status_code: int | None = None, target_type: str | None = None,
                    target_id: str | None = None, detail: dict | None = None,
                    db=None) -> None:
    """高危审计：必须写入成功。可传入业务 db 会话实现同事务。"""
    tenant_id = _resolved_tenant_id(target_id)
    _record_memory(action, method=method, path=path, status_code=status_code,
                   target_type=target_type, target_id=target_id, detail=detail,
                   tenant_id=tenant_id)
    from app.db.session import db_enabled
    if not db_enabled():
        return
    if tenant_id is None:
        raise RuntimeError(f"critical audit {action} has no verifiable tenant")
    from app.services import db_service
    payload = {"method": method, "path": path, "targetId": target_id, **(detail or {})}
    if db is not None:
        db_service.audit_insert_in_session(
            db, action, target_type or (path or ""), payload, _event_result(action, status_code),
            tenant_id=tenant_id, resource_id=target_id)
        return
    db_service.audit_insert(action, target_type or (path or ""), payload, _event_result(action, status_code),
                            tenant_id=tenant_id, resource_id=target_id)


def _record_memory(action, *, method=None, path=None, status_code=None,
                   target_type=None, target_id=None, detail=None, tenant_id=None) -> None:
    user = get_current_user_ctx() or {}
    resolved = tenant_id if tenant_id is not None else _resolved_tenant_id(target_id)
    entry = {
        "id": f"aud_{uuid.uuid4().hex[:12]}",
        "traceId": get_trace_id(),
        "tenantId": str(resolved) if resolved is not None else None,
        "userId": user.get("userId"),
        "realName": user.get("realName"),
        "roleCode": user.get("currentRoleCode"),
        "action": action,
        "method": method,
        "path": path,
        "targetType": target_type,
        "targetId": target_id,
        "statusCode": status_code,
        "result": _event_result(action, status_code),
        "detail": detail,
        "occurredAt": _now_iso(),
    }
    _BUFFER.insert(0, entry)
    del _BUFFER[_MAX:]


def _record_soft(action: str, *, method=None, path=None, status_code=None,
                 target_type=None, target_id=None, detail=None) -> None:
    tenant_id = _resolved_tenant_id(target_id)
    _record_memory(action, method=method, path=path, status_code=status_code,
                   target_type=target_type, target_id=target_id, detail=detail,
                   tenant_id=tenant_id)
    try:
        from app.db.session import db_enabled
        if db_enabled() and tenant_id is not None:
            from app.services import db_service
            db_service.audit_insert(
                action, target_type or (path or ""),
                {"method": method, "path": path, "targetId": target_id, **(detail or {})},
                _event_result(action, status_code), tenant_id=tenant_id, resource_id=target_id,
            )
    except Exception:  # noqa: BLE001
        pass


def _seed() -> None:
    if _BUFFER:
        return
    samples = [
        {"action": "登录", "method": "POST", "path": "/api/v1/auth/mock-login", "targetType": "auth"},
        {"action": "切换身份", "method": "POST", "path": "/api/v1/auth/switch-role", "targetType": "authz"},
        {"action": "导出学生名单", "method": "POST", "path": "/api/v1/export/create-placeholder", "targetType": "export"},
    ]
    for i, s in enumerate(samples):
        _BUFFER.append({
            "id": f"aud_seed_{i}", "traceId": f"req-seed{i:04d}", "tenantId": "1000000000000000001",
            "userId": "u_admin_001", "realName": "教务处·赵敏", "roleCode": "SCHOOL_ADMIN",
            "action": s["action"], "method": s["method"], "path": s["path"],
            "targetType": s["targetType"], "targetId": None, "statusCode": 200, "detail": None,
            "occurredAt": _now_iso(),
        })


def list_logs(action: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    _seed()
    rows = _BUFFER
    if action:
        rows = [r for r in rows if action in (r.get("action") or "")]
    total = len(rows)
    start = (page - 1) * page_size
    return paginate(rows[start:start + page_size], total, page, page_size)
