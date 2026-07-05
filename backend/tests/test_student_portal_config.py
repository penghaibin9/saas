"""P1 学生 PC 门户 · 租户配置：读取(仅学生本租户) + 管理端读写(平台/校管理员) + 权限/校验/审计/合并。

依赖 conftest：client / auth_headers(school_admin01·SCHOOL_ADMIN·主租户) / db_mode(临时库+种子, 主租户)。
mock 角色：student01=STUDENT，teacher01=GD_MENTOR，school_admin01=SCHOOL_ADMIN，platform_admin01=PLATFORM_OP。
"""
from __future__ import annotations

MAIN_TID = 1000000000000000001    # db_mode 与 mock-login 默认租户
OTHER_TID = 1000000000000000009   # 另一个租户（校管理员无权、平台管理员有权）

ADMIN_URL = "/api/v1/admin/tenants/{tid}/student-portal-config"
ME_URL = "/api/v1/mobile/me/portal-config"


def _headers(client, login_name: str) -> dict:
    data = client.post("/api/v1/auth/mock-login", json={"loginName": login_name}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _denied(resp) -> bool:
    return resp.status_code == 403 or resp.json().get("code") not in (0, None)


# ── 1/2/3 读取权限 ──

def test_student_reads_own_portal_config(client, db_mode):
    h = _headers(client, "student01")
    r = client.get(ME_URL, headers=h)
    assert r.status_code == 200
    d = r.json()["data"]
    for k in ("enabled", "portalName", "brand", "modules", "features", "package", "loginAccountTips"):
        assert k in d
    assert set(d["modules"]) >= {"dashboard", "academic", "internship", "graduation", "employment"}


def test_non_student_portal_config_forbidden(client, db_mode):
    assert _denied(client.get(ME_URL, headers=_headers(client, "teacher01")))


def test_portal_config_requires_login(client, db_mode):
    assert client.get(ME_URL).status_code == 401


# ── 15 配置缺失不 500（安全默认）──

def test_missing_config_safe_defaults_no_500(client, db_mode):
    r = client.get(ME_URL, headers=_headers(client, "student01"))
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["enabled"] is True                 # 未配置默认可用
    assert all(d["modules"].values())           # 模块默认全开
    assert d["features"]["upload"] is True       # 标准套餐允许 upload
    assert d["features"]["aiAssistant"] is False # AI 默认关（标准套餐不含）


# ── 11/12/4 enabled 总开关 ──

def test_enabled_false_reflected_to_student(client, db_mode):
    padmin = _headers(client, "platform_admin01")
    put = client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
                     json={"enabled": False, "requiredPackage": "standard"})
    assert put.json()["code"] == 0
    got = client.get(ME_URL, headers=_headers(client, "student01")).json()["data"]
    assert got["enabled"] is False


# ── 5 模块开关 ──

def test_module_toggle(client, db_mode):
    padmin = _headers(client, "platform_admin01")
    client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
               json={"enabled": True, "requiredPackage": "standard",
                     "modules": {"graduation": False, "employment": False}})
    m = client.get(ME_URL, headers=_headers(client, "student01")).json()["data"]["modules"]
    assert m["graduation"] is False and m["employment"] is False
    assert m["academic"] is True and m["internship"] is True


# ── 6 功能开关 + 套餐上限 ──

def test_feature_toggle(client, db_mode):
    padmin = _headers(client, "platform_admin01")
    client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
               json={"enabled": True, "requiredPackage": "professional",
                     "features": {"upload": False, "aiAssistant": True}})
    f = client.get(ME_URL, headers=_headers(client, "student01")).json()["data"]["features"]
    assert f["upload"] is False
    assert f["aiAssistant"] is True   # 专业版允许 AI


