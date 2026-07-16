"""通用用户偏好（/api/v1/me/preferences）端到端测试。

重点验证：读写闭环、只能动自己的偏好（user_key 取自令牌）、跨租户隔离、非法输入不落库。
首个用途是新手引导「已看过」标记。
"""
from __future__ import annotations

MAIN = 1000000000000000001
OTHER = 1000000000000000002

BASE = "/api/v1/me/preferences"
GUIDE_KEY = "guide.graduation.gd-batches"


def _token(user_id, user_type="TEACHER", tenant_id=MAIN, tid="demo", role="COUNSELOR"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id, "realName": f"用户{user_id}", "userType": user_type,
        "tid": tid, "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"})}


def test_preference_set_and_get_roundtrip(client, db_mode):
    """写入后能读回；未设置过的键不出现在结果里（由前端决定默认值）。"""
    hdr = _token("u-pref-1")
    empty = client.get(BASE, headers=hdr).json()
    assert empty["code"] == 0
    assert empty["data"]["items"] == {}

    saved = client.post(BASE, headers=hdr, json={"key": GUIDE_KEY, "value": "1"}).json()
    assert saved["code"] == 0
    assert saved["data"] == {"key": GUIDE_KEY, "value": "1"}

    got = client.get(BASE, headers=hdr).json()["data"]["items"]
    assert got == {GUIDE_KEY: "1"}


def test_preference_overwrite_same_key(client, db_mode):
    """同一键重复写入应覆盖而非建重复行（uk_user_pref 约束）。"""
    hdr = _token("u-pref-2")
    client.post(BASE, headers=hdr, json={"key": GUIDE_KEY, "value": "1"})
    client.post(BASE, headers=hdr, json={"key": GUIDE_KEY, "value": "2"})
    items = client.get(BASE, headers=hdr).json()["data"]["items"]
    assert items == {GUIDE_KEY: "2"}


def test_preference_keys_filter(client, db_mode):
    """keys 参数只返回指定键。"""
    hdr = _token("u-pref-3")
    client.post(BASE, headers=hdr, json={"key": "guide.a", "value": "1"})
    client.post(BASE, headers=hdr, json={"key": "guide.b", "value": "2"})
    only_a = client.get(f"{BASE}?keys=guide.a", headers=hdr).json()["data"]["items"]
    assert only_a == {"guide.a": "1"}
    both = client.get(f"{BASE}?keys=guide.a,guide.b", headers=hdr).json()["data"]["items"]
    assert both == {"guide.a": "1", "guide.b": "2"}


def test_preference_isolated_between_users(client, db_mode):
    """A 写的偏好 B 读不到——user_key 取自令牌，不接受外部传入。"""
    hdr_a = _token("u-pref-a")
    hdr_b = _token("u-pref-b")
    client.post(BASE, headers=hdr_a, json={"key": GUIDE_KEY, "value": "1"})
    assert client.get(BASE, headers=hdr_b).json()["data"]["items"] == {}
    # 即使 body 里塞 userKey 也改不了别人的偏好
    client.post(BASE, headers=hdr_b, json={"key": GUIDE_KEY, "value": "9", "userKey": "u-pref-a"})
    assert client.get(BASE, headers=hdr_a).json()["data"]["items"] == {GUIDE_KEY: "1"}
    assert client.get(BASE, headers=hdr_b).json()["data"]["items"] == {GUIDE_KEY: "9"}


def test_preference_isolated_between_tenants(client, db_mode):
    """同一 userId 在不同租户下的偏好互不可见（行级隔离）。"""
    hdr_main = _token("u-same-id", tenant_id=MAIN, tid="demo")
    hdr_other = _token("u-same-id", tenant_id=OTHER, tid="other")
    client.post(BASE, headers=hdr_main, json={"key": GUIDE_KEY, "value": "1"})
    assert client.get(BASE, headers=hdr_other).json()["data"]["items"] == {}


def test_preference_empty_key_rejected(client, db_mode):
    """空键必须明确报错——不能既不落库又回「已保存」骗调用方。"""
    hdr = _token("u-pref-4")
    for bad in ("", "   "):
        r = client.post(BASE, headers=hdr, json={"key": bad, "value": "1"}).json()
        assert r["code"] != 0, f"空键 {bad!r} 应被拒绝"
    assert client.get(BASE, headers=hdr).json()["data"]["items"] == {}


def test_preference_overlong_key_rejected(client, db_mode):
    """超长键报错，而不是等 MySQL 抛 1406 变成 500。"""
    hdr = _token("u-pref-6")
    r = client.post(BASE, headers=hdr, json={"key": "g" * 101, "value": "1"}).json()
    assert r["code"] != 0


def test_preference_long_value_truncated(client, db_mode):
    """超长值截断到 500，不撑爆列。"""
    hdr = _token("u-pref-5")
    client.post(BASE, headers=hdr, json={"key": "guide.long", "value": "x" * 900})
    items = client.get(BASE, headers=hdr).json()["data"]["items"]
    assert len(items["guide.long"]) == 500


def test_preference_requires_auth(client, db_mode):
    """未登录不可读写。"""
    assert client.get(BASE).status_code in (401, 403)
    assert client.post(BASE, json={"key": GUIDE_KEY, "value": "1"}).status_code in (401, 403)


def test_preference_student_can_use(client, db_mode):
    """学生身份也能读写自己的偏好（引导对学生端同样适用，故不挂 require_staff）。"""
    hdr = _token("u-stu-1", user_type="STUDENT", role="STUDENT")
    r = client.post(BASE, headers=hdr, json={"key": "guide.mobile.home", "value": "1"}).json()
    assert r["code"] == 0
    assert client.get(BASE, headers=hdr).json()["data"]["items"] == {"guide.mobile.home": "1"}
