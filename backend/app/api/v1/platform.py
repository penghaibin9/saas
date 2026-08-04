"""
P6 · 平台总控 /api/v1/platform/*（仅 PLATFORM_SUPER_ADMIN）
────────────────────────────────────────────────────────────
- 强校验：后端依赖 require_platform_super_admin；学校角色一律 403 NO_PERMISSION。
- 权限拒绝写审计（PERMISSION_DENIED / DENIED）。
- 覆盖：总览 / 租户 / 套餐 / 功能开关 / 规则中心 / 流程 / 字典 / 品牌 /
        账号 / 订单 / 公告 / 安全 / 全平台审计 / 系统参数。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Request

from app.core.exceptions import AppException
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.services import audit_log
from app.services import platform_defaults as D
from app.services import platform_service as svc

router = APIRouter(prefix="/platform", tags=["16·平台总控（仅平台超管）"])

PLATFORM_ROLE = "PLATFORM_SUPER_ADMIN"


def require_platform_super_admin(request: Request, user=Depends(get_current_user)) -> dict:
    """平台总控强校验：角色/用户类型必须是 PLATFORM_SUPER_ADMIN，拒绝即审计。"""
    role = user.get("currentRoleCode") or user.get("userType")
    if role not in {PLATFORM_ROLE, "PLATFORM_OWNER"}:
        audit_log.record("PERMISSION_DENIED", f"platform:{request.url.path}",
                         detail={"path": request.url.path, "method": request.method,
                                 "role": user.get("currentRoleCode"), "userType": user.get("userType")},
                         result="DENIED")
        raise AppException("NO_PERMISSION", "仅平台超级管理员可访问平台总控")
    return user


def _audit(action: str, resource: str, detail: dict | None = None, *, tenant_id: int | None = None):
    """平台侧审计。tenant_id 传"被操作学校"，使该校自身审计可见平台动作（跨租户责任追溯）。"""
    audit_log.record(action, resource, detail=detail or {}, result="SUCCESS", tenant_id=tenant_id)


def _expected_version(body: dict, *, operation: str) -> int:
    value = body.get("expectedVersion")
    if value is None:
        raise AppException("VALIDATION_ERROR", f"{operation}必须提供 expectedVersion")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{operation}的 expectedVersion 必须为整数") from None


# ── §二 总览 ──

@router.get("/overview", summary="平台经营、客户成功与运行总览")
def overview(user=Depends(require_platform_super_admin)):
    from app.services.platform_overview_service import overview as gov_overview
    return success(gov_overview())


# ── PLAT-06 公共底座运行中心（跨租户聚合 PR#25 文件底座 + PLAT-08 服务目录）──

@router.get("/foundations/overview", summary="公共底座运行中心：跨租户文件底座 + 服务目录")
def foundations_overview(user=Depends(require_platform_super_admin)):
    from app.services.foundation_operations_service import foundation_overview
    return success(foundation_overview())


# ── PLAT-14 数据治理、集成目录与合规证据（跨租户聚合）──

@router.get("/governance/overview", summary="数据治理、集成目录与合规证据")
def governance_overview_endpoint(user=Depends(require_platform_super_admin)):
    from app.services.platform_governance_service import governance_overview
    return success(governance_overview())


# ── §三 租户全托管 ──

@router.get("/tenants", summary="租户列表（keyword/status 过滤）")
def tenants(keyword: Optional[str] = Query(default=None), status: Optional[str] = Query(default=None),
            user=Depends(require_platform_super_admin)):
    items = svc.list_tenants(keyword, status)
    return success({"list": items, "total": len(items)})


@router.post("/tenants", summary="新建租户（学校）")
def tenant_create(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = svc.create_tenant(body)
    _audit("PLATFORM_TENANT_CREATE", out["tenantCode"], {"tenantId": out["tenantId"]},
           tenant_id=int(out["tenantId"]))
    return success(out, message="租户已创建")


@router.get("/tenants/{tenant_id}", summary="租户详情")
def tenant_get(tenant_id: int, user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import tenant_360
    legacy = svc.get_tenant(tenant_id)
    return success({**legacy, "tenant360": tenant_360(tenant_id)})


@router.put("/tenants/{tenant_id}", summary="租户基础信息修改")
def tenant_update(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    allow = {"schoolType", "province", "city", "contactName", "contactPhone", "contactWechat",
             "environment", "remark"}
    patch = {k: v for k, v in body.items() if k in allow}
    before = svc.tenant_meta(tenant_id)
    out = svc.update_tenant_meta(tenant_id, patch)
    _audit("PLATFORM_TENANT_UPDATE", str(tenant_id),
           {"changedKeys": list(patch),
            "before": {k: before.get(k) for k in patch}, "after": patch},
           tenant_id=tenant_id)
    return success(out)


@router.post("/tenants/{tenant_id}/enable", summary="启用租户（原因+版本锁）")
def tenant_enable(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, "enable", reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户变更"), payload=body,
    )
    _audit("PLATFORM_TENANT_ENABLE", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message="已启用")

@router.post("/tenants/{tenant_id}/disable", summary="停用租户（原因+版本锁）")
def tenant_disable(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, "disable", reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户变更"), payload=body,
    )
    _audit("PLATFORM_TENANT_DISABLE", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message="已停用，该校账号将无法登录")

@router.post("/tenants/{tenant_id}/extend-trial", summary="延长试用（原因+版本锁）")
def tenant_extend_trial(tenant_id: int, body: dict = Body(...),
                        user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, "extend-trial", reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户延期"), payload=body,
    )
    _audit("PLATFORM_TENANT_EXTEND_TRIAL", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message=f"已延长 {int(body.get('days') or 7)} 天")


@router.post("/tenants/{tenant_id}/convert-to-paid", summary="试用转正式（原因+版本锁）")
def tenant_convert(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, "convert-to-paid", reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户变更"), payload=body,
    )
    _audit("PLATFORM_TENANT_CONVERT_PAID", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message="已转为正式授权")

@router.post("/tenants/{tenant_id}/expire", summary="手动标记到期（原因+版本锁）")
def tenant_expire(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, "expire", reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户变更"), payload=body,
    )
    _audit("PLATFORM_TENANT_EXPIRE", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message="已标记到期（租户进入只读）")

@router.post("/tenants/{tenant_id}/change-package", summary="变更套餐（原因+版本锁）")
def tenant_change_package(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, "change-package", reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户变更"), payload=body,
    )
    _audit("PLATFORM_TENANT_CHANGE_PACKAGE", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message="套餐已变更；超额数据不会被静默删除")

@router.post("/tenants/{tenant_id}/quota", summary="租户商业容量覆盖（原因+版本锁）")
def tenant_quota(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, "quota", reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户变更"), payload=body,
    )
    _audit("PLATFORM_TENANT_QUOTA", str(tenant_id), out, tenant_id=tenant_id)
    return success(out)

@router.post("/tenants/{tenant_id}/reset-demo-data", summary="重置演示数据（仅 demo-school）")
def tenant_reset_demo(tenant_id: int, user=Depends(require_platform_super_admin)):
    if tenant_id != svc.DEMO_TID:
        raise AppException("NO_PERMISSION", "仅演示租户 demo-school 支持重置演示数据")
    out = svc.reset_demo_data()
    _audit("PLATFORM_DEMO_RESET", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message="演示数据已重置为基线（5 名学生）")


@router.post("/tenants/{tenant_id}/reset-sandbox-data", summary="恢复真实演示沙箱")
def tenant_reset_sandbox(tenant_id: int, user=Depends(require_platform_super_admin)):
    from app.db.session import db_enabled, get_sessionmaker
    from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID, reset_sandbox
    if tenant_id != SANDBOX_TID:
        raise AppException("NO_PERMISSION", f"仅 {SANDBOX_CODE} 支持恢复演示数据")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "恢复演示沙箱需要启用真实数据库")
    db = get_sessionmaker()()
    try:
        out = reset_sandbox(db, dry_run=False)
    finally:
        db.close()
    _audit("PLATFORM_SANDBOX_RESET", str(tenant_id), out, tenant_id=tenant_id)
    return success(out, message="真实演示沙箱已恢复；账号与权限已保留")


@router.get("/tenants/{tenant_id}/usage", summary="租户用量")
def tenant_usage(tenant_id: int, user=Depends(require_platform_super_admin)):
    t = svc.get_tenant(tenant_id)
    return success({"tenantId": t["tenantId"], "tenantName": t["tenantName"],
                    "studentCount": t["studentCount"], "maxStudents": t["maxStudents"],
                    "userCount": t["userCount"], "maxUsers": t["maxUsers"],
                    "usedStorageMb": t["usedStorageMb"], "storageLimitMb": t["storageLimitMb"],
                    "status": t["status"], "expireAt": t["expireAt"]})


@router.get("/tenants/{tenant_id}/audit-logs", summary="租户维度审计")
def tenant_audit(tenant_id: int, page: int = Query(default=1, ge=1),
                 pageSize: int = Query(default=20, ge=1, le=100),
                 user=Depends(require_platform_super_admin)):
    items, total = svc.platform_audit_query(page, pageSize, tenant_id=tenant_id)
    return success(paginate(items, total, page, pageSize))


# ── §四 套餐 ──

@router.get("/packages", summary="套餐列表（5 默认套餐 + 覆盖）")
def packages(user=Depends(require_platform_super_admin)):
    return success({"list": [svc.get_package(c) for c in D.DEFAULT_PACKAGES]})


@router.put("/packages/{package_code}", summary="修改套餐（价格/时长/容量/功能）")
def package_update(package_code: str, body: dict = Body(...),
                   user=Depends(require_platform_super_admin)):
    if package_code not in D.DEFAULT_PACKAGES:
        raise AppException("VALIDATION_ERROR", "packageCode 不存在")
    if body.get("expectedVersion") is None or len(str(body.get("reason") or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "套餐变更必须提供 expectedVersion 和至少5个字符的原因")
    cur = svc.get_package(package_code)
    allow = {"packageName", "price", "durationDays", "maxStudents", "maxUsers",
             "storageLimitMb", "features", "enabled", "remark"}
    base_cur = {k: v for k, v in cur.items() if k != "version"}
    merged = {**base_cur, **{k: v for k, v in body.items() if k in allow},
              "packageCode": package_code}
    if isinstance(body.get("features"), dict):
        merged["features"] = {**cur.get("features", {}),
                              **{k: bool(v) for k, v in body["features"].items() if k in D.FEATURE_KEYS}}
    for k in ("durationDays", "maxStudents", "maxUsers", "storageLimitMb"):
        if not isinstance(merged.get(k), int) or merged[k] < 1:
            raise AppException("VALIDATION_ERROR", f"{k} 需为正整数")
    svc.put_config_json(0, "PACKAGE", package_code, merged, expected_version=_expected_version(body, operation="套餐变更"))
    _audit("PLATFORM_PACKAGE_UPDATE", package_code, {"reason": str(body["reason"])[:1000]})
    return success(svc.get_package(package_code))


# ── §五 功能开关 ──

@router.get("/tenants/{tenant_id}/features", summary="租户功能开关（套餐+租户覆盖后的生效值）")
def features_get(tenant_id: int, user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    return success({"tenantId": str(tenant_id), "features": svc.effective_features(tenant_id),
                    "featureKeys": D.FEATURE_KEYS})


@router.put("/tenants/{tenant_id}/features", summary="修改租户功能开关（业务端即刻生效）")
def features_put(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    patch = {k: bool(v) for k, v in (body.get("features") or body).items() if k in D.FEATURE_KEYS}
    if not patch:
        raise AppException("VALIDATION_ERROR", "没有可更新的功能开关键")
    cur = svc.get_config_json(tenant_id, "FEATURES") or {}
    before = {k: cur.get(k) for k in patch}
    cur.update(patch)
    svc.put_config_json(tenant_id, "FEATURES", "-", cur)
    _audit("PLATFORM_FEATURES_UPDATE", str(tenant_id),
           {"before": before, "after": patch}, tenant_id=tenant_id)
    return success({"tenantId": str(tenant_id), "features": svc.effective_features(tenant_id)})


# ── §六 规则中心 ──

@router.get("/rules/defaults", summary="平台默认规则（9 组）")
def rules_defaults(user=Depends(require_platform_super_admin)):
    return success({"rules": D.DEFAULT_RULES})


@router.get("/tenants/{tenant_id}/rules", summary="租户生效规则（默认+覆盖合并）")
def rules_get(tenant_id: int, user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    return success({"tenantId": str(tenant_id), "rules": svc.effective_rules(tenant_id),
                    "override": svc.get_config_json(tenant_id, "RULES") or {}})


@router.put("/tenants/{tenant_id}/rules", summary="修改租户规则（后端业务即刻按新规则校验）")
def rules_put(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    payload = svc.validate_rules(body.get("rules") or body)
    cur = svc.get_config_json(tenant_id, "RULES") or {}
    for g, kv in payload.items():
        cur.setdefault(g, {}).update(kv)
    svc.put_config_json(tenant_id, "RULES", "-", cur)
    _audit("PLATFORM_RULES_UPDATE", str(tenant_id),
           {"groups": list(payload), "after": payload}, tenant_id=tenant_id)
    return success({"tenantId": str(tenant_id), "rules": svc.effective_rules(tenant_id)})


# ── §七 流程配置 ──

@router.get("/tenants/{tenant_id}/workflows", summary="租户审批流配置（8 类）")
def workflows_get(tenant_id: int, user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    return success({"tenantId": str(tenant_id), "workflows": svc.effective_workflows(tenant_id)})


@router.put("/tenants/{tenant_id}/workflows/{workflow_code}", summary="修改某审批流（开关/审批角色/时限）")
def workflow_put(tenant_id: int, workflow_code: str, body: dict = Body(...),
                 user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    if workflow_code not in D.DEFAULT_WORKFLOWS:
        raise AppException("VALIDATION_ERROR", "workflowCode 不存在")
    allow = {"enabled", "needApproval", "approverRoleCodes", "ccRoleCodes", "timeoutHours",
             "allowTransfer", "allowReject", "allowWithdraw"}
    patch = {k: v for k, v in body.items() if k in allow}
    if "timeoutHours" in patch and (not isinstance(patch["timeoutHours"], int)
                                    or not 1 <= patch["timeoutHours"] <= 720):
        raise AppException("VALIDATION_ERROR", "timeoutHours 需在 1~720 之间")
    cur = svc.get_config_json(tenant_id, "WORKFLOWS") or {}
    cur.setdefault(workflow_code, {}).update(patch)
    svc.put_config_json(tenant_id, "WORKFLOWS", "-", cur)
    _audit("PLATFORM_WORKFLOW_UPDATE", f"{tenant_id}:{workflow_code}",
           {"workflowCode": workflow_code, "after": patch}, tenant_id=tenant_id)
    return success({"workflowCode": workflow_code,
                    "workflow": svc.effective_workflows(tenant_id)[workflow_code]})


# ── §八 字典 ──

@router.get("/dictionaries", summary="平台字典（12 类；tenantId 传值时含租户覆盖）")
def dicts_get(tenantId: Optional[int] = Query(default=None),
              user=Depends(require_platform_super_admin)):
    data = {k: list(v) for k, v in D.DEFAULT_DICTIONARIES.items()}
    data.update(svc.get_config_json(0, "DICT") or {})
    if tenantId:
        data.update(svc.get_config_json(tenantId, "DICT") or {})
    return success({"dictionaries": data})


@router.put("/dictionaries/{dict_code}", summary="修改字典（tenantId=0 全平台默认，否则租户覆盖）")
def dicts_put(dict_code: str, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    if dict_code not in D.DEFAULT_DICTIONARIES:
        raise AppException("VALIDATION_ERROR", "dictCode 不存在")
    items = body.get("items")
    if not isinstance(items, list) or not items:
        raise AppException("VALIDATION_ERROR", "items 必须是非空数组")
    for it in items:
        if not isinstance(it, dict) or not it.get("code") or not it.get("label"):
            raise AppException("VALIDATION_ERROR", "字典项需要 code 与 label")
    tid = int(body.get("tenantId") or 0)
    cur = svc.get_config_json(tid, "DICT") or {}
    cur[dict_code] = [{"code": str(i["code"]), "label": str(i["label"]),
                       "enabled": bool(i.get("enabled", True))} for i in items]
    svc.put_config_json(tid, "DICT", "-", cur)
    _audit("PLATFORM_DICT_UPDATE", f"{tid}:{dict_code}")
    return success({"dictCode": dict_code, "items": cur[dict_code]})


# ── §九 品牌 ──

@router.get("/tenants/{tenant_id}/brand", summary="租户品牌配置")
def brand_get(tenant_id: int, user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    return success({"tenantId": str(tenant_id), "brand": svc.effective_brand(tenant_id)})


@router.put("/tenants/{tenant_id}/brand", summary="修改租户品牌（名称/水印/主色/联系电话等）")
def brand_put(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    allow = set(D.DEFAULT_BRAND)
    patch = {k: str(v) for k, v in body.items() if k in allow}
    if not patch:
        raise AppException("VALIDATION_ERROR", "没有可更新的品牌字段")
    cur = svc.get_config_json(tenant_id, "BRAND") or {}
    before = {k: cur.get(k) for k in patch}
    cur.update(patch)
    svc.put_config_json(tenant_id, "BRAND", "-", cur)
    _audit("PLATFORM_BRAND_UPDATE", str(tenant_id),
           {"keys": list(patch), "before": before, "after": patch}, tenant_id=tenant_id)
    return success({"tenantId": str(tenant_id), "brand": svc.effective_brand(tenant_id)})


# ── §十 账号控制 ──

@router.get("/tenants/{tenant_id}/users", summary="租户账号列表")
def users_get(tenant_id: int, user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    return success({"list": svc.list_users(tenant_id)})


@router.post("/tenants/{tenant_id}/users", summary="为租户创建学校管理员（初始密码仅显示一次）")
def users_create(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    svc.get_tenant(tenant_id)
    login_name = str(body.get("loginName") or "").strip()
    real_name = str(body.get("realName") or "").strip()
    if not login_name or not real_name:
        raise AppException("VALIDATION_ERROR", "loginName / realName 必填")
    out = svc.create_school_admin(tenant_id, login_name, real_name)
    # 审计不落初始密码
    _audit("PLATFORM_USER_CREATE", f"{tenant_id}:{login_name}",
           {"userId": out.get("userId"), "loginName": login_name}, tenant_id=tenant_id)
    return success(out, message="账号已创建，初始密码仅本次显示")


@router.post("/users/{user_id}/enable", summary="启用账号")
def user_enable(user_id: int, user=Depends(require_platform_super_admin)):
    out = svc.set_user_status(user_id, "ACTIVE")
    _audit("PLATFORM_USER_ENABLE", str(user_id), {"userId": out["userId"]},
           tenant_id=int(out["tenantId"]))
    return success(out)


@router.post("/users/{user_id}/disable", summary="停用账号")
def user_disable(user_id: int, user=Depends(require_platform_super_admin)):
    out = svc.set_user_status(user_id, "DISABLED")
    _audit("PLATFORM_USER_DISABLE", str(user_id), {"userId": out["userId"]},
           tenant_id=int(out["tenantId"]))
    return success(out)


@router.post("/users/{user_id}/reset-password", summary="重置密码（新密码仅显示一次，不写日志）")
def user_reset_pwd(user_id: int, user=Depends(require_platform_super_admin)):
    out = svc.reset_user_password(user_id)
    _audit("PLATFORM_USER_RESET_PWD", str(user_id), {"userId": out["userId"]},
           tenant_id=int(out["tenantId"]))  # 不含密码
    return success(out)


# ── §十一 订单/计费 ──

@router.get("/orders", summary="订单列表")
def orders(tenantId: Optional[int] = Query(default=None), status: Optional[str] = Query(default=None),
           user=Depends(require_platform_super_admin)):
    items = svc.list_orders(tenantId, status)
    return success({"list": items, "total": len(items)})


@router.post("/orders", summary="人工录入订单")
def order_create(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = svc.create_order(body)
    _audit("PLATFORM_ORDER_CREATE", out["orderNo"])
    return success(out, message="订单已创建（未支付）")


@router.post("/orders/{order_no}/mark-paid", summary="标记已支付（自动开通/续期）")
def order_paid(order_no: str, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = svc.order_action(order_no, "mark-paid", expected_version=_expected_version(body, operation="订单变更"), reason=body.get("reason"))
    _audit("PLATFORM_ORDER_PAID", order_no)
    return success(out, message="已入账并开通")


@router.post("/orders/{order_no}/cancel", summary="取消订单")
def order_cancel(order_no: str, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = svc.order_action(order_no, "cancel", expected_version=_expected_version(body, operation="订单变更"), reason=body.get("reason"))
    _audit("PLATFORM_ORDER_CANCEL", order_no)
    return success(out)


# ── §十二 公告 ──

@router.get("/notices", summary="平台公告列表")
def notices(status: Optional[str] = Query(default=None), user=Depends(require_platform_super_admin)):
    return success({"list": svc.list_notices(status)})


@router.post("/notices", summary="新建公告（草稿）")
def notice_create(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = svc.create_notice(body)
    _audit("PLATFORM_NOTICE_CREATE", out["noticeId"])
    return success(out)


@router.post("/notices/{notice_id}/publish", summary="发布公告")
def notice_publish(notice_id: int, user=Depends(require_platform_super_admin)):
    out = svc.notice_action(notice_id, "publish")
    _audit("PLATFORM_NOTICE_PUBLISH", str(notice_id))
    return success(out, message="已发布")


@router.post("/notices/{notice_id}/offline", summary="下线公告")
def notice_offline(notice_id: int, user=Depends(require_platform_super_admin)):
    out = svc.notice_action(notice_id, "offline")
    _audit("PLATFORM_NOTICE_OFFLINE", str(notice_id))
    return success(out, message="已下线")


# ── §十三 安全策略 ──

@router.get("/security", summary="平台安全参数（生效值）")
def security_get(user=Depends(require_platform_super_admin)):
    return success({"security": svc.effective_security(), "bounds": D.SECURITY_BOUNDS})


@router.put("/security", summary="修改安全参数（越界拒绝保存，不允许不设防）")
def security_put(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    merged = svc.validate_security(body.get("security") or body)
    svc.put_config_json(0, "SECURITY", "-", merged)
    _audit("PLATFORM_SECURITY_UPDATE", "global", {"keys": list(body)})
    return success({"security": svc.effective_security()})


# ── §十四 全平台审计 ──

@router.get("/audit-logs", summary="跨租户审计查询（tenantId/action/operator/日期）")
def audit_logs(tenantId: Optional[int] = Query(default=None),
               action: Optional[str] = Query(default=None),
               operator: Optional[str] = Query(default=None),
               dateFrom: Optional[str] = Query(default=None),
               dateTo: Optional[str] = Query(default=None),
               page: int = Query(default=1, ge=1),
               pageSize: int = Query(default=20, ge=1, le=100),
               user=Depends(require_platform_super_admin)):
    items, total = svc.platform_audit_query(page, pageSize, tenant_id=tenantId, action=action,
                                            operator=operator, date_from=dateFrom, date_to=dateTo)
    return success(paginate(items, total, page, pageSize))


# ── §系统参数 ──

@router.get("/settings", summary="平台系统参数")
def settings_get(user=Depends(require_platform_super_admin)):
    return success({"settings": svc.get_settings_config()})


@router.put("/settings", summary="修改平台系统参数")
def settings_put(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = svc.put_settings_config(body.get("settings") or body)
    _audit("PLATFORM_SETTINGS_UPDATE", "global", {"keys": list(body)})
    return success({"settings": out})


# ── §文件存储（本地 / 腾讯云 COS 可视化切换）──

@router.get("/file-storage", summary="文件存储配置（密钥脱敏）")
def file_storage_get(user=Depends(require_platform_super_admin)):
    from app.services.storage import config as storage_config
    return success({"config": storage_config.masked_config()})


@router.put("/file-storage", summary="保存文件存储配置（密钥加密存库，即时生效）")
def file_storage_put(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services.storage import config as storage_config
    payload = body.get("config") or body
    out = storage_config.save_config(payload)
    _audit("PLATFORM_FILE_STORAGE_UPDATE", "global", {"backend": out.get("backend")})
    return success({"config": out})


@router.post("/file-storage/test", summary="测试对象存储连接（写探针后删除）")
def file_storage_test(user=Depends(require_platform_super_admin)):
    from app.services.storage import config as storage_config
    result = storage_config.test_connection()
    _audit("PLATFORM_FILE_STORAGE_TEST", "global", {"ok": result.get("ok")})
    return success(result)


# ── V6 PLAT-02 / PLAT-15 / PLAT-03 canonical control endpoints ──

def require_platform_capability(capability: str):
    def _dep(user=Depends(get_current_user)):
        from app.services.platform_access_governance_service import assert_platform_capability
        return assert_platform_capability(user, capability)
    return _dep


@router.get("/tenants/{tenant_id}/360", summary="租户360与有效状态")
def tenant_360_get(tenant_id: int, user=Depends(require_platform_capability("tenant.view"))):
    from app.services.tenant_effective_state_service import tenant_360
    return success(tenant_360(tenant_id))


@router.post("/tenants/{tenant_id}/transitions/{action}/preview", summary="租户生命周期变更影响预览")
def tenant_transition_preview(tenant_id: int, action: str, body: dict = Body(default={}),
                              user=Depends(require_platform_capability("tenant.view"))):
    from app.services.tenant_effective_state_service import preview_transition
    return success(preview_transition(tenant_id, action, body))


@router.post("/tenants/{tenant_id}/transitions/{action}", summary="租户生命周期权威变更")
def tenant_transition_apply(tenant_id: int, action: str, body: dict = Body(...),
                            user=Depends(require_platform_capability("commercial.manage"))):
    from app.services.tenant_effective_state_service import apply_transition
    out = apply_transition(
        tenant_id, action, reason=body.get("reason"),
        expected_version=_expected_version(body, operation="租户变更"), payload=body,
    )
    _audit("PLATFORM_TENANT_TRANSITION", str(tenant_id), out, tenant_id=tenant_id)
    return success(out)


@router.get("/access-assignments", summary="平台职责分配")
def access_assignments(user=Depends(require_platform_capability("access.review"))):
    from app.services.platform_access_governance_service import ASSIGNMENT, list_records
    return success({"items": list_records(ASSIGNMENT)})


@router.post("/access-assignments", summary="保存平台职责分配")
def access_assignment_save(body: dict = Body(...), user=Depends(require_platform_capability("access.manage"))):
    from app.services.platform_access_governance_service import save_access_assignment
    out = save_access_assignment(body)
    _audit("PLATFORM_ACCESS_ASSIGNMENT_SAVE", str(out.get("id") or ""), {
        "targetUserId": out.get("userId"),
        "dutyCode": out.get("dutyCode"),
        "reason": out.get("reason"),
        "expiresAt": out.get("expiresAt"),
    })
    return success(out)


@router.get("/elevation-sessions", summary="临时权限提升会话")
def elevation_sessions(user=Depends(require_platform_capability("access.review"))):
    from app.services.platform_access_governance_service import ELEVATION, list_records
    return success({"items": list_records(ELEVATION)})


@router.post("/elevation-sessions", summary="创建自动到期的临时提升")
def elevation_session_create(body: dict = Body(...), user=Depends(require_platform_capability("access.manage"))):
    from app.services.platform_access_governance_service import create_elevation
    out = create_elevation(body)
    _audit("PLATFORM_ELEVATION_CREATE", str(out.get("id") or ""), {
        "targetUserId": out.get("userId"),
        "capabilities": out.get("capabilities"),
        "approvedBy": out.get("approvedBy"),
        "reason": out.get("reason"),
        "expiresAt": out.get("expiresAt"),
    })
    return success(out)


@router.get("/support-sessions", summary="受控学校协助会话")
def support_sessions(tenantId: int | None = Query(default=None),
                     user=Depends(require_platform_capability("support.request"))):
    from app.services.platform_access_governance_service import SUPPORT, list_records
    return success({"items": list_records(SUPPORT, tenant_id=tenantId)})


@router.post("/support-sessions", summary="创建绑定工单/事件的受控协助")
def support_session_create(body: dict = Body(...), user=Depends(require_platform_capability("support.request"))):
    from app.services.platform_access_governance_service import create_support_session
    payload = {**body, "operatorUserId": user.get("userId")}
    out = create_support_session(payload)
    _audit("PLATFORM_SUPPORT_SESSION_CREATE", str(out.get("id") or ""), {
        "operatorUserId": out.get("operatorUserId"),
        "tenantId": out.get("tenantId"),
        "ticketId": out.get("ticketId"),
        "incidentId": out.get("incidentId"),
        "scopes": out.get("scopes"),
        "reason": out.get("reason"),
        "expiresAt": out.get("expiresAt"),
    }, tenant_id=int(out.get("tenantId") or 0))
    return success(out)


@router.get("/access-reviews", summary="平台访问复核")
def access_reviews(user=Depends(require_platform_capability("access.review"))):
    from app.services.platform_access_governance_service import REVIEW, list_records
    return success({"items": list_records(REVIEW)})


@router.get("/reconciliations", summary="合同、授权、配额与实际消费只读对账")
def reconciliations(tenantId: int | None = Query(default=None),
                    user=Depends(require_platform_capability("commercial.view"))):
    from app.services.entitlement_reconciliation_service import list_reconciliations
    return success({"items": list_reconciliations(tenantId)})


# ── PLAT-08 服务目录、依赖与租户影响地图 ────────────────────────────────────
# 注：细粒度 capability（如 service.view/service.manage）需要在
# platform_access_governance_service.py 的 DUTY_CAPABILITIES 里登记，
# 该文件不在本卡白名单内；沿用现有 require_platform_super_admin 硬门槛，
# 与本文件里未接入 capability 系统的大多数路由口径一致。

@router.get("/services/overview", summary="服务目录治理首屏结论")
def service_catalog_overview(user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    return success(svcat.governance_overview())


@router.post("/services/bootstrap", summary="幂等登记首版默认服务（API/PC/门户/小程序/MySQL/Redis/Worker/COS/ClamAV/短信）")
def service_catalog_bootstrap(user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    created = svcat.bootstrap_default_services()
    _audit("PLATFORM_SERVICE_CATALOG_BOOTSTRAP", "bootstrap", {"created": created})
    return success({"created": created}, message="默认服务已登记")


@router.get("/services", summary="服务目录列表")
def services_list(user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    items = svcat.list_services()
    return success({"items": items, "total": len(items)})


@router.post("/services", summary="新建/更新服务条目")
def services_upsert(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    out = svcat.upsert_service(body, expected_version=body.get("expectedVersion"))
    _audit("PLATFORM_SERVICE_CATALOG_UPSERT", out["serviceCode"], out)
    return success(out, message="服务条目已保存")


@router.get("/service-dependencies", summary="服务依赖边列表")
def service_dependencies_list(serviceCode: Optional[str] = Query(default=None),
                              user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    items = svcat.list_dependencies(serviceCode)
    return success({"items": items, "total": len(items)})


@router.post("/service-dependencies", summary="新增服务依赖（拒绝成环）")
def service_dependencies_add(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    out = svcat.add_dependency(body.get("serviceCode"), body.get("dependsOnServiceCode"),
                               dependency_type=body.get("dependencyType") or "HARD")
    _audit("PLATFORM_SERVICE_DEPENDENCY_ADD", f"{out['serviceCode']}->{out['dependsOnServiceCode']}", out)
    return success(out, message="依赖已登记")


@router.delete("/service-dependencies/{dependency_id}", summary="删除服务依赖")
def service_dependencies_remove(dependency_id: int, user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    svcat.remove_dependency(dependency_id)
    _audit("PLATFORM_SERVICE_DEPENDENCY_REMOVE", str(dependency_id), {})
    return success({"dependencyId": str(dependency_id)}, message="依赖已删除")


@router.get("/service-impact", summary="故障影响面：直接/间接受影响租户与服务")
def service_impact(serviceCode: str = Query(...), releaseId: Optional[str] = Query(default=None),
                   user=Depends(require_platform_super_admin)):
    from app.services import service_catalog_service as svcat
    out = svcat.compute_service_impact(serviceCode)
    out["releaseId"] = releaseId
    return success(out)


# ── PLAT-04 租户自动开通、初始化与上线验收 ───────────────────────────────────
@router.get("/provisioning-jobs/overview", summary="开通治理首屏结论")
def provisioning_overview(user=Depends(require_platform_capability("tenant.view"))):
    from app.services import tenant_provisioning_service as prov
    return success(prov.governance_overview())


@router.get("/provisioning-jobs", summary="开通任务列表")
def provisioning_jobs_list(user=Depends(require_platform_capability("tenant.view"))):
    from app.services import tenant_provisioning_service as prov
    items = prov.list_jobs()
    return success({"items": items, "total": len(items)})


@router.post("/provisioning-jobs", summary="发起/续跑开通任务（按idempotencyKey幂等）")
def provisioning_jobs_create(body: dict = Body(...),
                             user=Depends(require_platform_capability("provisioning.manage"))):
    from app.services import tenant_provisioning_service as prov
    out = prov.start_provisioning_job(user, body)
    _audit("PLATFORM_PROVISIONING_START", out["jobId"],
          {"tenantCode": out["tenantCode"], "status": out["status"]})
    return success(out, message="开通任务已受理")


@router.get("/provisioning-jobs/{job_id}", summary="开通任务详情")
def provisioning_job_get(job_id: int, user=Depends(require_platform_capability("tenant.view"))):
    from app.services import tenant_provisioning_service as prov
    return success(prov.get_job(job_id))


@router.post("/provisioning-jobs/{job_id}/resume", summary="续跑开通任务")
def provisioning_job_resume(job_id: int, user=Depends(require_platform_capability("provisioning.manage"))):
    from app.services import tenant_provisioning_service as prov
    out = prov.run_provisioning_job(job_id, user=user)
    _audit("PLATFORM_PROVISIONING_RESUME", str(job_id), {"status": out["status"]})
    return success(out, message="已续跑")


@router.post("/provisioning-jobs/{job_id}/retry-step", summary="重试指定失败步骤")
def provisioning_job_retry_step(job_id: int, body: dict = Body(...),
                                user=Depends(require_platform_capability("provisioning.manage"))):
    from app.services import tenant_provisioning_service as prov
    out = prov.retry_step(job_id, body.get("stepCode") or "", user=user)
    _audit("PLATFORM_PROVISIONING_RETRY_STEP", str(job_id),
          {"stepCode": body.get("stepCode"), "status": out["status"]})
    return success(out, message="已重试")


@router.post("/provisioning-jobs/{job_id}/compensate", summary="对失败步骤发起补偿（高危，需理由）")
def provisioning_job_compensate(job_id: int, body: dict = Body(...),
                                user=Depends(require_platform_super_admin)):
    from app.services import tenant_provisioning_service as prov
    out = prov.compensate_step(job_id, body.get("stepCode") or "",
                               reason=body.get("reason") or "", user=user)
    _audit("PLATFORM_PROVISIONING_COMPENSATE", str(job_id),
          {"stepCode": body.get("stepCode"), "reason": body.get("reason")})
    return success(out, message="补偿已执行")


@router.post("/provisioning-jobs/{job_id}/flag-manual-review", summary="转人工队列（补偿也解决不了）")
def provisioning_job_flag_manual(job_id: int, body: dict = Body(...),
                                 user=Depends(require_platform_super_admin)):
    from app.services import tenant_provisioning_service as prov
    out = prov.flag_manual_review(job_id, body.get("stepCode") or "",
                                  reason=body.get("reason") or "", user=user)
    _audit("PLATFORM_PROVISIONING_MANUAL_REVIEW", str(job_id),
          {"stepCode": body.get("stepCode"), "reason": body.get("reason")})
    return success(out, message="已转人工队列")


@router.post("/provisioning-jobs/{job_id}/cancel", summary="取消开通任务（高危，需理由）")
def provisioning_job_cancel(job_id: int, body: dict = Body(...),
                            user=Depends(require_platform_super_admin)):
    from app.services import tenant_provisioning_service as prov
    out = prov.cancel_job(job_id, reason=body.get("reason") or "", user=user)
    _audit("PLATFORM_PROVISIONING_CANCEL", str(job_id), {"reason": body.get("reason")})
    return success(out, message="已取消")


# ── PLAT-09 事件、状态页与统一学校通知 ───────────────────────────────────────
@router.get("/incidents/overview", summary="事件治理首屏结论")
def incidents_overview(user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    return success(inc.governance_overview())


@router.get("/incidents", summary="事件列表")
def incidents_list(status: Optional[str] = Query(default=None),
                   user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    items = inc.list_incidents(status=status)
    return success({"items": items, "total": len(items)})


@router.post("/incidents", summary="创建事件（受影响租户按当前依赖图快照一次）")
def incidents_create(body: dict = Body(...), user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    out = inc.create_incident(user, body)
    _audit("PLATFORM_INCIDENT_CREATE", out["incidentId"],
          {"title": out["title"], "severity": out["severity"],
           "affectedServiceCodes": out["affectedServiceCodes"]})
    return success(out, message="事件已登记")


@router.get("/incidents/{incident_id}", summary="事件详情（含内部时间线，仅平台侧可见）")
def incident_get(incident_id: int, user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    return success(inc.get_incident(incident_id, include_internal=True))


@router.get("/incidents/{incident_id}/affected-tenants", summary="受影响租户快照")
def incident_affected_tenants(incident_id: int,
                              user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    detail = inc.get_incident(incident_id, include_internal=False)
    return success({"items": detail.get("affectedTenants", [])})


@router.post("/incidents/{incident_id}/status", summary="推进事件状态（不可倒退）")
def incident_transition(incident_id: int, body: dict = Body(...),
                        user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    out = inc.transition_status(incident_id, body.get("status") or "", user=user)
    _audit("PLATFORM_INCIDENT_STATUS", str(incident_id), {"status": out["status"]})
    return success(out, message="状态已更新")


@router.post("/incidents/{incident_id}/updates", summary="新增一条事件更新（草稿，未发布）")
def incident_add_update(incident_id: int, body: dict = Body(...),
                        user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    out = inc.add_update(incident_id, body, user=user)
    _audit("PLATFORM_INCIDENT_UPDATE_DRAFT", str(incident_id), {"updateId": out["updateId"]})
    return success(out, message="更新已保存")


@router.post("/incidents/{incident_id}/updates/{update_id}/publish", summary="发布更新并通知受影响租户")
def incident_publish_update(incident_id: int, update_id: int,
                            user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    out = inc.publish_update(incident_id, update_id, user=user)
    _audit("PLATFORM_INCIDENT_PUBLISH", str(incident_id),
          {"updateId": out["updateId"], "result": out["notificationResult"]})
    return success(out, message="已发布通知")


@router.post("/incidents/{incident_id}/request-problem-conversion", summary="RESOLVED事件申请转Problem")
def incident_request_problem(incident_id: int, user=Depends(require_platform_capability("incident.manage"))):
    from app.services import incident_service as inc
    out = inc.request_problem_conversion(incident_id, user=user)
    _audit("PLATFORM_INCIDENT_PROBLEM_CONVERSION_REQUEST", str(incident_id), {})
    return success(out, message="已登记转Problem申请")


# ── PLAT-11 变更、发布、兼容性、灰度与回滚 ───────────────────────────────────
@router.get("/changes/overview", summary="变更治理首屏结论")
def changes_overview(user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    return success(chg.governance_overview())


@router.get("/changes", summary="变更列表")
def changes_list(status: Optional[str] = Query(default=None),
                 user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    items = chg.list_changes(status=status)
    return success({"items": items, "total": len(items)})


@router.post("/changes", summary="创建变更请求（DRAFT）")
def changes_create(body: dict = Body(...), user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    out = chg.create_change(user, body)
    _audit("PLATFORM_CHANGE_CREATE", out["changeId"], {"title": out["title"], "changeType": out["changeType"]})
    return success(out, message="变更请求已创建")


@router.get("/changes/{change_id}", summary="变更详情")
def change_get(change_id: int, user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    return success(chg.get_change(change_id))


@router.post("/changes/{change_id}/assess", summary="评估变更（计算受影响服务与租户快照）")
def change_assess(change_id: int, user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    out = chg.assess(change_id, user=user)
    _audit("PLATFORM_CHANGE_ASSESS", str(change_id), {"affectedTenants": len(out.get("affectedTenants", []))})
    return success(out, message="已评估")


@router.post("/changes/{change_id}/approve", summary="审批变更（须与发起人不同）")
def change_approve(change_id: int, body: dict = Body(...),
                   user=Depends(require_platform_super_admin)):
    from app.services import change_management_service as chg
    out = chg.approve(change_id, user=user, reason=body.get("reason") or "")
    _audit("PLATFORM_CHANGE_APPROVE", str(change_id), {"reason": body.get("reason")})
    return success(out, message="已审批通过")


@router.post("/changes/{change_id}/schedule", summary="排期（冻结窗口冲突时拒绝）")
def change_schedule(change_id: int, body: dict | None = Body(default=None),
                    user=Depends(require_platform_capability("operations.manage"))):
    from datetime import datetime as _dt

    from app.services import change_management_service as chg
    payload = body if isinstance(body, dict) else {}
    scheduled_at = _dt.fromisoformat(payload["scheduledAt"]) if payload.get("scheduledAt") else None
    out = chg.schedule(change_id, user=user, scheduled_at=scheduled_at)
    _audit("PLATFORM_CHANGE_SCHEDULE", str(change_id), {"scheduledAt": out["scheduledAt"]})
    return success(out, message="已排期")


@router.post("/changes/{change_id}/start-wave", summary="开始一个灰度批次")
def change_start_wave(change_id: int, body: dict = Body(...),
                      user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    out = chg.start_wave(change_id, wave_no=int(body.get("waveNo") or 1),
                         tenant_ids=body.get("tenantIds") or [], user=user)
    _audit("PLATFORM_CHANGE_WAVE_START", str(change_id), out)
    return success(out, message="灰度批次已开始")


@router.post("/changes/{change_id}/waves/{wave_no}/report", summary="上报灰度批次结果（失败即停止扩展并回滚）")
def change_wave_report(change_id: int, wave_no: int, body: dict = Body(...),
                       user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    out = chg.report_wave_result(change_id, wave_no, status=body.get("status") or "",
                                 error=body.get("error"), user=user)
    _audit("PLATFORM_CHANGE_WAVE_REPORT", str(change_id), out)
    return success(out, message="已记录批次结果")


@router.post("/changes/{change_id}/verify", summary="验证通过（全部灰度批次成功后才允许）")
def change_verify(change_id: int, user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    out = chg.verify(change_id, user=user)
    _audit("PLATFORM_CHANGE_VERIFY", str(change_id), {})
    return success(out, message="已验证通过")


@router.post("/changes/{change_id}/fail", summary="标记变更失败")
def change_fail(change_id: int, body: dict = Body(...),
                user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    out = chg.fail(change_id, reason=body.get("reason") or "", user=user)
    _audit("PLATFORM_CHANGE_FAIL", str(change_id), {"reason": body.get("reason")})
    return success(out, message="已标记失败")


@router.post("/changes/{change_id}/rollback", summary="回滚变更（高危）")
def change_rollback(change_id: int, body: dict = Body(...),
                    user=Depends(require_platform_super_admin)):
    from app.services import change_management_service as chg
    out = chg.rollback(change_id, reason=body.get("reason") or "", user=user)
    _audit("PLATFORM_CHANGE_ROLLBACK", str(change_id), {"reason": body.get("reason")})
    return success(out, message="已回滚")


@router.get("/maintenance-windows", summary="平台全局冻结期列表")
def maintenance_windows_list(user=Depends(require_platform_capability("operations.manage"))):
    from app.services import change_management_service as chg
    items = chg.list_maintenance_windows()
    return success({"items": items, "total": len(items)})


@router.post("/maintenance-windows", summary="登记平台全局冻结期")
def maintenance_windows_create(body: dict = Body(...),
                               user=Depends(require_platform_super_admin)):
    from app.services import change_management_service as chg
    out = chg.upsert_maintenance_window(user, body)
    _audit("PLATFORM_MAINTENANCE_WINDOW_CREATE", out["id"], out)
    return success(out, message="冻结期已登记")
