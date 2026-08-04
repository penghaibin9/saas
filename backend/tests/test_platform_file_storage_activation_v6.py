"""PLAT-07 文件存储后端、密钥与生产环境验证（真库）。

后端配置存取/加密/脱敏/测试连接的代码在"阶段8"就已经做好（app/services/
storage/config.py），本卡缺的不是代码，是真实腾讯云 COS 凭据——AI 不能
替甲方在云控制台建账号/发密钥，这一步只能甲方自己做（见「上线前必做
清单-总闸门.md」PLAT-07 条目）。这里只补此前一直缺失的自动化测试，覆盖
不需要真实云凭据也能验证的部分：加密存库不落明文、脱敏回显、"未改则
保留原值"的合并语义、必填校验，以及用 mock 掉 COS SDK 覆盖 test_connection
的成功/失败两条分支（不对外发真实网络请求，不依赖真实凭据也不依赖
外网可达性）。
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def clean_file_storage_config(db_mode):
    """每个用例前清空 FILE_STORAGE 配置，避免相互污染。"""
    from app.db.session import get_sessionmaker
    from sqlalchemy import select
    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0, PlatformConfig.config_type == "FILE_STORAGE")).all()
        for r in rows:
            db.delete(r)
        db.commit()
    finally:
        db.close()
    yield


# ── PLAT07-T01：密钥加密存库，DB 里不落明文 ─────────────────────────────────
def test_t01_secret_key_stored_encrypted_not_plaintext(clean_file_storage_config):
    from app.db.session import get_sessionmaker
    from sqlalchemy import select
    from app.models import PlatformConfig
    from app.services.storage import config as storage_config

    plain_key = "PLAINTEXT-SECRET-KEY-SHOULD-NEVER-APPEAR-IN-DB"
    storage_config.save_config({
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "test-bucket-1234567890",
        "cosSecretId": "FAKE-TEST-SECRET-ID-NOT-REAL-0000000000",
        "cosSecretKey": plain_key,
    })

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0, PlatformConfig.config_type == "FILE_STORAGE",
            PlatformConfig.is_deleted.is_(False))).first()
        assert row is not None
        stored_json = str(row.config_json)
        assert plain_key not in stored_json  # 明文绝不出现在库里
        assert row.config_json.get("cosSecretKeyEnc")  # 但确实存了（加密后的）密文
    finally:
        db.close()

    # 加密是可逆的：effective_config() 能正确解出原文，供后端真正调用 COS 时使用
    effective = storage_config.effective_config()
    assert effective["cosSecretKey"] == plain_key


# ── PLAT07-T02：脱敏回显只留后4位，不泄漏完整密钥 ───────────────────────────
def test_t02_masked_config_only_shows_last_four_chars(clean_file_storage_config):
    from app.services.storage import config as storage_config

    storage_config.save_config({
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "test-bucket-1234567890",
        "cosSecretId": "FAKE-TEST-SECRET-ID-NOT-REAL-0000000000",
        "cosSecretKey": "abcd1234efgh5678",
    })
    masked = storage_config.masked_config()
    assert masked["cosSecretKey"].endswith("5678")
    assert "abcd1234efgh" not in masked["cosSecretKey"]
    assert masked["hasSecretKey"] is True
    assert masked["hasSecretId"] is True


# ── PLAT07-T03：前端回传脱敏占位（未修改）时保留原密钥，不会被占位符覆盖 ────
def test_t03_resaving_with_masked_placeholder_preserves_previous_secret(clean_file_storage_config):
    from app.services.storage import config as storage_config

    original_key = "original-real-secret-key-value"
    storage_config.save_config({
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "test-bucket-1234567890",
        "cosSecretId": "FAKE-TEST-SECRET-ID-NOT-REAL-0000000000",
        "cosSecretKey": original_key,
    })
    masked_view = storage_config.masked_config()

    # 模拟前端"只改了地域，密钥字段原样回传脱敏占位"的保存场景
    storage_config.save_config({
        "backend": "cos", "cosRegion": "ap-shanghai", "cosBucket": "test-bucket-1234567890",
        "cosSecretId": masked_view["cosSecretId"], "cosSecretKey": masked_view["cosSecretKey"],
    })
    effective = storage_config.effective_config()
    assert effective["cosSecretKey"] == original_key  # 没被脱敏占位符覆盖掉
    assert effective["cosRegion"] == "ap-shanghai"  # 地域确实改了


# ── PLAT07-T04：启用 COS 后端时必填项校验真实生效 ──────────────────────────
def test_t04_cos_backend_requires_all_fields(clean_file_storage_config):
    from app.core.exceptions import AppException
    from app.services.storage import config as storage_config

    with pytest.raises(AppException) as exc:
        storage_config.save_config({"backend": "cos", "cosRegion": "ap-guangzhou"})
    assert "SecretId" in exc.value.message or "SecretKey" in exc.value.message


# ── PLAT07-T05：无平台配置时回退 local，行为可预期 ─────────────────────────
def test_t05_no_config_falls_back_to_local_backend(clean_file_storage_config):
    from app.services.storage import config as storage_config

    effective = storage_config.effective_config()
    assert effective["backend"] == "local"
    assert effective["source"] == "env"


# ── PLAT07-T06：test_connection 的确定性分支（不依赖真实网络/真实凭据）────
def test_t06_test_connection_local_backend_is_noop(clean_file_storage_config):
    from app.services.storage import config as storage_config

    result = storage_config.test_connection()
    assert result["ok"] is False
    assert "本地磁盘" in result["message"]


def test_t06b_test_connection_missing_field_reports_which_one(clean_file_storage_config):
    from app.db.session import get_sessionmaker
    from app.services import platform_service
    from app.services.storage import config as storage_config

    # 直接写一条缺 bucket 的配置，绕开 save_config 的必填校验，模拟脏配置场景
    platform_service.put_config_json(0, "FILE_STORAGE", "-", {
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "",
        "cosSecretId": "FAKE-x", "cosSecretKeyEnc": storage_config._encrypt("x"),
    })
    result = storage_config.test_connection()
    assert result["ok"] is False
    assert "桶名" in result["message"]


def test_t06c_test_connection_success_and_failure_via_mocked_sdk(clean_file_storage_config, monkeypatch):
    """真实网络连接需要真实腾讯云凭据（PLAT-07 卡在这一步，见总闸门登记）；
    这里 mock 掉 COS SDK 本身，只验证 test_connection() 对 SDK 返回结果的
    处理逻辑是对的——探针写入/删除都被调用、异常被转成友好消息，不泄漏堆栈。"""
    from app.services.storage import config as storage_config

    storage_config.save_config({
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "test-bucket-1234567890",
        "cosSecretId": "FAKE-TEST-SECRET-ID-NOT-REAL-0000000000",
        "cosSecretKey": "fake-secret-key-for-mocked-sdk-test",
    })

    calls = {"put": None, "delete": None}

    class _FakeClient:
        def __init__(self, *_a, **_kw):
            pass

        def put_object(self, Bucket, Body, Key):  # noqa: N803 — 与 COS SDK 参数名保持一致
            calls["put"] = (Bucket, Key)

        def delete_object(self, Bucket, Key):  # noqa: N803
            calls["delete"] = (Bucket, Key)

    import qcloud_cos
    monkeypatch.setattr(qcloud_cos, "CosS3Client", _FakeClient)
    monkeypatch.setattr(qcloud_cos, "CosConfig", lambda **kw: kw)

    ok_result = storage_config.test_connection()
    assert ok_result["ok"] is True
    assert calls["put"] is not None and calls["delete"] is not None
    assert calls["put"][1] == ".healthcheck/probe.txt"

    class _FailingClient:
        def __init__(self, *_a, **_kw):
            pass

        def put_object(self, Bucket, Body, Key):  # noqa: N803
            raise RuntimeError("模拟：SecretId/SecretKey 无效或桶不存在")

        def delete_object(self, Bucket, Key):  # noqa: N803
            pass

    monkeypatch.setattr(qcloud_cos, "CosS3Client", _FailingClient)
    fail_result = storage_config.test_connection()
    assert fail_result["ok"] is False
    assert "模拟" in fail_result["message"]


# ── HTTP：仅平台超管可访问，密钥不通过 API 明文回显 ────────────────────────
def test_http_file_storage_endpoints_require_platform_super_admin(client, clean_file_storage_config):
    from app.core.security import create_access_token

    school_token = create_access_token({
        "userId": "u-plat07-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/file-storage", headers={"Authorization": f"Bearer {school_token}"})
    assert r.status_code == 403

    admin_token = create_access_token({
        "userId": "u-plat07-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = client.put("/api/v1/platform/file-storage", headers=headers, json={"config": {
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "test-bucket-1234567890",
        "cosSecretId": "FAKE-TEST-SECRET-ID-NOT-REAL-0000000000",
        "cosSecretKey": "http-smoke-secret-key",
    }})
    assert r.json()["code"] == 0, r.json()
    assert "http-smoke-secret-key" not in str(r.json())  # HTTP 响应体不回显明文密钥

    r = client.get("/api/v1/platform/file-storage", headers=headers)
    body = r.json()
    assert body["code"] == 0, body
    assert "http-smoke-secret-key" not in str(body)
    assert body["data"]["config"]["hasSecretKey"] is True
