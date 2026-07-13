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
    if user.get("currentRoleCode") != PLATFORM_ROLE and user.get("userType") != PLATFORM_ROLE:
        audit_log.record("PERMISSION_DENIED", f"platform:{request.url.path}",
                         detail={"path": request.url.path, "method": request.method,
                                 "role": user.get("currentRoleCode"), "userType": user.get("userType")},
                         result="DENIED")
        raise AppException("NO_PERMISSION", "仅平台超级管理员可访问平台总控")
    return user


def _audit(action: str, resource: str, detail: dict | None = None):
    audit_log.record(action, resource, detail=detail or {}, result="SUCCESS")


# ── §二 总览 ──

@router.get("/overview", summary="平台经营总览")
def overview(user=Depends(require_platform_super_admin)):
    return success(svc.overview())


# ── §三 租户全托管 ──

@router.get("/tenants", summary="租户列表（keyword/status 过滤）")
def tenants(keyword: Optional[str] = Query(default=None), status: Optional[str] = Query(default=None),
            user=Depends(require_platform_super_admin)):
    items = svc.list_tenants(keyword, status)
    return success({"list": items, "total": len(items)})


@router.post("/tenants", summary="新建租户（学校）")
def tenant_create(body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = svc.create_tenant(body)
    _audit("PLATFORM_TENANT_CREATE", out["tenantCode"], {"tenantId": out["tenantId"]})
    return success(out, message="租户已创建")


@router.get("/tenants/{tenant_id}", summary="租户详情")
def tenant_get(tenant_id: int, user=Depends(require_platform_super_admin)):
    return success(svc.get_tenant(tenant_id))


@router.put("/tenants/{tenant_id}", summary="租户基础信息修改")
def tenant_update(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    allow = {"schoolType", "province", "city", "contactName", "contactPhone", "contactWechat",
             "environment", "remark"}
    out = svc.update_tenant_meta(tenant_id, {k: v for k, v in body.items() if k in allow})
    _audit("PLATFORM_TENANT_UPDATE", str(tenant_id))
    return success(out)


@router.post("/tenants/{tenant_id}/enable", summary="启用租户")
def tenant_enable(tenant_id: int, user=Depends(require_platform_super_admin)):
    out = svc.update_tenant_meta(tenant_id, {"status": "active"})
    _audit("PLATFORM_TENANT_ENABLE", str(tenant_id))
    return success(out, message="已启用")


@router.post("/tenants/{tenant_id}/disable", summary="停用租户（该校全员即刻无法登录）")
def tenant_disable(tenant_id: int, user=Depends(require_platform_super_admin)):
    out = svc.update_tenant_meta(tenant_id, {"status": "disabled"})
    _audit("PLATFORM_TENANT_DISABLE", str(tenant_id))
    return success(out, message="已停用，该校账号将无法登录")


@router.post("/tenants/{tenant_id}/extend-trial", summary="延长试用（days）")
def tenant_extend_trial(tenant_id: int, body: dict = Body(default={}),
                        user=Depends(require_platform_super_admin)):
    from datetime import datetime, timedelta
    days = int(body.get("days") or 7)
    if not 1 <= days <= 365:
        raise AppException("VALIDATION_ERROR", "延长天数需在 1~365 之间")
    meta = svc.tenant_meta(tenant_id)
    base = meta.get("expireAt") or meta.get("trialEndAt")
    try:
        start = max(datetime.fromisoformat(base), datetime.now()) if base else datetime.now()
    except ValueError:
        start = datetime.now()
    new_end = (start + timedelta(days=days)).isoformat(timespec="seconds")
    out = svc.update_tenant_meta(tenant_id, {"trialEndAt": new_end, "expireAt": new_end,
                                             "status": meta.get("status") if meta.get("status") == "active" else "trial"})
    _audit("PLATFORM_TENANT_EXTEND_TRIAL", str(tenant_id), {"days": days, "newExpireAt": new_end})
    return success(out, message=f"已延长 {days} 天")


@router.post("/tenants/{tenant_id}/convert-to-paid", summary="试用转正式（packageCode + 时长）")
def tenant_convert(tenant_id: int, body: dict = Body(default={}),
                   user=Depends(require_platform_super_admin)):
    from datetime import datetime, timedelta
    pkg = svc.get_package(str(body.get("packageCode") or "standard"))
    days = int(body.get("durationDays") or pkg["durationDays"])
    new_end = (datetime.now() + timedelta(days=days)).isoformat(timespec="seconds")
    out = svc.update_tenant_meta(tenant_id, {"status": "active", "packageCode": pkg["packageCode"],
                                             "expireAt": new_end})
    _audit("PLATFORM_TENANT_CONVERT_PAID", str(tenant_id),
           {"packageCode": pkg["packageCode"], "expireAt": new_end})
    return success(out, message=f"已开通 {pkg['packageName']}")


@router.post("/tenants/{tenant_id}/expire", summary="手动标记到期（转只读）")
def tenant_expire(tenant_id: int, user=Depends(require_platform_super_admin)):
    from datetime import datetime, timedelta
    past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    out = svc.update_tenant_meta(tenant_id, {"status": "expired", "expireAt": past})
    _audit("PLATFORM_TENANT_EXPIRE", str(tenant_id))
    return success(out, message="已标记到期（租户进入只读）")


@router.post("/tenants/{tenant_id}/change-package", summary="变更套餐")
def tenant_change_package(tenant_id: int, body: dict = Body(...),
                          user=Depends(require_platform_super_admin)):
    pkg = svc.get_package(str(body.get("packageCode") or ""))
    if pkg["packageCode"] != body.get("packageCode"):
        raise AppException("VALIDATION_ERROR", "packageCode 不存在")
    out = svc.update_tenant_meta(tenant_id, {"packageCode": pkg["packageCode"],
                                             "maxStudents": None, "maxUsers": None,
                                             "storageLimitMb": None})
    _audit("PLATFORM_TENANT_CHANGE_PACKAGE", str(tenant_id), {"packageCode": pkg["packageCode"]})
    return success(out, message=f"已切换为 {pkg['packageName']}")


@router.post("/tenants/{tenant_id}/quota", summary="租户级容量覆盖（maxStudents/maxUsers/storageLimitMb）")
def tenant_quota(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    patch = {}
    for k in ("maxStudents", "maxUsers", "storageLimitMb"):
        if k in body:
            v = body[k]
            if not isinstance(v, int) or not 1 <= v <= 1000000:
                raise AppException("VALIDATION_ERROR", f"{k} 需为 1~1000000 的整数")
            patch[k] = v
    if not patch:
        raise AppException("VALIDATION_ERROR", "至少提供一个容量参数")
    out = svc.update_tenant_meta(tenant_id, patch)
    _audit("PLATFORM_TENANT_QUOTA", str(tenant_id), patch)
    return success(out)


@router.post("/tenants/{tenant_id}/reset-demo-data", summary="重置演示数据（仅 demo-school）")
def tenant_reset_demo(tenant_id: int, user=Depends(require_platform_super_admin)):
    if tenant_id != svc.DEMO_TID:
        raise AppException("NO_PERMISSION", "仅演示租户 demo-school 支持重置演示数据")
    out = svc.reset_demo_data()
    _audit("PLATFORM_DEMO_RESET", str(tenant_id), out)
    return success(out, message="演示数据已重置为基线（5 名学生）")


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
    cur = svc.get_package(package_code)
    allow = {"packageName", "price", "durationDays", "maxStudents", "maxUsers",
             "storageLimitMb", "features", "enabled", "remark"}
    merged = {**cur, **{k: v for k, v in body.items() if k in allow},
              "packageCode": package_code}
    if isinstance(body.get("features"), dict):
        merged["features"] = {**cur.get("features", {}),
                              **{k: bool(v) for k, v in body["features"].items() if k in D.FEATURE_KEYS}}
    for k in ("durationDays", "maxStudents", "maxUsers", "storageLimitMb"):
        if not isinstance(merged.get(k), int) or merged[k] < 1:
            raise AppException("VALIDATION_ERROR", f"{k} 需为正整数")
    svc.put_config_json(0, "PACKAGE", package_code, merged)
    _audit("PLATFORM_PACKAGE_UPDATE", package_code)
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
    cur.update(patch)
    svc.put_config_json(tenant_id, "FEATURES", "-", cur)
    _audit("PLATFORM_FEATURES_UPDATE", str(tenant_id), patch)
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
    _audit("PLATFORM_RULES_UPDATE", str(tenant_id), {"groups": list(payload)})
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
    _audit("PLATFORM_WORKFLOW_UPDATE", f"{tenant_id}:{workflow_code}")
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
    cur.update(patch)
    svc.put_config_json(tenant_id, "BRAND", "-", cur)
    _audit("PLATFORM_BRAND_UPDATE", str(tenant_id), {"keys": list(patch)})
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
    _audit("PLATFORM_USER_CREATE", f"{tenant_id}:{login_name}")
    return success(out, message="账号已创建，初始密码仅本次显示")


@router.post("/users/{user_id}/enable", summary="启用账号")
def user_enable(user_id: int, user=Depends(require_platform_super_admin)):
    out = svc.set_user_status(user_id, "ACTIVE")
    _audit("PLATFORM_USER_ENABLE", str(user_id))
    return success(out)


@router.post("/users/{user_id}/disable", summary="停用账号")
def user_disable(user_id: int, user=Depends(require_platform_super_admin)):
    out = svc.set_user_status(user_id, "DISABLED")
    _audit("PLATFORM_USER_DISABLE", str(user_id))
    return success(out)


@router.post("/users/{user_id}/reset-password", summary="重置密码（新密码仅显示一次，不写日志）")
def user_reset_pwd(user_id: int, user=Depends(require_platform_super_admin)):
    out = svc.reset_user_password(user_id)
    _audit("PLATFORM_USER_RESET_PWD", str(user_id))  # 不含密码
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
def order_paid(order_no: str, user=Depends(require_platform_super_admin)):
    out = svc.order_action(order_no, "mark-paid")
    _audit("PLATFORM_ORDER_PAID", order_no)
    return success(out, message="已入账并开通")


@router.post("/orders/{order_no}/cancel", summary="取消订单")
def order_cancel(order_no: str, user=Depends(require_platform_super_admin)):
    out = svc.order_action(order_no, "cancel")
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
