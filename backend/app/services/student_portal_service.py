"""学生 PC 门户 · 租户配置服务。

职责：
- get_config(tenant_id)：合并「默认 < 套餐能力上限 < 租户覆盖 < 总开关」，下发最终门户配置（安全默认，绝不 500）。
- update_config(tenant_id, body, ...)：校验 + 落库（TenantPortalConfig.config_json）+ 返回最新。
- assert_feature(tenant_id, feature)：后端功能开关强校验（前端隐藏按钮不作数）。
不写死学校名/Logo/主色（来自 TenantBrandConfig）；不写死任何租户是否开通（来自 config_json）。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker

# ── 模块 / 功能键（与设计文档、前端 registry 对齐）──
MODULE_KEYS = ["dashboard", "profile", "orientation", "campusService",
               "academic", "internship", "graduation", "employment", "messages"]
FEATURE_KEYS = ["upload", "export", "proofDownload", "profileCorrection",
                "messageReceipt", "materialCenter", "workItems", "aiAssistant"]

DEFAULT_MODULES = {k: True for k in MODULE_KEYS}
DEFAULT_FEATURES = {k: True for k in FEATURE_KEYS}
DEFAULT_FEATURES["aiAssistant"] = False  # AI 助手默认关闭（专业版及以上才可开）

# 套餐能力上限：features 的白名单；租户即使勾选，超出套餐上限的一律置 false。
PACKAGES = {
    "trial":        {"name": "试用版",  "features": {"upload", "proofDownload", "messageReceipt", "workItems"}},
    "standard":     {"name": "标准版",  "features": {"upload", "export", "proofDownload", "profileCorrection",
                                                    "messageReceipt", "materialCenter", "workItems"}},
    "professional": {"name": "专业版",  "features": set(FEATURE_KEYS)},
    "private":      {"name": "私有部署", "features": set(FEATURE_KEYS)},
}
DEFAULT_PACKAGE = "standard"
DEFAULT_ENABLED = True          # 未配置时的安全默认：门户可用（管理员可显式关闭）
DEFAULT_PORTAL_NAME = "学生服务门户"
DEFAULT_PORTAL_URL = "/portal/"
DEFAULT_PRIMARY_COLOR = "#1677ff"

# portalUrl 允许的绝对地址白名单前缀（其余只允许相对路径 /...）
_URL_WHITELIST_PREFIXES = ("http://118.25.143.96", "https://")
_DANGEROUS = ("javascript:", "data:", "vbscript:", "<", ">")


# ─────────────────────────── 读取覆盖配置 ───────────────────────────

def _load_override(tenant_id: int) -> dict:
    """读取租户覆盖配置（无库/无行/异常 → 空 dict，绝不抛错）。"""
    if not db_enabled():
        return {}
    try:
        from sqlalchemy import select
        from app.models import TenantPortalConfig
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(TenantPortalConfig).where(
                TenantPortalConfig.tenant_id == tenant_id,
                TenantPortalConfig.is_deleted.is_(False))).first()
            return dict(row.config_json or {}) if row else {}
        finally:
            db.close()
    except Exception:
        return {}


def _load_brand(tenant_id: int) -> dict:
    """品牌信息（学校名/平台名/主色/水印）来自 TenantBrandConfig + Tenant；缺失用安全默认。"""
    brand = {"schoolName": "", "platformName": DEFAULT_PORTAL_NAME, "logo": "",
             "primaryColor": DEFAULT_PRIMARY_COLOR, "watermark": ""}
    if not db_enabled():
        return brand
    try:
        from sqlalchemy import select
        from app.models import Tenant, TenantBrandConfig
        db = get_sessionmaker()()
        try:
            t = db.get(Tenant, tenant_id)
            if t:
                brand["schoolName"] = t.school_name or ""
                brand["watermark"] = t.short_name or t.school_name or ""
            bc = db.scalars(select(TenantBrandConfig).where(
                TenantBrandConfig.tenant_id == tenant_id,
                TenantBrandConfig.is_deleted.is_(False))).first()
            if bc:
                brand["platformName"] = bc.platform_name or brand["platformName"]
                brand["primaryColor"] = bc.primary_color or brand["primaryColor"]
                brand["watermark"] = bc.watermark_text or brand["watermark"]
        finally:
            db.close()
    except Exception:
        pass
    return brand


# ─────────────────────────── 合并 → 最终配置 ───────────────────────────

def _merge(override: dict, brand: dict) -> dict:
    pkg_code = str(override.get("requiredPackage") or DEFAULT_PACKAGE).strip().lower()
    pkg = PACKAGES.get(pkg_code) or PACKAGES[DEFAULT_PACKAGE]
    caps = pkg["features"]

    enabled = bool(override.get("enabled", DEFAULT_ENABLED))

    ov_modules = override.get("modules") or {}
    modules = {k: bool(ov_modules.get(k, DEFAULT_MODULES[k])) for k in MODULE_KEYS}

    ov_features = override.get("features") or {}
    # 租户选择 AND 套餐上限：超出套餐的一律 false
    features = {k: bool(ov_features.get(k, DEFAULT_FEATURES[k])) and (k in caps) for k in FEATURE_KEYS}

    # 登录账号提示：仅当 override 明确 enabled 且套餐为 trial（演示/试用）才下发，否则空
    tips_in = override.get("loginAccountTips") or {}
    tips_enabled = bool(tips_in.get("enabled")) and pkg_code == "trial"
    login_tips = {"enabled": tips_enabled,
                  "accounts": (tips_in.get("accounts") or []) if tips_enabled else []}

    return {
        "enabled": enabled,
        "portalName": str(override.get("portalName") or DEFAULT_PORTAL_NAME),
        "portalUrl": str(override.get("portalUrl") or DEFAULT_PORTAL_URL),
        "brand": {
            "schoolName": brand.get("schoolName") or "",
            "platformName": str(override.get("portalName") or brand.get("platformName") or DEFAULT_PORTAL_NAME),
            "logo": brand.get("logo") or "",
            "primaryColor": brand.get("primaryColor") or DEFAULT_PRIMARY_COLOR,
            "watermark": brand.get("watermark") or brand.get("schoolName") or "",
        },
        "modules": modules,
        "features": features,
        "package": {"code": pkg_code, "name": pkg["name"]},
        "loginAccountTips": login_tips,
    }


def get_config(tenant_id: int) -> dict:
    """下发给学生门户的最终配置（安全默认，绝不 500，绝不跨租户）。"""
    tid = int(tenant_id or 0)
    if not tid:
        # 无租户上下文：返回未开通安全态，不泄露、不 500
        return _merge({"enabled": False}, {})
    return _merge(_load_override(tid), _load_brand(tid))


# ─────────────────────────── 校验 + 落库 ───────────────────────────

def _clean_text(v, max_len: int = 200) -> str:
    s = str(v or "").strip()
    if any(d in s for d in ("<", ">")):
        raise AppException("VALIDATION_ERROR", "文本字段不允许包含尖括号等脚本字符")
    return s[:max_len]


def _validate_url(v) -> str:
    s = str(v or "").strip()
    if not s:
        return DEFAULT_PORTAL_URL
    low = s.lower()
    if any(d in low for d in _DANGEROUS):
        raise AppException("VALIDATION_ERROR", "portalUrl 含非法字符")
    if s.startswith("/"):
        return s[:300]
    if any(low.startswith(p) for p in _URL_WHITELIST_PREFIXES):
        return s[:300]
    raise AppException("VALIDATION_ERROR", "portalUrl 只允许相对路径(/...)或白名单域名(https://)")


def _bool_map(src, keys, defaults) -> dict:
    src = src or {}
    return {k: bool(src.get(k, defaults[k])) for k in keys}


def _sanitize_login_tips(tips, pkg_code: str) -> dict:
    """登录账号提示：仅演示/试用租户(trial)可启用；且只保留展示文案，不落真实敏感密码。"""
    tips = tips or {}
    if pkg_code != "trial" or not tips.get("enabled"):
        return {"enabled": False, "accounts": []}
    accounts = []
    for a in (tips.get("accounts") or [])[:6]:
        a = a or {}
        # 只存展示用文案：机构名/演示登录名/密码提示（不接收/不落任何真实生产密码字段）
        accounts.append({
            "label": _clean_text(a.get("label"), 60),
            "loginName": _clean_text(a.get("loginName"), 60),
            "passwordHint": _clean_text(a.get("passwordHint") or a.get("password"), 40),
        })
    return {"enabled": True, "accounts": accounts}


def update_config(tenant_id: int, body: dict, operator: dict | None = None) -> dict:
    """校验并写入租户门户覆盖配置，返回合并后的最新配置。写审计。"""
    tid = int(tenant_id or 0)
    if not tid:
        raise AppException("VALIDATION_ERROR", "缺少 tenantId")
    if not db_enabled():
        raise AppException("SERVER_ERROR", "配置写入需启用数据库")

    body = body or {}
    pkg_code = str(body.get("requiredPackage") or DEFAULT_PACKAGE).strip().lower()
    if pkg_code not in PACKAGES:
        raise AppException("VALIDATION_ERROR", f"未知套餐：{pkg_code}（支持 {'/'.join(PACKAGES)}）")

    override = {
        "enabled": bool(body.get("enabled", DEFAULT_ENABLED)),
        "portalName": _clean_text(body.get("portalName") or DEFAULT_PORTAL_NAME, 60),
        "portalUrl": _validate_url(body.get("portalUrl")),
        "requiredPackage": pkg_code,
        "modules": _bool_map(body.get("modules"), MODULE_KEYS, DEFAULT_MODULES),
        "features": _bool_map(body.get("features"), FEATURE_KEYS, DEFAULT_FEATURES),
        "loginAccountTips": _sanitize_login_tips(body.get("loginAccountTips"), pkg_code),
    }

    from sqlalchemy import select
    from app.models import TenantPortalConfig
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantPortalConfig).where(
            TenantPortalConfig.tenant_id == tid)).first()
        before = dict(row.config_json or {}) if row else {}
        if row:
            row.config_json = override
        else:
            db.add(TenantPortalConfig(tenant_id=tid, config_json=override))
        db.commit()
    finally:
        db.close()

    # 审计：TENANT_STUDENT_PORTAL_CONFIG / UPDATE（before/after 摘要，不含敏感密钥）
    try:
        from app.services import audit_log
        audit_log.record("TENANT_STUDENT_PORTAL_CONFIG", f"tenant:{tid}",
                         detail={"action": "UPDATE", "tenantId": tid,
                                 "operatorId": (operator or {}).get("userId"),
                                 "beforeEnabled": before.get("enabled"),
                                 "afterEnabled": override["enabled"],
                                 "package": pkg_code})
    except Exception:
        pass
    return get_config(tid)


# ─────────────────────────── 后端功能开关强校验 ───────────────────────────

def assert_feature(tenant_id: int, feature: str) -> None:
    """后端强校验：门户未开通或该功能关闭 → 403。用于 upload/export 等敏感操作的服务端兜底。"""
    cfg = get_config(tenant_id)
    if not cfg.get("enabled"):
        raise AppException("NO_PERMISSION", "学生门户未开通，请联系学校管理员")
    if not cfg.get("features", {}).get(feature):
        raise AppException("NO_PERMISSION", f"该功能（{feature}）未开通，请联系学校管理员")
