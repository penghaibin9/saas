"""P6 · 平台总控服务：配置存取（全局←套餐←租户三级合并）、租户运营操作、总览聚合。"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.core.security import hash_password
from app.db.session import db_enabled, get_sessionmaker
from app.services import platform_defaults as D

MAIN_TID = 1000000000000000001
DEMO_TID = 1000000000000000003


def _require_db():
    if not db_enabled():
        raise AppException("SERVER_ERROR", "平台总控需要 DB_ENABLED=true")


def session():
    return get_sessionmaker()()


# ═══ 配置 KV ═══

def _get_cfg(db, tenant_id: int, ctype: str, key: str = "-"):
    from app.models import PlatformConfig
    return db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == tenant_id, PlatformConfig.config_type == ctype,
        PlatformConfig.config_key == key, PlatformConfig.is_deleted.is_(False))).first()


def get_config_json(tenant_id: int, ctype: str, key: str = "-") -> dict | None:
    with session() as db:
        row = _get_cfg(db, tenant_id, ctype, key)
        return dict(row.config_json) if row else None


def put_config_json(tenant_id: int, ctype: str, key: str, payload: dict, enabled: bool = True) -> dict:
    from app.models import PlatformConfig
    with session() as db:
        row = _get_cfg(db, tenant_id, ctype, key)
        if row:
            row.config_json = payload
            row.enabled = enabled
            row.version += 1
        else:
            row = PlatformConfig(tenant_id=tenant_id, config_type=ctype, config_key=key,
                                 config_json=payload, enabled=enabled)
            db.add(row)
        db.commit()
        return dict(payload)


def list_configs(ctype: str, tenant_id: int | None = None) -> list[dict]:
    from app.models import PlatformConfig
    with session() as db:
        q = select(PlatformConfig).where(PlatformConfig.config_type == ctype,
                                         PlatformConfig.is_deleted.is_(False))
        if tenant_id is not None:
            q = q.where(PlatformConfig.tenant_id == tenant_id)
        return [{"tenantId": str(r.tenant_id), "key": r.config_key, "enabled": r.enabled,
                 **dict(r.config_json)} for r in db.scalars(q.order_by(PlatformConfig.id)).all()]


# ═══ 有效配置（三级合并）═══

def get_package(package_code: str) -> dict:
    stored = get_config_json(0, "PACKAGE", package_code)
    base = D.DEFAULT_PACKAGES.get(package_code, D.DEFAULT_PACKAGES["trial"])
    return {**base, **(stored or {})}


def tenant_meta(tenant_id: int) -> dict:
    return get_config_json(tenant_id, "TENANT_META") or {}


def effective_features(tenant_id: int) -> dict:
    meta = tenant_meta(tenant_id)
    pkg = get_package(meta.get("packageCode", "professional"))
    merged = {**D.DEFAULT_FEATURES, **(pkg.get("features") or {})}
    merged.update(get_config_json(tenant_id, "FEATURES") or {})
    return {k: bool(merged.get(k, True)) for k in D.FEATURE_KEYS}


def effective_rules(tenant_id: int) -> dict:
    rules = {g: dict(v) for g, v in D.DEFAULT_RULES.items()}
    override = get_config_json(tenant_id, "RULES") or {}
    for g, kv in override.items():
        if g in rules and isinstance(kv, dict):
            rules[g].update(kv)
    return rules


def rule(tenant_id: int, group: str, key: str):
    return effective_rules(tenant_id).get(group, {}).get(key, D.DEFAULT_RULES.get(group, {}).get(key))


def effective_workflows(tenant_id: int) -> dict:
    flows = {k: dict(v) for k, v in D.DEFAULT_WORKFLOWS.items()}
    override = get_config_json(tenant_id, "WORKFLOWS") or {}
    for k, v in override.items():
        if k in flows and isinstance(v, dict):
            flows[k].update(v)
    return flows


def effective_brand(tenant_id: int) -> dict:
    from app.models import Tenant, TenantBrandConfig
    base = dict(D.DEFAULT_BRAND)
    with session() as db:
        t = db.get(Tenant, tenant_id)
        if t:
            base["schoolName"] = t.school_name
        b = db.scalars(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == tenant_id)).first()
        if b:
            base.update({k: v for k, v in {
                "watermarkText": b.watermark_text, "primaryColor": b.primary_color,
            }.items() if v})
    base.update(get_config_json(tenant_id, "BRAND") or {})
    base["contactPhone"] = base.get("contactPhone") or "13549666867"
    return base


def effective_security() -> dict:
    return {**D.DEFAULT_SECURITY, **(get_config_json(0, "SECURITY") or {})}


def validate_security(payload: dict) -> dict:
    merged = {**effective_security(), **payload}
    for k, (lo, hi) in D.SECURITY_BOUNDS.items():
        v = merged.get(k)
        if not isinstance(v, (int, float)) or not (lo <= v <= hi):
            raise AppException("VALIDATION_ERROR", f"安全参数 {k} 必须在 {lo}~{hi} 之间，拒绝保存")
    if not str(merged.get("corsAllowedOrigins", "")).strip():
        raise AppException("VALIDATION_ERROR", "corsAllowedOrigins 不允许为空（禁止放开跨域限制）")
    return merged


def validate_rules(payload: dict) -> dict:
    for g, kv in (payload or {}).items():
        if g not in D.DEFAULT_RULES:
            raise AppException("VALIDATION_ERROR", f"未知规则分组：{g}")
        if not isinstance(kv, dict):
            raise AppException("VALIDATION_ERROR", f"规则分组 {g} 必须是对象")
        for k, v in kv.items():
            if k not in D.DEFAULT_RULES[g]:
                raise AppException("VALIDATION_ERROR", f"未知规则：{g}.{k}")
            default = D.DEFAULT_RULES[g][k]
            if isinstance(default, bool) and not isinstance(v, bool):
                raise AppException("VALIDATION_ERROR", f"{g}.{k} 需要布尔值")
            if isinstance(default, int) and not isinstance(default, bool):
                if not isinstance(v, int) or v < 0 or v > 1000000:
                    raise AppException("VALIDATION_ERROR", f"{g}.{k} 需要 0~1000000 的整数")
    return payload


# ═══ 租户 ═══

def _tenant_row(db, t, meta: dict) -> dict:
    from app.models import StudentProfile, User
    students = db.scalar(select(func.count()).select_from(StudentProfile).where(
        StudentProfile.tenant_id == t.id, StudentProfile.is_deleted.is_(False))) or 0
    users = db.scalar(select(func.count()).select_from(User).where(
        User.tenant_id == t.id, User.is_deleted.is_(False))) or 0
    pkg = get_package(meta.get("packageCode", "professional"))
    feats = effective_features(t.id)
    return {
        "tenantId": str(t.id), "tenantCode": t.tenant_code, "tenantName": t.school_name,
        "schoolType": meta.get("schoolType", "VOCATIONAL"),
        "province": meta.get("province", ""), "city": meta.get("city", ""),
        "contactName": meta.get("contactName", ""), "contactPhone": meta.get("contactPhone", ""),
        "contactWechat": meta.get("contactWechat", ""),
        "status": meta.get("status", "active" if t.status == "ACTIVE" else "disabled"),
        "environment": meta.get("environment", "production"),
        "packageCode": pkg["packageCode"], "packageName": pkg["packageName"],
        "trialStartAt": meta.get("trialStartAt"), "trialEndAt": meta.get("trialEndAt"),
        "expireAt": meta.get("expireAt"),
        "maxStudents": meta.get("maxStudents", pkg["maxStudents"]),
        "maxUsers": meta.get("maxUsers", pkg["maxUsers"]),
        "storageLimitMb": meta.get("storageLimitMb", pkg["storageLimitMb"]),
        "usedStorageMb": meta.get("usedStorageMb", 0),
        "studentCount": students, "userCount": users,
        **{f"allow{k[0].upper()}{k[1:]}" if not k.startswith("allow") else k: v
           for k, v in {
               "allowImport": feats["studentImport"], "allowExport": feats["studentExport"],
               "allowFileUpload": feats["fileUpload"], "allowMiniapp": feats["miniapp"],
               "allowGraduation": feats["graduation"], "allowInternship": feats["internship"],
               "allowEmployment": feats["employment"], "allowRiskWarning": feats["riskWarning"],
               "allowCustomBrand": feats["customBrand"], "allowWorkflowConfig": feats["workflowConfig"],
               "allowApiAccess": feats["apiAccess"],
           }.items()},
        "createdAt": t.created_at.isoformat(timespec="seconds") if t.created_at else None,
        "updatedAt": t.updated_at.isoformat(timespec="seconds") if t.updated_at else None,
    }


def list_tenants(keyword: str | None = None, status: str | None = None) -> list[dict]:
    _require_db()
    from app.models import Tenant
    with session() as db:
        rows = db.scalars(select(Tenant).where(Tenant.is_deleted.is_(False)).order_by(Tenant.id)).all()
        out = []
        for t in rows:
            meta = tenant_meta(t.id)
            item = _tenant_row(db, t, meta)
            if keyword and keyword not in item["tenantName"] and keyword not in item["tenantCode"]:
                continue
            if status and item["status"] != status:
                continue
            out.append(item)
        return out


def get_tenant(tenant_id: int) -> dict:
    _require_db()
    from app.models import Tenant
    with session() as db:
        t = db.get(Tenant, tenant_id)
        if not t or t.is_deleted:
            raise not_found("租户不存在")
        return _tenant_row(db, t, tenant_meta(tenant_id))


def create_tenant(body: dict) -> dict:
    _require_db()
    from app.models import Tenant, TenantBrandConfig
    code = str(body.get("tenantCode", "")).strip()
    name = str(body.get("tenantName", "")).strip()
    if not code or not name:
        raise AppException("VALIDATION_ERROR", "tenantCode 与 tenantName 必填")
    with session() as db:
        dup = db.scalars(select(Tenant).where(Tenant.tenant_code == code,
                                              Tenant.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"tenantCode「{code}」已存在")
        tid = int(datetime.now().strftime("%y%m%d%H%M%S")) * 1000 + secrets.randbelow(1000)
        t = Tenant(id=tid, tenant_code=code, school_name=name, status="ACTIVE")
        db.add(t)
        db.add(TenantBrandConfig(tenant_id=tid, platform_name="高校学生全生命周期管理平台",
                                 primary_color="#2563EB", watermark_text=f"{name}内部系统"))
        db.commit()
    pkg = str(body.get("packageCode") or "trial")
    days = get_package(pkg).get("durationDays", 30)
    now = datetime.now()
    put_config_json(tid, "TENANT_META", "-", {
        "status": "trial" if pkg == "trial" else "active", "packageCode": pkg,
        "environment": body.get("environment", "production"),
        "schoolType": body.get("schoolType", "VOCATIONAL"),
        "province": body.get("province", ""), "city": body.get("city", ""),
        "contactName": body.get("contactName", ""), "contactPhone": body.get("contactPhone", ""),
        "contactWechat": body.get("contactWechat", ""),
        "trialStartAt": now.isoformat(timespec="seconds"),
        "trialEndAt": (now + timedelta(days=days)).isoformat(timespec="seconds"),
        "expireAt": (now + timedelta(days=days)).isoformat(timespec="seconds"),
    })
    return get_tenant(tid)


def update_tenant_meta(tenant_id: int, patch: dict) -> dict:
    _require_db()
    meta = tenant_meta(tenant_id)
    meta.update({k: v for k, v in patch.items() if v is not None})
    put_config_json(tenant_id, "TENANT_META", "-", meta)
    return get_tenant(tenant_id)


def tenant_status(tenant_id: int) -> str:
    try:
        meta = tenant_meta(tenant_id)
    except Exception:
        return "active"
    status = meta.get("status", "active")
    expire = meta.get("expireAt")
    if status in ("trial", "active") and expire:
        try:
            if datetime.fromisoformat(expire) < datetime.now():
                return "expired"
        except ValueError:
            pass
    return status


def overview() -> dict:
    _require_db()
    from pathlib import Path
    from app.core.config import settings
    from app.models import (SecurityAuditLog, StudentProfile, Tenant, UnifiedTodo, User,
                            WorkflowTask)
    with session() as db:
        tenants = db.scalars(select(Tenant).where(Tenant.is_deleted.is_(False))).all()
        by = {"trial": 0, "active": 0, "expired": 0, "disabled": 0}
        expiring, abnormal = [], []
        for t in tenants:
            st = tenant_status(t.id)
            by[st] = by.get(st, 0) + 1
            meta = tenant_meta(t.id)
            exp = meta.get("expireAt")
            if exp and st != "disabled":
                try:
                    days = (datetime.fromisoformat(exp) - datetime.now()).days
                    if 0 <= days <= 30:
                        expiring.append({"tenantName": t.school_name, "expireAt": exp, "daysLeft": days})
                except ValueError:
                    pass
            if st in ("expired", "disabled"):
                abnormal.append({"tenantName": t.school_name, "status": st})
        today = datetime.now().strftime("%Y-%m-%d")

        def _count(action):
            return db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
                SecurityAuditLog.action == action,
                func.date(SecurityAuditLog.created_at) == today)) or 0

        week_ago = datetime.now() - timedelta(days=7)
        upload_dir = Path(settings.UPLOAD_DIR or "./uploads")
        used_mb = round(sum(f.stat().st_size for f in upload_dir.rglob("*") if f.is_file()) / 1048576, 2) \
            if upload_dir.exists() else 0
        recent = db.scalars(select(SecurityAuditLog).order_by(SecurityAuditLog.id.desc()).limit(8)).all()
        return {
            "tenantTotal": len(tenants), "tenantTrial": by["trial"], "tenantActive": by["active"],
            "tenantExpired": by["expired"], "tenantDisabled": by["disabled"],
            "studentTotal": db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.is_deleted.is_(False))) or 0,
            "userTotal": db.scalar(select(func.count()).select_from(User).where(
                User.is_deleted.is_(False))) or 0,
            "todayLogin": _count("登录") + _count("LOGIN"),
            "weekLogin": db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
                SecurityAuditLog.action.in_(["登录", "LOGIN"]),
                SecurityAuditLog.created_at >= week_ago)) or 0,
            "todayImport": _count("IMPORT"), "todayExport": _count("EXPORT"),
            "todayUpload": _count("FILE_UPLOAD"),
            "todayApproval": _count("审批通过") + _count("审批驳回"),
            "storageUsedMb": used_mb,
            "expiringTenants": sorted(expiring, key=lambda x: x["daysLeft"])[:5],
            "abnormalTenants": abnormal[:5],
            "recentAudits": [{"action": r.action, "operator": r.operator_name or "-",
                              "at": r.created_at.isoformat(timespec="seconds")} for r in recent],
            "systemHealth": "UP", "dbStatus": "OK",
            "fileDirStatus": "OK" if upload_dir.exists() else "MISSING",
            "todoPending": db.scalar(select(func.count()).select_from(UnifiedTodo).where(
                UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False))) or 0,
            "approvalPending": db.scalar(select(func.count()).select_from(WorkflowTask).where(
                WorkflowTask.status == "PENDING", WorkflowTask.is_deleted.is_(False))) or 0,
        }


# ═══ 账号控制 ═══

def list_users(tenant_id: int) -> list[dict]:
    _require_db()
    from app.models import User
    with session() as db:
        rows = db.scalars(select(User).where(User.tenant_id == tenant_id,
                                             User.is_deleted.is_(False)).order_by(User.id)).all()
        return [{"userId": str(u.id), "loginName": u.login_name, "realName": u.real_name,
                 "userType": u.user_type, "status": u.status,
                 "lastLoginAt": u.last_login_at.isoformat(timespec="seconds") if u.last_login_at else None}
                for u in rows]


def create_school_admin(tenant_id: int, login_name: str, real_name: str) -> dict:
    _require_db()
    from app.models import Role, User, UserRole
    meta = tenant_meta(tenant_id)
    max_users = meta.get("maxUsers") or get_package(meta.get("packageCode", "professional"))["maxUsers"]
    with session() as db:
        count = db.scalar(select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id, User.is_deleted.is_(False))) or 0
        if count >= max_users:
            raise AppException("NO_PERMISSION", f"已达套餐账号上限（{max_users}），无法新建")
        # 唯一键不包含 is_deleted；历史软删账号也必须提前报业务冲突，避免落到 DB 500。
        dup = db.scalars(select(User).where(User.tenant_id == tenant_id,
                                            User.login_name == login_name)).first()
        if dup:
            raise AppException("DATA_CONFLICT", "登录名已存在")
        pwd = "Tmp@" + secrets.token_urlsafe(8)
        u = User(tenant_id=tenant_id, login_name=login_name, real_name=real_name,
                 password_hash=hash_password(pwd), user_type="SCHOOL_ADMIN", status="ACTIVE",
                 must_change_password=True)
        db.add(u)
        db.flush()
        role = db.scalars(select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code == "SCHOOL_ADMIN")).first()
        if role is None:
            role = Role(tenant_id=tenant_id, role_code="SCHOOL_ADMIN", role_name="学校管理员",
                        role_type="SYSTEM", status="ACTIVE",
                        remark="租户开通时自动初始化；权限由平台内置模板约束")
            db.add(role)
            db.flush()
        elif role.is_deleted:
            role.is_deleted = False
            role.status = "ACTIVE"
            role.version = int(role.version or 0) + 1
        elif role.status not in ("ACTIVE", "ENABLED"):
            raise AppException("DATA_CONFLICT", "学校管理员内置角色已停用，请先恢复角色模板")
        db.add(UserRole(tenant_id=tenant_id, user_id=u.id, role_id=role.id, status="ACTIVE"))
        db.commit()
        db.refresh(u)
        # 初始密码只随本响应返回一次，不落任何日志
        return {"userId": str(u.id), "loginName": login_name, "initialPassword": pwd,
                "notice": "初始密码仅本次显示，请立即转交并要求首次登录修改"}


def set_user_status(user_id: int, status: str) -> dict:
    _require_db()
    from app.models import User
    with session() as db:
        u = db.get(User, user_id)
        if not u or u.is_deleted:
            raise not_found("账号不存在")
        u.status = status
        u.version += 1
        db.commit()
        if status != "ACTIVE":
            from app.core.token_store import revoke_refresh_by_user
            revoke_refresh_by_user(f"db-{u.id}")
        return {"userId": str(u.id), "status": u.status}


def reset_user_password(user_id: int) -> dict:
    _require_db()
    from app.models import User
    with session() as db:
        u = db.get(User, user_id)
        if not u or u.is_deleted:
            raise not_found("账号不存在")
        pwd = "Rst@" + secrets.token_urlsafe(8)
        u.password_hash = hash_password(pwd)
        u.must_change_password = True
        u.version += 1
        db.commit()
        from app.core.token_store import revoke_refresh_by_user
        revoke_refresh_by_user(f"db-{u.id}")
        return {"userId": str(u.id), "newPassword": pwd,
                "notice": "新密码仅本次显示，不写入日志"}


def reset_demo_data() -> dict:
    """仅重置 demo-school 演示学生（5 名基线），不触碰其它租户。"""
    _require_db()
    from app.models import StudentContact, StudentProfile
    with session() as db:
        olds = db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == DEMO_TID)).all()
        for s in olds:
            db.delete(s)
        for c in db.scalars(select(StudentContact).where(StudentContact.tenant_id == DEMO_TID)).all():
            db.delete(c)
        for i in range(5):
            s = StudentProfile(tenant_id=DEMO_TID, student_no=f"2026D{i+1:04d}",
                               real_name=f"演示学生{i+1}", gender="男" if i % 2 == 0 else "女",
                               grade="2026", current_stage="ON_CAMPUS", student_status="NORMAL",
                               status="ACTIVE")
            db.add(s)
            db.flush()
            db.add(StudentContact(tenant_id=DEMO_TID, student_id=s.id, contact_type="PHONE",
                                  contact_value_encrypted=f"1390000{i:04d}", is_primary=True,
                                  verified_status="VERIFIED"))
        db.commit()
    return {"tenantId": str(DEMO_TID), "students": 5, "reset": True}


def feature_enabled(tenant_id: int, key: str) -> bool:
    """业务端功能开关检查：配置缺失/异常时默认放行（不因总控故障阻断业务）。"""
    try:
        return bool(effective_features(tenant_id).get(key, True))
    except Exception:
        return True


def safe_rule(tenant_id: int, group: str, key: str):
    try:
        return rule(tenant_id, group, key)
    except Exception:
        return D.DEFAULT_RULES.get(group, {}).get(key)


# ═══ 订单 ═══

def list_orders(tenant_id: int | None = None, status: str | None = None) -> list[dict]:
    _require_db()
    from app.models import PlatformOrder, Tenant
    with session() as db:
        q = select(PlatformOrder).where(PlatformOrder.is_deleted.is_(False))
        if tenant_id:
            q = q.where(PlatformOrder.tenant_id == tenant_id)
        if status:
            q = q.where(PlatformOrder.status == status)
        rows = db.scalars(q.order_by(PlatformOrder.id.desc())).all()
        names = {t.id: t.school_name for t in db.scalars(select(Tenant)).all()}
        return [{
            "orderId": str(r.id), "orderNo": r.order_no, "tenantId": str(r.tenant_id),
            "tenantName": names.get(r.tenant_id, "-"), "orderType": r.order_type,
            "packageCode": r.package_code, "amount": float(r.amount or 0),
            "paidAmount": float(r.paid_amount or 0), "status": r.status,
            "startAt": r.start_at.isoformat(timespec="seconds") if r.start_at else None,
            "endAt": r.end_at.isoformat(timespec="seconds") if r.end_at else None,
            "remark": r.remark or "",
            "createdAt": r.created_at.isoformat(timespec="seconds") if r.created_at else None,
        } for r in rows]


def create_order(body: dict) -> dict:
    _require_db()
    from app.models import PlatformOrder
    tid = int(body.get("tenantId") or 0)
    get_tenant(tid)  # 校验租户存在
    pkg = get_package(str(body.get("packageCode") or "basic"))
    days = int(body.get("durationDays") or pkg["durationDays"])
    now = datetime.now()
    with session() as db:
        o = PlatformOrder(
            tenant_id=tid, order_no=f"PO{now:%Y%m%d%H%M%S}{secrets.randbelow(900) + 100}",
            order_type=str(body.get("orderType") or "NEW"), package_code=pkg["packageCode"],
            amount=body.get("amount", pkg["price"]), paid_amount=0, status="unpaid",
            start_at=now, end_at=now + timedelta(days=days), remark=str(body.get("remark") or ""))
        db.add(o)
        db.commit()
        db.refresh(o)
        return {"orderId": str(o.id), "orderNo": o.order_no, "status": o.status}


def order_action(order_no: str, action: str) -> dict:
    """mark-paid：标记支付并自动开通/续期（试用转正式）；cancel：取消未支付订单。"""
    _require_db()
    from app.models import PlatformOrder
    with session() as db:
        o = db.scalars(select(PlatformOrder).where(PlatformOrder.order_no == order_no,
                                                   PlatformOrder.is_deleted.is_(False))).first()
        if not o:
            raise not_found("订单不存在")
        if action == "mark-paid":
            if o.status != "unpaid":
                raise AppException("DATA_CONFLICT", f"订单状态为 {o.status}，不能标记支付")
            o.status = "paid"
            o.paid_amount = o.amount
            o.version += 1
            db.commit()
            end_at = o.end_at.isoformat(timespec="seconds") if o.end_at else None
            update_tenant_meta(o.tenant_id, {"status": "active", "packageCode": o.package_code,
                                             "expireAt": end_at})
            return {"orderNo": o.order_no, "status": "paid", "tenantActivated": True,
                    "expireAt": end_at}
        if action == "cancel":
            if o.status != "unpaid":
                raise AppException("DATA_CONFLICT", "仅未支付订单可取消")
            o.status = "cancelled"
            o.version += 1
            db.commit()
            return {"orderNo": o.order_no, "status": "cancelled"}
        raise AppException("VALIDATION_ERROR", f"不支持的订单操作：{action}")


# ═══ 公告 ═══

def list_notices(status: str | None = None) -> list[dict]:
    _require_db()
    from app.models import PlatformNotice
    with session() as db:
        q = select(PlatformNotice).where(PlatformNotice.is_deleted.is_(False))
        if status:
            q = q.where(PlatformNotice.status == status)
        return [_notice_row(r) for r in db.scalars(q.order_by(PlatformNotice.id.desc())).all()]


def _notice_row(r) -> dict:
    return {"noticeId": str(r.id), "tenantId": str(r.tenant_id), "noticeType": r.notice_type,
            "title": r.title, "content": r.content or "", "status": r.status,
            "publishAt": r.publish_at.isoformat(timespec="seconds") if r.publish_at else None,
            "createdAt": r.created_at.isoformat(timespec="seconds") if r.created_at else None}


def create_notice(body: dict) -> dict:
    _require_db()
    from app.models import PlatformNotice
    title = str(body.get("title") or "").strip()
    if not title:
        raise AppException("VALIDATION_ERROR", "公告标题必填")
    with session() as db:
        n = PlatformNotice(tenant_id=int(body.get("tenantId") or 0),
                           notice_type=str(body.get("noticeType") or "ANNOUNCEMENT"),
                           title=title, content=str(body.get("content") or ""), status="DRAFT")
        db.add(n)
        db.commit()
        db.refresh(n)
        return _notice_row(n)


def notice_action(notice_id: int, action: str) -> dict:
    _require_db()
    from app.models import PlatformNotice
    with session() as db:
        n = db.get(PlatformNotice, notice_id)
        if not n or n.is_deleted:
            raise not_found("公告不存在")
        if action == "publish":
            n.status = "PUBLISHED"
            n.publish_at = datetime.now()
        elif action == "offline":
            n.status = "OFFLINE"
        else:
            raise AppException("VALIDATION_ERROR", f"不支持的公告操作：{action}")
        n.version += 1
        db.commit()
        return _notice_row(n)


def active_notices_for(tenant_id: int) -> list[dict]:
    """租户端可见的已发布公告（全平台 tenant_id=0 + 本租户）——任意登录角色可读。"""
    if not db_enabled():
        return []
    from app.models import PlatformNotice
    try:
        with session() as db:
            rows = db.scalars(select(PlatformNotice).where(
                PlatformNotice.status == "PUBLISHED", PlatformNotice.is_deleted.is_(False),
                PlatformNotice.tenant_id.in_([0, tenant_id])
            ).order_by(PlatformNotice.publish_at.desc()).limit(10)).all()
            return [_notice_row(r) for r in rows]
    except Exception:
        return []


# ═══ 平台系统参数 ═══

DEFAULT_SETTINGS = {
    "platformName": "高校学生全生命周期管理平台",
    "trialContactPhone": "13549666867",
    "trialDefaultDays": 30,
    "expireRemindDays": 30,
    "demoTenantCode": "demo-school",
    "allowSelfRegister": False,
}


def get_settings_config() -> dict:
    return {**DEFAULT_SETTINGS, **(get_config_json(0, "SETTINGS") or {})}


def put_settings_config(patch: dict) -> dict:
    merged = {**get_settings_config(), **{k: v for k, v in patch.items() if k in DEFAULT_SETTINGS}}
    if str(merged.get("trialContactPhone") or "").strip() == "":
        raise AppException("VALIDATION_ERROR", "试用咨询电话不允许为空")
    put_config_json(0, "SETTINGS", "-", merged)
    return merged


def platform_audit_query(page: int, page_size: int, tenant_id: int | None = None,
                         action: str | None = None, operator: str | None = None,
                         date_from: str | None = None, date_to: str | None = None):
    """§十四 跨租户审计查询（仅平台超管入口使用；普通端仍走 db_service.audit_query 本租户）。"""
    _require_db()
    from app.models import SecurityAuditLog, Tenant
    with session() as db:
        q = select(SecurityAuditLog)
        if tenant_id:
            q = q.where(SecurityAuditLog.tenant_id == tenant_id)
        if action:
            q = q.where(SecurityAuditLog.action == action)
        if operator:
            q = q.where(SecurityAuditLog.operator_name.like(f"%{operator}%"))
        if date_from:
            q = q.where(func.date(SecurityAuditLog.created_at) >= date_from)
        if date_to:
            q = q.where(func.date(SecurityAuditLog.created_at) <= date_to)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(SecurityAuditLog.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        names = {t.id: t.school_name for t in db.scalars(select(Tenant)).all()}
        items = [{
            "auditId": str(r.id), "tenantId": str(r.tenant_id),
            "tenantName": names.get(r.tenant_id, str(r.tenant_id)),
            "action": r.action, "resource": r.resource, "result": r.result,
            "operatorName": r.operator_name, "currentRole": r.current_role,
            "ip": r.ip, "requestMethod": r.request_method, "requestPath": r.request_path,
            "occurredAt": r.created_at.isoformat(timespec="seconds") if r.created_at else None,
        } for r in rows]
        return items, total
