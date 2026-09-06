"""SYS-13 模块商业授权、学校启用与准备度（真库）。

对应必测 SYS13-T01～T05：
未授权不能启用 / 学校停用后后端拒绝 / 存储故障不放开 / 并发一个成功一个 409 / 依赖校验生效。

商业授权测试只走真实套餐 + 已支付订单，不再用退休的 FEATURES override 伪造购买状态。
另加四态不合并、启用期限、跨租户隔离、旧 JSON 兼容读与影响预览的回归锁。
"""
from datetime import datetime, timedelta
import hashlib
import json

import pytest

from app.core.exceptions import AppException
from app.services import module_access_service as access
from app.services import platform_defaults as defaults
from app.services import platform_service as platform
from app.services import system_governance_service as gov
from app.services import tenant_capability_setting_service as caps

TENANT = 8601
OTHER_TENANT = 8602
MAIN_TENANT_ID = 1000000000000000001


def _ensure_tenant_row(tenant_id: int) -> None:
    """只建真实租户主表；正式商业状态由下面的已支付订单建立。"""
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, int(tenant_id)) is None:
            db.add(Tenant(id=int(tenant_id), tenant_code=f"cap-test-{tenant_id}",
                          school_name=f"能力测试学校{tenant_id}", status="ACTIVE"))
            db.commit()
    finally:
        db.close()