def test_package_caps_override_tenant_choice(client, db_mode):
    # 试用版不含 export：即使租户勾选 export=true，最终也应为 false
    padmin = _headers(client, "platform_admin01")
    client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
               json={"enabled": True, "requiredPackage": "trial",
                     "features": {"export": True, "aiAssistant": True}})
    d = client.get(ME_URL, headers=_headers(client, "student01")).json()["data"]
    assert d["features"]["export"] is False       # 套餐上限压过租户勾选
    assert d["features"]["aiAssistant"] is False
    assert d["features"]["upload"] is True         # trial 允许 upload
    assert d["package"]["code"] == "trial"


# ── 7/8/9/10/11 管理端写权限 ──

def test_platform_admin_can_update_any_tenant(client, db_mode):
    padmin = _headers(client, "platform_admin01")
    assert client.put(ADMIN_URL.format(tid=OTHER_TID), headers=padmin,
                      json={"enabled": True, "requiredPackage": "standard"}).json()["code"] == 0


def test_school_admin_only_own_tenant(client, db_mode):
    sadmin = _headers(client, "school_admin01")
    assert client.put(ADMIN_URL.format(tid=MAIN_TID), headers=sadmin,
                      json={"enabled": True, "requiredPackage": "standard"}).json()["code"] == 0
    assert _denied(client.put(ADMIN_URL.format(tid=OTHER_TID), headers=sadmin,
                              json={"enabled": True, "requiredPackage": "standard"}))


def test_teacher_cannot_update(client, db_mode):
    assert _denied(client.put(ADMIN_URL.format(tid=MAIN_TID), headers=_headers(client, "teacher01"),
                              json={"enabled": True}))


def test_student_cannot_update(client, db_mode):
    assert _denied(client.put(ADMIN_URL.format(tid=MAIN_TID), headers=_headers(client, "student01"),
                              json={"enabled": True}))


# ── 12 审计 ──

def test_update_writes_audit(client, db_mode):
    from app.services import audit_log
    client.put(ADMIN_URL.format(tid=MAIN_TID), headers=_headers(client, "platform_admin01"),
               json={"enabled": True, "requiredPackage": "standard"})
    items, total = audit_log.query(action="TENANT_STUDENT_PORTAL_CONFIG")
    assert total >= 1
    assert items[0]["detail"].get("action") == "UPDATE"


# ── 13 portalUrl 校验 ──

def test_portal_url_validation(client, db_mode):
    padmin = _headers(client, "platform_admin01")
    ok = client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
                    json={"enabled": True, "requiredPackage": "standard", "portalUrl": "/portal/"})
    assert ok.json()["code"] == 0
    bad = client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
                     json={"enabled": True, "requiredPackage": "standard",
                           "portalUrl": "javascript:alert(1)"})
    assert bad.json()["code"] != 0


# ── 14 loginAccountTips 不为正式租户下发 / 不存真实密码字段 ──

def test_login_tips_not_stored_for_non_demo(client, db_mode):
    padmin = _headers(client, "platform_admin01")
    # standard（非 trial）租户：即使传 accounts，也不下发
    client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
               json={"enabled": True, "requiredPackage": "standard",
                     "loginAccountTips": {"enabled": True,
                                          "accounts": [{"loginName": "student", "password": "123456"}]}})
    tips = client.get(ME_URL, headers=_headers(client, "student01")).json()["data"]["loginAccountTips"]
    assert tips["enabled"] is False and tips["accounts"] == []


def test_login_tips_trial_stores_hint_not_password(client, db_mode):
    padmin = _headers(client, "platform_admin01")
    client.put(ADMIN_URL.format(tid=MAIN_TID), headers=padmin,
               json={"enabled": True, "requiredPackage": "trial",
                     "loginAccountTips": {"enabled": True,
                                          "accounts": [{"label": "演示校", "loginName": "student",
                                                        "password": "123456"}]}})
    tips = client.get(ME_URL, headers=_headers(client, "student01")).json()["data"]["loginAccountTips"]
    assert tips["enabled"] is True and len(tips["accounts"]) == 1
    acc = tips["accounts"][0]
    assert "password" not in acc           # 不落 password 字段
    assert acc["loginName"] == "student"
