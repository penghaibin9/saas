"""P6 · 平台总控验收：强校验 403 / 租户运营 / 规则真生效 / 功能开关 / 订单 / 公告 / 安全边界。"""
from __future__ import annotations

import pytest

MAIN_TID = 1000000000000000001


def _ensure_main_tenant():
    """db_mode 夹具只种学生数据，这里补主租户行（平台租户接口需要 t_tenant 存在）。"""
    from app.db.session import get_sessionmaker
    from sqlalchemy import select
    from app.models import PlatformConfig, Tenant
    db = get_sessionmaker()()
    try:
        if not db.get(Tenant, MAIN_TID):
            db.add(Tenant(id=MAIN_TID, tenant_code="demo", school_name="示范职业技术学院",
                          status="ACTIVE"))
            db.flush()
        meta = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == MAIN_TID,
            PlatformConfig.config_type == "TENANT_META",
            PlatformConfig.config_key == "-",
            PlatformConfig.is_deleted.is_(False),
        )).first()
        if meta is None:
            db.add(PlatformConfig(
                tenant_id=MAIN_TID, config_type="TENANT_META", config_key="-",
                config_json={"status": "active", "packageCode": "professional"}, enabled=True,
            ))
        db.commit()
    finally:
        db.close()



def _seed_main_org_class() -> str:
    """为需要验证正式建档的测试种一套完整、自洽的学院/专业/班级。"""
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass

    db = get_sessionmaker()()
    try:
        col = College(tenant_id=MAIN_TID, college_name="平台测试学院", status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=MAIN_TID, college_id=col.id, major_name="平台测试专业", status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=MAIN_TID, major_id=maj.id, class_name="平台测试2601",
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        class_id = str(cls.id)
        db.commit()
        return class_id
    finally:
        db.close()

def _owner_headers() -> dict:
    from app.core.security import create_access_token
    token = create_access_token({
        "userId": "u-platform-owner", "realName": "平台老板", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "1000000000000000000", "tenantName": "平台运营中心",
        "activeContextId": "ctx_platform_owner", "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _tenant_version(client, headers: dict, tenant_id: int | str) -> int:
    detail = client.get(f"/api/v1/platform/tenants/{tenant_id}/360", headers=headers).json()
    assert detail["code"] == 0, detail
    return int(detail["data"]["version"])


def _tenant_action(client, headers: dict, tenant_id: int | str, action: str, **payload):
    reason = payload.pop("reason", f"测试执行{action}操作")
    body = {
        **payload,
        "reason": reason,
        "expectedVersion": _tenant_version(client, headers, tenant_id),
    }
    return client.post(
        f"/api/v1/platform/tenants/{tenant_id}/{action}",
        headers=headers,
        json=body,
    )


# ── §一 强校验：非平台超管一律 403，拒绝写审计 ──

def test_platform_requires_login(client):
    resp = client.get("/api/v1/platform/overview")
    assert resp.json()["code"] == 401001


def test_platform_school_admin_403(client, auth_headers):
    resp = client.get("/api/v1/platform/overview", headers=auth_headers)
    body = resp.json()
    assert resp.status_code == 403 and body["code"] == 403001 and body["bizCode"] == "NO_PERMISSION"


def test_platform_403_paths_all_guarded(client, auth_headers):
    for path in ("/api/v1/platform/tenants", "/api/v1/platform/packages",
                 "/api/v1/platform/security", "/api/v1/platform/audit-logs",
                 "/api/v1/platform/orders", "/api/v1/platform/notices"):
        assert client.get(path, headers=auth_headers).json()["code"] == 403001, path


# ── §二/§三 总览与租户全托管（走真库）──

def test_overview_and_tenant_lifecycle(client, db_mode):
    h = _owner_headers()
    body = client.get("/api/v1/platform/overview", headers=h).json()
    assert body["code"] == 0 and body["data"]["tenantTotal"] >= 0

    created = client.post("/api/v1/platform/tenants", headers=h, json={
        "tenantCode": "t-life", "tenantName": "生命周期测试学院", "packageCode": "trial",
        "province": "广东省", "city": "东莞市", "contactName": "张三", "contactPhone": "13800001111",
    }).json()
    assert created["code"] == 0 and created["data"]["status"] == "trial"
    tid = created["data"]["tenantId"]

    dup = client.post("/api/v1/platform/tenants", headers=h,
                      json={"tenantCode": "t-life", "tenantName": "重复"}).json()
    assert dup["code"] == 409001

    ext = _tenant_action(client, h, tid, "extend-trial", days=30).json()
    assert ext["code"] == 0

    paid = _tenant_action(client, h, tid, "convert-to-paid", packageCode="standard").json()
    assert paid["code"] == 0 and paid["data"]["status"] == "active" \
        and paid["data"]["packageCode"] == "standard"

    quota = _tenant_action(client, h, tid, "quota", maxStudents=500).json()
    assert quota["code"] == 0 and quota["data"]["maxStudents"] == 500

    off = _tenant_action(client, h, tid, "disable").json()
    assert off["code"] == 0 and off["data"]["status"] == "disabled"

    exp = _tenant_action(client, h, tid, "expire").json()
    assert exp["code"] == 0 and exp["data"]["status"] == "expired"


def test_disabled_tenant_login_blocked(client, db_mode):
    h = _owner_headers()

    created = client.post("/api/v1/platform/tenants", headers=h, json={
        "tenantCode": "t-block", "tenantName": "停用登录测试学院"}).json()["data"]
    # 经平台端正规接口建号（User+Role+UserRole 全链路）。此前手工插 User 不建 UserRole，
    # 登录在"停用前"一步就被 fail-closed 拒（LOGIN_NO_ACTIVE_ROLE），测不到停用拦截。
    u = client.post(f"/api/v1/platform/tenants/{created['tenantId']}/users", headers=h,
                    json={"loginName": "blocked_admin", "realName": "被停用管理员"}).json()["data"]
    pwd = u["initialPassword"]

    ok = client.post("/api/v1/auth/login",
                     json={"loginName": "blocked_admin", "password": pwd}).json()
    assert ok["code"] == 0  # 停用前可登录

    _tenant_action(client, h, created["tenantId"], "disable")
    blocked = client.post("/api/v1/auth/login",
                          json={"loginName": "blocked_admin", "password": pwd}).json()
    assert blocked["code"] == 403001 and blocked["bizCode"] == "NO_PERMISSION"


def test_expired_tenant_readonly(client, auth_headers, db_mode):
    _ensure_main_tenant()
    h = _owner_headers()
    _tenant_action(client, h, MAIN_TID, "expire")

    read = client.get("/api/v1/students", headers=auth_headers).json()
    assert read["code"] == 0  # 到期后仍可查看

    write = client.post("/api/v1/students", headers=auth_headers,
                        json={"studentNo": "RO2026001", "realName": "只读测试"}).json()
    assert write["code"] == 403001 and write["bizCode"] == "MODULE_EXPIRED_READONLY"

    _tenant_action(client, h, MAIN_TID, "convert-to-paid", packageCode="professional")
    class_id = _seed_main_org_class()
    write2 = client.post("/api/v1/students", headers=auth_headers,
                         json={"studentNo": "RO2026001", "realName": "只读测试",
                               "classId": class_id}).json()
    assert write2["code"] == 0


# ── §五 功能开关真生效 ──

def _student_xlsx(no="FT2026001", name="开关测试"):
    """构造一份最小学生导入 xlsx（表头须与 build_student_template 一致）。"""
    import io as _io

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "导入模板"
    ws.append(["学号 *", "姓名 *", "所属学院", "所属专业", "班级名称 *", "年级", "性别", "身份证号"])
    ws.append([no, name, "", "", "软件2301班", "", "", ""])
    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_feature_toggle_blocks_import(client, auth_headers, db_mode):
    """studentImport 特性闸门：旧 /import/students/* 已删除，闸门随入口收敛迁到
    「系统管理 › 学生导入与账号开通」，此处验证它在新入口仍真实生效。"""
    _ensure_main_tenant()
    h = _owner_headers()
    files = {"file": ("students.xlsx", _student_xlsx(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

    put = client.put(f"/api/v1/platform/tenants/{MAIN_TID}/features", headers=h,
                     json={"studentImport": False}).json()
    assert put["code"] == 0 and put["data"]["features"]["studentImport"] is False

    denied = client.post("/api/v1/system/identity-import/students/validate-file",
                         headers=auth_headers, files=files).json()
    assert denied["code"] == 403001 and denied["bizCode"] == "MODULE_NOT_AUTHORIZED"

    client.put(f"/api/v1/platform/tenants/{MAIN_TID}/features", headers=h,
               json={"studentImport": True})
    files = {"file": ("students.xlsx", _student_xlsx(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    ok = client.post("/api/v1/system/identity-import/students/validate-file",
                     headers=auth_headers, files=files).json()
    # 闸门放开后不应再是 MODULE_NOT_AUTHORIZED（班级不存在等业务错误由预检回执承载）
    assert ok.get("bizCode") != "MODULE_NOT_AUTHORIZED"


# ── §六 规则中心真生效 ──

def test_rules_reject_reason_min_length(client, auth_headers, db_mode):
    _ensure_main_tenant()
    h = _owner_headers()
    tid_task = db_mode["task"]
    put = client.put(f"/api/v1/platform/tenants/{MAIN_TID}/rules", headers=h,
                     json={"approval": {"rejectReasonMinLength": 10}}).json()
    assert put["code"] == 0 and put["data"]["rules"]["approval"]["rejectReasonMinLength"] == 10

    task = client.get(f"/api/v1/approvals/tasks/{tid_task}", headers=auth_headers).json()
    assert task["code"] == 0
    version = int(task["data"]["version"])
    short = client.post(f"/api/v1/approvals/tasks/{tid_task}/reject", headers=auth_headers,
                        json={"reason": "材料不符", "version": version}).json()
    assert short["code"] == 400001 and "10" in short["message"]

    ok = client.post(f"/api/v1/approvals/tasks/{tid_task}/reject", headers=auth_headers,
                     json={"reason": "材料不清晰且缺少盖章页请重新上传",
                           "version": version}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "REJECTED"


def test_rules_export_purpose_min_length(client, auth_headers, db_mode):
    _ensure_main_tenant()
    h = _owner_headers()
    client.put(f"/api/v1/platform/tenants/{MAIN_TID}/rules", headers=h,
               json={"export": {"exportPurposeMinLength": 12}})
    short = client.post("/api/v1/export/students", headers=auth_headers,
                        json={"purpose": "迎新名册用途"}).json()
    assert short["code"] == 422001 and "12" in short["message"]


def test_rules_validation_rejects_unknown(client, db_mode):
    _ensure_main_tenant()
    h = _owner_headers()
    bad = client.put(f"/api/v1/platform/tenants/{MAIN_TID}/rules", headers=h,
                     json={"approval": {"noSuchRule": 1}}).json()
    assert bad["code"] == 422001


# ── §四 套餐 / §十三 安全边界 ──

def test_packages_default_five(client, db_mode):
    h = _owner_headers()
    body = client.get("/api/v1/platform/packages", headers=h).json()
    codes = {p["packageCode"] for p in body["data"]["list"]}
    assert codes == {"trial", "basic", "standard", "professional", "private"}

    current = next(item for item in body["data"]["list"] if item["packageCode"] == "trial")
    put = client.put("/api/v1/platform/packages/trial", headers=h,
                     json={"durationDays": 45, "expectedVersion": current["version"],
                           "reason": "测试更新试用套餐期限"}).json()
    assert put["code"] == 0 and put["data"]["durationDays"] == 45


def test_security_bounds_reject_unsafe(client, db_mode):
    h = _owner_headers()
    bad = client.put("/api/v1/platform/security", headers=h,
                     json={"loginFailMaxTimes": 999}).json()
    assert bad["code"] == 422001

    ok = client.put("/api/v1/platform/security", headers=h,
                    json={"loginFailMaxTimes": 6}).json()
    assert ok["code"] == 0 and ok["data"]["security"]["loginFailMaxTimes"] == 6


# ── §十一 订单：标记支付自动开通 ──

def test_order_mark_paid_activates_tenant(client, db_mode):
    h = _owner_headers()
    t = client.post("/api/v1/platform/tenants", headers=h, json={
        "tenantCode": "t-order", "tenantName": "订单测试学院", "packageCode": "trial"}).json()["data"]
    o = client.post("/api/v1/platform/orders", headers=h, json={
        "tenantId": t["tenantId"], "packageCode": "standard", "amount": 49800}).json()["data"]
    paid = client.post(
        f"/api/v1/platform/orders/{o['orderNo']}/mark-paid", headers=h,
        json={"expectedVersion": o["version"], "reason": "测试确认订单已完成支付"},
    ).json()
    assert paid["code"] == 0 and paid["data"]["tenantActivated"] is True

    got = client.get(f"/api/v1/platform/tenants/{t['tenantId']}", headers=h).json()["data"]
    assert got["status"] == "active" and got["packageCode"] == "standard"


# ── §十二 公告 ──

def test_notice_publish_flow(client, db_mode):
    h = _owner_headers()
    n = client.post("/api/v1/platform/notices", headers=h, json={
        "title": "测试公告", "content": "内容", "noticeType": "ANNOUNCEMENT"}).json()["data"]
    assert n["status"] == "DRAFT"
    pub = client.post(f"/api/v1/platform/notices/{n['noticeId']}/publish", headers=h).json()
    assert pub["code"] == 0 and pub["data"]["status"] == "PUBLISHED"

    from app.services.platform_service import active_notices_for
    assert any(x["noticeId"] == n["noticeId"] for x in active_notices_for(MAIN_TID))

    off = client.post(f"/api/v1/platform/notices/{n['noticeId']}/offline", headers=h).json()
    assert off["data"]["status"] == "OFFLINE"


# ── §十 账号控制：初始密码只出现一次 ──

def test_platform_create_school_admin(client, db_mode):
    h = _owner_headers()
    t = client.post("/api/v1/platform/tenants", headers=h, json={
        "tenantCode": "t-user", "tenantName": "账号测试学院"}).json()["data"]
    u = client.post(f"/api/v1/platform/tenants/{t['tenantId']}/users", headers=h,
                    json={"loginName": "new_admin01", "realName": "新管理员"}).json()
    assert u["code"] == 0 and u["data"]["initialPassword"]

    login = client.post("/api/v1/auth/login", json={
        "loginName": "new_admin01", "password": u["data"]["initialPassword"]}).json()
    assert login["code"] == 0

    reset = client.post(f"/api/v1/platform/users/{u['data']['userId']}/reset-password",
                        headers=h).json()
    assert reset["code"] == 0 and reset["data"]["newPassword"] != u["data"]["initialPassword"]


# ── §十四 拒绝审计落库 ──

def test_permission_denied_written_to_audit(client, auth_headers, db_mode):
    _ensure_main_tenant()
    client.get("/api/v1/platform/overview", headers=auth_headers)  # 403 → 审计
    h = _owner_headers()
    logs = client.get("/api/v1/platform/audit-logs",
                      params={"action": "PERMISSION_DENIED"}, headers=h).json()
    assert logs["code"] == 0 and logs["data"]["total"] >= 1