def _activate_entitlement(tenant_id: int, overrides: dict | None = None) -> str:
    """真实商业事实：测试套餐目录 -> 订单 -> 支付 -> 激活；FEATURES 永不参与。"""
    _ensure_tenant_row(tenant_id)
    patch = {str(k): bool(v) for k, v in (overrides or {}).items() if k in defaults.FEATURE_KEYS}
    features = {**defaults.DEFAULT_FEATURES, **patch}
    digest = hashlib.sha256(json.dumps(features, sort_keys=True).encode()).hexdigest()[:10]
    package_code = f"sys13_{tenant_id}_{digest}"[:50]
    package = {
        "packageCode": package_code,
        "packageName": f"SYS13测试套餐-{digest}",
        "price": 1,
        "durationDays": 30,
        "maxStudents": 10000,
        "maxUsers": 1000,
        "storageLimitMb": 20480,
        "features": features,
        "enabled": True,
        "remark": "SYS-13 paid-order entitlement fixture",
    }
    platform.put_config_json(0, "PACKAGE", package_code, package)
    platform.put_config_json(tenant_id, "TENANT_META", "-", {
        "status": "trial",
        "packageCode": "trial",
        "environment": "test",
        "expireAt": (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds"),
    })
    created = platform.create_order({
        "tenantId": str(tenant_id),
        "packageCode": package_code,
        "orderType": "NEW",
        "durationDays": 30,
        "amount": 1,
        "remark": "SYS-13真实订单授权测试",
    })
    paid = platform.order_action(
        created["orderNo"], "mark-paid",
        expected_version=int(created["version"]),
        reason="SYS13真实订单入账测试",
    )
    if paid.get("repairTaskRequired"):
        paid = platform.order_action(
            created["orderNo"], "repair-activation",
            expected_version=int(paid["version"]),
            reason="SYS13修复订单激活测试",
        )
    assert paid.get("tenantActivated") is True
    return package_code


def _ensure_tenant(tenant_id: int) -> None:
    _activate_entitlement(tenant_id, {})


def _set_features(tenant_id: int, overrides: dict) -> None:
    """兼容旧测试函数名；实际写入的是已支付订单对应的套餐能力快照。"""
    _activate_entitlement(tenant_id, overrides)


def _state(key: str, tenant_id: int = TENANT) -> dict:
    return caps.capability_states(tenant_id)[key]


# ── SYS13-T01：未授权不能启用 ────────────────────────────────────────────────
def test_t01_not_entitled_cannot_be_enabled(db_mode):
    _set_features(TENANT, {"employment": False})
    st = _state("employment")
    assert st["entitled"] is False
    assert st["enabled"] is False
    assert st["allowed"] is False
    assert st["reasonCode"] == caps.REASON_NOT_ENTITLED

    with pytest.raises(AppException) as caught:
        caps.set_capability("employment", enabled=True, reason="学校希望开通就业服务",
                            tenant_id=TENANT)
    assert caught.value.code == "VALIDATION_ERROR"
    assert "未购买" in caught.value.message
    assert _state("employment")["configured"] is False


def test_t01b_entitled_and_enabled_are_separate_fields(db_mode):
    """禁止把 entitled 与 enabled 合成一个字段：平台没卖和学校自己关，必须区分得出来。"""
    _set_features(TENANT, {"internship": False})
    not_entitled = _state("internship")
    assert (not_entitled["entitled"], not_entitled["schoolEnabled"]) == (False, True)
    assert not_entitled["reasonCode"] == caps.REASON_NOT_ENTITLED

    caps.set_capability("campusService", enabled=False, reason="本学期不开放在校服务",
                        tenant_id=TENANT)
    school_off = _state("campusService")
    assert (school_off["entitled"], school_off["schoolEnabled"]) == (True, False)
    assert school_off["reasonCode"] == caps.REASON_SCHOOL_DISABLED


# ── SYS13-T02：学校停用后后端拒绝（不是只藏菜单）──────────────────────────────
def test_t02_school_disabled_denies_backend(db_mode):
    _ensure_tenant(TENANT)
    before = access.module_access_state(TENANT, "internship")
    assert before["enabled"] is True and before["allowed"] is True

    caps.set_capability("internship", enabled=False, reason="实习模块本学期停用",
                        tenant_id=TENANT)

    after = access.module_access_state(TENANT, "internship")
    assert after["entitled"] is True, "学校停用不得篡改平台授权"
    assert after["enabled"] is False
    assert after["allowed"] is False
    assert after["reasonCode"] == caps.REASON_SCHOOL_DISABLED

    with pytest.raises(AppException) as caught:
        access.assert_module_access(TENANT, "internship")
    assert caught.value.http_status == 403


def test_t02b_http_layer_reads_and_writes(client, auth_headers, db_mode):
    listed = client.get("/api/v1/system/capability-settings", headers=auth_headers).json()
    assert listed["code"] == 0
    items = {row["capabilityKey"]: row for row in listed["data"]["list"]}
    assert "internship" in items and "platform" not in items, "平台专属模块不进学校目录"
    for row in items.values():
        assert {"entitled", "enabled", "ready", "allowed", "reasonCode"} <= set(row)

    version = items["campusService"]["version"]
    resp = client.put("/api/v1/system/capability-settings/campusService", headers=auth_headers,
                      json={"enabled": False, "reason": "本学期暂停在校服务",
                            "expectedVersion": version})
    assert resp.status_code == 200 and resp.json()["code"] == 0
    assert resp.json()["data"]["enabled"] is False

    stale = client.put("/api/v1/system/capability-settings/campusService", headers=auth_headers,
                       json={"enabled": True, "reason": "用过期版本重试",
                             "expectedVersion": version})
    assert stale.status_code == 409
    assert stale.json()["bizCode"] == "DATA_CONFLICT"

    impact = client.get("/api/v1/system/capability-settings/campusService/impact",
                        headers=auth_headers).json()
    assert impact["code"] == 0
    assert impact["data"]["menus"] and impact["data"]["apis"]


# ── SYS13-T03：存储故障不放开 ────────────────────────────────────────────────
def test_t03_storage_failure_fails_closed(db_mode, monkeypatch):
    _ensure_tenant(TENANT)

    def _boom(_tenant_id):
        raise RuntimeError("capability storage down")

    monkeypatch.setattr(caps, "_load_rows", _boom)

    with pytest.raises(Exception) as raw:
        caps.capability_states(TENANT)
    assert isinstance(raw.value, RuntimeError)

    monkeypatch.undo()

    from app.db import session as db_session

    def _bad_sessionmaker():
        raise RuntimeError("connection pool exhausted")

    monkeypatch.setattr(db_session, "get_sessionmaker", _bad_sessionmaker)
    with pytest.raises(AppException) as caught:
        caps.capability_states(TENANT)
    assert caught.value.http_status == 503

    with pytest.raises(AppException) as gate:
        access.module_access_state(TENANT, "internship")
    assert gate.value.http_status == 503, "读不到开关时必须拒绝，不能默认放行"


# ── SYS13-T04：并发一个成功一个 409 ─────────────────────────────────────────
def test_t04_concurrent_update_one_conflict(db_mode):
    _ensure_tenant(TENANT)
    version = _state("orientation")["version"]
    caps.set_capability("orientation", enabled=False, reason="迎新阶段结束，先停用",
                        expected_version=version, tenant_id=TENANT)

    with pytest.raises(AppException) as caught:
        caps.set_capability("orientation", enabled=True, reason="另一人拿旧版本改回来",
                            expected_version=version, tenant_id=TENANT)
    assert caught.value.code == "DATA_CONFLICT"
    assert caught.value.http_status == 409
    assert _state("orientation")["enabled"] is False, "冲突方不得写入"

    fresh = _state("orientation")["version"]
    caps.set_capability("orientation", enabled=True, reason="刷新后重新启用迎新",
                        expected_version=fresh, tenant_id=TENANT)
    assert _state("orientation")["enabled"] is True


# ── SYS13-T05：依赖校验生效 ─────────────────────────────────────────────────
def test_t05_dependency_blocks_enable_and_disable(db_mode):
    assert "studentAffairs" in caps.capability_registry()["orientation"]["dependencies"]

    _set_features(TENANT, {"studentAffairs": False})
    st = _state("orientation")
    assert st["schoolEnabled"] is True and st["entitled"] is True
    assert st["dependencyUnmet"] == ["studentAffairs"]
    assert st["ready"] is False and st["allowed"] is False
    assert st["reasonCode"] == caps.REASON_DEPENDENCY_UNMET

    with pytest.raises(AppException) as enable_denied:
        caps.set_capability("orientation", enabled=True, reason="依赖没开也要开迎新",
                            tenant_id=TENANT)
    assert "依赖" in enable_denied.value.message

    _set_features(TENANT, {})
    assert _state("orientation")["allowed"] is True
    caps.set_capability("studentAffairs", enabled=False, reason="学工中心整体停用",
                        tenant_id=TENANT)
    cascaded = _state("orientation")
    assert cascaded["schoolEnabled"] is True, "级联不可用不得偷偷改写学校的开关"
    assert cascaded["allowed"] is False
    assert cascaded["reasonCode"] == caps.REASON_DEPENDENCY_UNMET
    assert access.module_access_state(TENANT, "orientation")["enabled"] is False

    caps.set_capability("studentAffairs", enabled=True, reason="学工中心恢复启用",
                        tenant_id=TENANT)
    assert _state("orientation")["allowed"] is True


# ── 启用期限 ─────────────────────────────────────────────────────────────────
def test_expired_capability_is_not_allowed(db_mode):
    _ensure_tenant(TENANT)
    past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    caps.set_capability("graduationDesign", enabled=True, reason="设置一个已过期的启用期限",
                        tenant_id=TENANT, expires_at=past)
    st = _state("graduationDesign")
    assert st["schoolEnabled"] is True
    assert st["enabled"] is False and st["allowed"] is False
    assert st["reasonCode"] == caps.REASON_EXPIRED

    state = access.module_access_state(TENANT, "graduation")
    assert state["enabled"] is False
    assert state["reasonCode"] == caps.REASON_EXPIRED


# ── 跨租户隔离 ───────────────────────────────────────────────────────────────
def test_tenant_isolation(db_mode):
    _ensure_tenant(TENANT)
    _ensure_tenant(OTHER_TENANT)
    caps.set_capability("employment", enabled=False, reason="A 校停用就业服务",
                        tenant_id=TENANT)
    assert _state("employment", TENANT)["enabled"] is False
    assert _state("employment", OTHER_TENANT)["enabled"] is True
    assert access.module_access_state(OTHER_TENANT, "employment")["enabled"] is True


# ── 旧 JSON 文档兼容读：升级当天不得把学校关掉的模块自动打开 ──────────────────
def test_legacy_json_document_is_read_as_default(db_mode):
    from app.core.context import set_tenant

    _ensure_tenant(TENANT)
    set_tenant({"tenantId": str(TENANT)})
    try:
        gov._save(gov.DOC_MODULE_FEATURES,
                  {"internship": {"enabled": False, "expiresAt": ""}}, None)
        st = _state("internship")
        assert st["configured"] is False, "旧文档不产生结构化行"
        assert st["enabled"] is False, "升级后必须沿用学校原来的停用状态"

        caps.set_capability("internship", enabled=True, reason="重新启用实习模块",
                            tenant_id=TENANT)
        assert _state("internship")["enabled"] is True
        assert _state("internship")["configured"] is True
    finally:
        set_tenant(None)


# ── 旧整份写入口退役：只保留历史 JSON 读取，不再落结构化行 ────────────────────
def test_legacy_blob_write_is_rejected(client, auth_headers, db_mode):
    from app.core.context import set_tenant

    _ensure_tenant(TENANT)
    set_tenant({"tenantId": str(TENANT)})
    try:
        before = _state("campusService")
        with pytest.raises(AppException) as direct:
            gov.save_module_features(
                {"userId": "db-1"},
                {"campusService": {"enabled": False}},
                "旧整份接口不得继续写入",
            )
        assert direct.value.code == "CAPABILITY_AUTHORITY_MOVED"
        assert _state("campusService")["enabled"] == before["enabled"]
    finally:
        set_tenant(None)

    response = client.put(
        "/api/v1/system/module-features",
        headers=auth_headers,
        json={"features": {"campusService": {"enabled": False}}, "reason": "旧整份HTTP写入应拒绝"},
    )
    assert response.status_code == 409
    assert response.json()["bizCode"] == "CAPABILITY_AUTHORITY_MOVED"


# ── 影响预览：不许拿 0 冒充"无影响" ────────────────────────────────────────
def test_impact_preview_is_honest(db_mode):
    _ensure_tenant(TENANT)
    impact = caps.capability_impact("studentAffairs", tenant_id=TENANT)
    assert impact["capabilityKey"] == "studentAffairs"
    assert "/admin/student-affairs" in impact["menus"]
    assert any(api.startswith("/api/v1/") for api in impact["apis"])
    cascade = {row["capabilityKey"] for row in impact["cascadeDisabled"]}
    assert "orientation" in cascade, "停用学工中心会连带迎新不可用，必须先讲清楚"
    assert impact["countsExact"] is False
    assert set(impact["counts"]) == {"affectedUsers", "runningWorkflows",
                                     "pendingTodos", "fileBindings"}


# ── 目录本身 ─────────────────────────────────────────────────────────────────
def test_registry_excludes_platform_only_and_has_labels(db_mode):
    reg = caps.capability_registry()
    assert "platform" not in reg
    assert len(reg) >= 14
    for key, mod in reg.items():
        assert mod.get("label"), f"{key} 缺少中文名"
        assert mod.get("featureKey")


def test_unknown_capability_rejected(db_mode):
    with pytest.raises(AppException):
        caps.set_capability("not_a_capability", enabled=True, reason="不存在的能力",
                            tenant_id=TENANT)
    with pytest.raises(AppException):
        caps.capability_impact("not_a_capability", tenant_id=TENANT)


def test_alias_resolves_to_canonical_key(db_mode):
    _ensure_tenant(TENANT)
    caps.set_capability("graduation", enabled=False, reason="用别名停用毕业设计",
                        tenant_id=TENANT)
    assert _state("graduationDesign")["enabled"] is False
