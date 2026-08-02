"""SYS-11 有效配置继承链（真库）。

对应必测 SYS11-T01～T04：完整来源链与 consumer / 学校覆盖不得突破平台底线 /
未来配置按时生效 / 并发保存 409。另加一条关键回归：升级后既有 t_sys_config
必须继续参与解析，否则学校已配置的登录锁定策略会在上线瞬间悄悄回到默认值。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services import effective_config_service as svc

TENANT = 8901
OTHER_TENANT = 8902
KEY = "SEC_LOCK_MAX_FAIL"


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed():
    svc.ensure_definitions()


def _set_legacy(tenant_id: int, key: str, value: str) -> None:
    from app.models import SysConfig

    with _session() as db:
        db.add(SysConfig(tenant_id=tenant_id, config_key=key, value_text=value, config_group="SECURITY"))
        db.commit()


# ── SYS11-T01：完整来源链与 consumer ────────────────────────────────────────
def test_t01_chain_reports_every_layer_and_real_consumers(db_mode):
    _seed()
    result = svc.resolve(KEY, tenant_id=TENANT)

    assert result["value"] == 5  # 套餐默认
    assert result["sourceLayer"] == "PACKAGE_DEFAULT"
    layers = [c["layer"] for c in result["chain"]]
    assert "PLATFORM_FLOOR" in layers
    assert "PACKAGE_DEFAULT" in layers
    # consumer 必须是代码里真实存在的读取点，不是设想
    assert result["consumers"] == ["auth_service_db.record_login_failure"]
    assert result["takesEffectImmediately"] is True
    assert result["platformFloor"] == {"min": 3, "max": 10}


def test_t01_tenant_override_wins_and_shows_in_chain(db_mode):
    _seed()
    svc.set_override(KEY, value=7, reason="学校提高容忍度", tenant_id=TENANT)
    result = svc.resolve(KEY, tenant_id=TENANT)
    assert result["value"] == 7
    assert result["sourceLayer"] == "TENANT"
    assert [c["layer"] for c in result["chain"]][-1] == "TENANT"


def test_t01_org_unit_and_term_layers_take_precedence(db_mode):
    _seed()
    svc.set_override(KEY, value=6, reason="全校", tenant_id=TENANT)
    svc.set_override(
        KEY, value=8, scope_type="ORG_UNIT", scope_id="COLLEGE:1", reason="某学院放宽", tenant_id=TENANT
    )
    svc.set_override(KEY, value=9, scope_type="TERM", scope_id="TERM:2027", reason="某学期", tenant_id=TENANT)

    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 6
    assert svc.resolve(KEY, org_unit_id="COLLEGE:1", tenant_id=TENANT)["value"] == 8
    # 学期层优先级高于组织层
    scoped = svc.resolve(KEY, org_unit_id="COLLEGE:1", term_id="TERM:2027", tenant_id=TENANT)
    assert scoped["value"] == 9
    assert scoped["sourceLayer"] == "TERM"
    # 别的学院不受影响
    assert svc.resolve(KEY, org_unit_id="COLLEGE:2", tenant_id=TENANT)["value"] == 6


def test_t01_legacy_sys_config_still_participates(db_mode):
    """升级不得让学校已配置的登录锁定策略悄悄失效。"""
    _seed()
    _set_legacy(TENANT, KEY, "9")
    result = svc.resolve(KEY, tenant_id=TENANT)
    assert result["value"] == 9
    assert result["sourceLayer"] == "TENANT_LEGACY"

    # 新的 TENANT 覆盖仍然能盖过旧表
    svc.set_override(KEY, value=4, reason="收紧", tenant_id=TENANT)
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 4


def test_t01_config_is_tenant_isolated(db_mode):
    _seed()
    svc.set_override(KEY, value=7, reason="本校", tenant_id=TENANT)
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 7
    assert svc.resolve(KEY, tenant_id=OTHER_TENANT)["value"] == 5  # 别校仍是默认


# ── SYS11-T02：不得突破平台底线 ─────────────────────────────────────────────
def test_t02_below_platform_floor_is_rejected_not_clamped(db_mode):
    _seed()
    with pytest.raises(AppException) as exc:
        svc.set_override(KEY, value=1, reason="想关掉锁定", tenant_id=TENANT)
    assert exc.value.code == "CONFIG_BELOW_PLATFORM_FLOOR"
    # 拒绝之后值必须没变，不能被静默夹逼成 3
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 5


def test_t02_above_platform_ceiling_is_rejected(db_mode):
    _seed()
    with pytest.raises(AppException) as exc:
        svc.set_override(KEY, value=99, reason="放太宽", tenant_id=TENANT)
    assert exc.value.code == "CONFIG_ABOVE_PLATFORM_CEILING"


def test_t02_boundary_values_are_allowed(db_mode):
    _seed()
    svc.set_override(KEY, value=3, reason="取下界", tenant_id=TENANT)
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 3
    svc.set_override(KEY, value=10, reason="取上界", tenant_id=TENANT)
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 10


def test_t02_non_integer_value_rejected(db_mode):
    _seed()
    with pytest.raises(AppException):
        svc.set_override(KEY, value="不是数字", reason="类型错误", tenant_id=TENANT)


def test_t02_unknown_config_key_rejected(db_mode):
    _seed()
    with pytest.raises(AppException):
        svc.resolve("SEC_NOT_REGISTERED", tenant_id=TENANT)


# ── SYS11-T03：未来配置按时生效 ─────────────────────────────────────────────
def test_t03_future_override_does_not_apply_yet(db_mode):
    _seed()
    future = datetime.utcnow() + timedelta(days=3)
    svc.set_override(KEY, value=8, effective_at=future, reason="下学期收紧", tenant_id=TENANT)

    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 5  # 现在还是默认
    later = svc.resolve(KEY, at=future + timedelta(hours=1), tenant_id=TENANT)
    assert later["value"] == 8


def test_t03_expired_override_stops_applying(db_mode):
    _seed()
    start = datetime.utcnow() - timedelta(days=2)
    end = datetime.utcnow() - timedelta(hours=1)
    svc.set_override(KEY, value=9, effective_at=start, expires_at=end, reason="临时放宽", tenant_id=TENANT)
    # 已过期：读取时就要失效，不依赖定时任务
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 5
    during = svc.resolve(KEY, at=start + timedelta(hours=1), tenant_id=TENANT)
    assert during["value"] == 9


def test_t03_expiry_must_be_after_effective(db_mode):
    _seed()
    now = datetime.utcnow()
    with pytest.raises(AppException):
        svc.set_override(
            KEY, value=6, effective_at=now, expires_at=now - timedelta(hours=1), reason="时间反了", tenant_id=TENANT
        )


def test_t03_revoked_override_falls_back(db_mode):
    _seed()
    created = svc.set_override(KEY, value=7, reason="先设置", tenant_id=TENANT)
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 7
    svc.revoke_override(
        int(created["overrideId"]), reason="撤销", expected_version=int(created["version"]), tenant_id=TENANT
    )
    assert svc.resolve(KEY, tenant_id=TENANT)["value"] == 5


# ── SYS11-T04：并发与留痕 ───────────────────────────────────────────────────
def test_t04_stale_version_returns_conflict(db_mode):
    _seed()
    now = datetime.utcnow()
    created = svc.set_override(KEY, value=6, effective_at=now, reason="第一次", tenant_id=TENANT)
    # 用同一 effective_at 再保存 = 更新同一行，版本号必须对得上
    svc.set_override(
        KEY, value=7, effective_at=now, reason="第二次",
        expected_version=int(created["version"]), tenant_id=TENANT,
    )
    with pytest.raises(AppException) as exc:
        svc.set_override(
            KEY, value=8, effective_at=now, reason="用过期版本号",
            expected_version=int(created["version"]), tenant_id=TENANT,
        )
    assert exc.value.code == "VERSION_CONFLICT"


def test_t04_change_history_records_before_and_after(db_mode):
    _seed()
    svc.set_override(KEY, value=6, reason="第一次调整", tenant_id=TENANT)
    svc.set_override(KEY, value=7, reason="第二次调整", tenant_id=TENANT)
    rows = svc.history(KEY, tenant_id=TENANT)["items"]
    assert len(rows) >= 2
    assert rows[0]["after"]["value"] == 7
    assert rows[0]["reason"] == "第二次调整"
    assert rows[0]["traceId"]


def test_t04_reason_is_mandatory(db_mode):
    _seed()
    with pytest.raises(AppException):
        svc.set_override(KEY, value=6, reason="", tenant_id=TENANT)


def test_t04_ensure_definitions_is_idempotent(db_mode):
    first = svc.ensure_definitions()
    second = svc.ensure_definitions()
    assert first["created"] == len(svc.SEED_DEFINITIONS)
    assert second["created"] == 0


# ── 真实生效：配置必须作用到登录强制层，而不是只在页面上好看 ────────────────
def test_override_actually_reaches_the_login_enforcement_layer(db_mode, monkeypatch):
    """auth_service_db 读的是 system_config_service.get_int；覆盖必须在那里生效。"""
    from app.services import system_config_service as legacy

    _seed()
    monkeypatch.setattr(legacy, "_tid", lambda **kw: TENANT)

    assert legacy.get_int(KEY, 5) == 5  # 默认

    _set_legacy(TENANT, KEY, "7")
    assert legacy.get_int(KEY, 5) == 7  # 旧表仍然有效

    svc.set_override(KEY, value=4, reason="分层覆盖收紧", tenant_id=TENANT)
    assert legacy.get_int(KEY, 5) == 4  # 新覆盖赢


def test_future_override_not_visible_to_enforcement_layer_yet(db_mode, monkeypatch):
    from app.services import system_config_service as legacy

    _seed()
    monkeypatch.setattr(legacy, "_tid", lambda **kw: TENANT)
    svc.set_override(
        KEY, value=9, effective_at=datetime.utcnow() + timedelta(days=1),
        reason="明天才生效", tenant_id=TENANT,
    )
    assert legacy.get_int(KEY, 5) == 5


def test_expired_override_not_visible_to_enforcement_layer(db_mode, monkeypatch):
    from app.services import system_config_service as legacy

    _seed()
    monkeypatch.setattr(legacy, "_tid", lambda **kw: TENANT)
    svc.set_override(
        KEY, value=9,
        effective_at=datetime.utcnow() - timedelta(days=2),
        expires_at=datetime.utcnow() - timedelta(hours=1),
        reason="已过期", tenant_id=TENANT,
    )
    assert legacy.get_int(KEY, 5) == 5
