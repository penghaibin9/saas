"""P6 · 平台总控种子（driver 无关，幂等：平台租户已存在则跳过）。
含：平台运营租户 + 平台超管账号、trial/expired/disabled 三个演示租户、
主/演示租户 TENANT_META、订单、公告。密码只存 pbkdf2 哈希，绝不落明文
（platform_owner / 各校 admin 的初始密码由平台方线下移交，模式同 demo 账号）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (PlatformConfig, PlatformNotice, PlatformOrder, StudentContact,
                        StudentProfile, Tenant, TenantBrandConfig, User)

TID0 = 1000000000000000000   # 平台运营中心（platform_owner 所属）
TID = 1000000000000000001    # 主租户 demo（示范职业技术学院）
TID2 = 1000000000000000003   # 演示租户 demo-school
TID4 = 1000000000000000004   # trial-school 试用中
TID5 = 1000000000000000005   # expired-school 已到期（只读演示）
TID6 = 1000000000000000006   # disabled-school 已停用（禁止登录演示）

# 密码均为 pbkdf2_sha256 哈希（明文不入库不入仓，线下移交）
OWNER_HASH = "pbkdf2_sha256$200000$f0caa0839bdbd5d93f5e258d3ac6db10$bce303f8f08d4f95b236085b2103a144a84028ee2d601c18e0fc334f1fe1391a"
TRIAL_HASH = "pbkdf2_sha256$200000$bd9c3f1aca794d8c41b5687a62e639ca$cba48ae86b8a726ecff344c57c49cfb604e65d2516da80889edebd01d0a7e72b"
EXPIRED_HASH = "pbkdf2_sha256$200000$fdad080bb6e564afc915868d785f4757$db4ae32aeb1cc1e71dbb5b1b2b3877804113e3e0f09cd3d8cef18023dcac083c"
DISABLED_HASH = "pbkdf2_sha256$200000$f9f1838fcc75e92a5a4ee9df1af57267$2d4e97685be28dd2cdac01e7bce820b45b484fd62469f4968aba33ac26d6ed42"

NEW_TENANTS = [
    # (tid, code, name, short, admin_login, admin_name, admin_hash, meta_status, package, expire_delta_days)
    (TID4, "trial-school", "试点职业技术学院", "试点职院",
     "admin_trial", "试点管理员", TRIAL_HASH, "trial", "trial", 7),
    (TID5, "expired-school", "到期职业技术学院", "到期职院",
     "admin_expired", "到期管理员", EXPIRED_HASH, "expired", "basic", -3),
    (TID6, "disabled-school", "停用职业技术学院", "停用职院",
     "admin_disabled", "停用管理员", DISABLED_HASH, "disabled", "basic", 180),
]


def _put_cfg(db, tenant_id: int, ctype: str, key: str, payload: dict) -> None:
    row = db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == tenant_id, PlatformConfig.config_type == ctype,
        PlatformConfig.config_key == key, PlatformConfig.is_deleted.is_(False))).first()
    if row:
        row.config_json = payload
    else:
        db.add(PlatformConfig(tenant_id=tenant_id, config_type=ctype, config_key=key,
                              config_json=payload, enabled=True))


def seed_platform(db) -> dict:
    """在既有会话上追加平台总控种子；不触碰 demo=5 / main=100 的既有学生数据。"""
    now = datetime.now()
    if db.get(Tenant, TID0):
        return {"skipped": True}

    # ── 平台运营中心 + 平台超管 ──
    db.add(Tenant(id=TID0, tenant_code="platform", school_name="平台运营中心",
                  short_name="平台", status="ACTIVE"))
    db.add(User(tenant_id=TID0, login_name="platform_owner", real_name="平台老板",
                password_hash=OWNER_HASH, user_type="PLATFORM_SUPER_ADMIN", status="ACTIVE"))

    # ── 主/演示租户运营元数据（保持 active，远期到期，不影响既有链路）──
    _put_cfg(db, TID, "TENANT_META", "-", {
        "status": "active", "packageCode": "professional", "environment": "production",
        "schoolType": "VOCATIONAL", "province": "广东省", "city": "广州市",
        "contactName": "陈校办", "contactPhone": "13549666867",
        "expireAt": (now + timedelta(days=365)).isoformat(timespec="seconds")})
    _put_cfg(db, TID2, "TENANT_META", "-", {
        "status": "active", "packageCode": "standard", "environment": "demo",
        "schoolType": "VOCATIONAL", "province": "广东省", "city": "深圳市",
        "contactName": "平台演示", "contactPhone": "13549666867",
        "expireAt": (now + timedelta(days=365)).isoformat(timespec="seconds")})

    # ── 三个运营状态演示租户 ──
    for tid, code, name, short, login, uname, phash, status, pkg, delta in NEW_TENANTS:
        db.add(Tenant(id=tid, tenant_code=code, school_name=name, short_name=short, status="ACTIVE"))
        db.add(TenantBrandConfig(tenant_id=tid, platform_name="高校学生全生命周期管理平台",
                                 primary_color="#2563EB", watermark_text=f"{short}内部系统"))
        db.add(User(tenant_id=tid, login_name=login, real_name=uname,
                    password_hash=phash, user_type="SCHOOL_ADMIN", status="ACTIVE"))
        expire = (now + timedelta(days=delta)).isoformat(timespec="seconds")
        meta = {"status": status, "packageCode": pkg, "environment": "production",
                "schoolType": "VOCATIONAL", "province": "广东省", "city": "佛山市",
                "contactName": uname, "contactPhone": "13800000000", "expireAt": expire}
        if status == "trial":
            meta["trialStartAt"] = (now - timedelta(days=23)).isoformat(timespec="seconds")
            meta["trialEndAt"] = expire
        _put_cfg(db, tid, "TENANT_META", "-", meta)
        for i in range(2):
            s = StudentProfile(tenant_id=tid, student_no=f"{code[:1].upper()}2026{i+1:03d}",
                               real_name=f"{short}学生{i+1}", gender="男" if i == 0 else "女",
                               grade="2026", current_stage="ON_CAMPUS",
                               student_status="NORMAL", status="ACTIVE")
            db.add(s)
            db.flush()
            db.add(StudentContact(tenant_id=tid, student_id=s.id, contact_type="PHONE",
                                  contact_value_encrypted=f"137{tid % 10}000{i:04d}",
                                  is_primary=True, verified_status="VERIFIED"))

    # ── 订单：主租户已支付年费 + 试用租户待支付升级单 ──
    db.add(PlatformOrder(tenant_id=TID, order_no="PO20260101000001", order_type="RENEW",
                         package_code="professional", amount=99800, paid_amount=99800,
                         status="paid", start_at=now - timedelta(days=180),
                         end_at=now + timedelta(days=365), remark="种子：主租户年费（已支付）"))
    db.add(PlatformOrder(tenant_id=TID4, order_no="PO20260701000002", order_type="NEW",
                         package_code="standard", amount=49800, paid_amount=0,
                         status="unpaid", start_at=now, end_at=now + timedelta(days=365),
                         remark="种子：试点职院标准版意向单（未支付）"))

    # ── 公告：1 条已发布（全平台）+ 1 条草稿 ──
    db.add(PlatformNotice(tenant_id=0, notice_type="ANNOUNCEMENT",
                          title="平台 7 月功能更新：平台总控上线",
                          content="平台新增总控中心：租户、套餐、规则、品牌、公告一站式管理。",
                          status="PUBLISHED", publish_at=now - timedelta(days=1)))
    db.add(PlatformNotice(tenant_id=TID4, notice_type="TRIAL_REMIND",
                          title="试用期剩余 7 天提醒（草稿）",
                          content="您的试用将于 7 天后到期，续费请联系平台方 13549666867。",
                          status="DRAFT"))

    db.commit()
    return {"platformTenant": "platform", "owner": "platform_owner",
            "tenants": [t[1] for t in NEW_TENANTS], "orders": 2, "notices": 2}
