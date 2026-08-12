"""平台运营端 · 文件存储设置：读写闭环 + 密钥加密脱敏 + 越权 403 + 保存即生效。"""
from __future__ import annotations


def _owner_headers() -> dict:
    from app.core.security import create_access_token
    token = create_access_token({
        "userId": "u-platform-owner", "realName": "平台老板", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "1000000000000000000", "tenantName": "平台运营中心",
        "activeContextId": "ctx_platform_owner", "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


FS = "/api/v1/platform/file-storage"


def test_non_platform_admin_forbidden(client, auth_headers, db_mode):
    assert client.get(FS, headers=auth_headers).status_code == 403


def test_default_is_local(client, db_mode):
    body = client.get(FS, headers=_owner_headers()).json()
    assert body["code"] == 0
    assert body["data"]["config"]["backend"] == "local"


def test_save_cos_encrypts_and_masks_secret(client, db_mode):
    h = _owner_headers()
    payload = {"backend": "cos", "cosRegion": "ap-guangzhou",
               "cosBucket": "student-files-1250000000",
               "cosSecretId": "AKIDexample1234567890",
               "cosSecretKey": "realsecretkey9876543210"}
    saved = client.put(FS, headers=h, json={"config": payload}).json()
    assert saved["code"] == 0
    cfg = saved["data"]["config"]
    assert cfg["backend"] == "cos"
    # 读回脱敏：不回显明文，只留后 4 位
    assert cfg["cosSecretKey"].endswith("3210") and "realsecret" not in cfg["cosSecretKey"]
    assert cfg["hasSecretKey"] is True and cfg["cosSecretId"].endswith("7890")

    # 数据库里密钥是带 key-id 的字段加密密文，不是明文，也不再依赖 JWT 签名密钥。
    from app.services import platform_service
    raw = platform_service.get_config_json(0, "FILE_STORAGE", "-")
    assert raw["cosSecretKeyEnc"] and "realsecretkey" not in raw["cosSecretKeyEnc"]
    assert raw["cosSecretKeyEnc"].startswith("k")

    # 后端生效配置能解回明文（内部用）
    from app.services.storage import config as sc
    eff = sc.effective_config()
    assert eff["cosSecretKey"] == "realsecretkey9876543210"
    assert eff["backend"] == "cos" and eff["source"] == "platform"


def test_resave_with_masked_placeholder_keeps_secret(client, db_mode):
    h = _owner_headers()
    client.put(FS, headers=h, json={"config": {
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "b-1250000000",
        "cosSecretId": "AKIDkeepme0001", "cosSecretKey": "keepmesecret0001"}})
    # 只改桶名，密钥字段留空（前端未改）→ 旧密钥保留
    client.put(FS, headers=h, json={"config": {
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "b-new-1250000000",
        "cosSecretId": "", "cosSecretKey": ""}})
    from app.services.storage import config as sc
    eff = sc.effective_config()
    assert eff["cosBucket"] == "b-new-1250000000"
    assert eff["cosSecretKey"] == "keepmesecret0001"  # 未被抹掉


def test_persisted_cos_secret_survives_jwt_rotation(client, db_mode):
    """JWT 签名密钥轮换不得再让平台已保存的 COS SecretKey 失效。"""
    from app.core.config import settings
    from app.services.storage import config as sc

    h = _owner_headers()
    client.put(FS, headers=h, json={"config": {
        "backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "jwt-independent-1250000000",
        "cosSecretId": "AKID-independent", "cosSecretKey": "secret-survives-jwt-rotation"}})

    old_alias = settings.JWT_SECRET_KEY
    old_primary = settings.JWT_SECRET
    try:
        # 两个兼容配置名都轮换，确保测试不是碰巧仍能从另一个 JWT 值派生旧 Fernet。
        settings.JWT_SECRET_KEY = "rotated-jwt-secret-key-for-storage-test-0000000001"
        settings.JWT_SECRET = "rotated-jwt-secret-key-for-storage-test-0000000002"
        assert sc.effective_config()["cosSecretKey"] == "secret-survives-jwt-rotation"
    finally:
        settings.JWT_SECRET_KEY = old_alias
        settings.JWT_SECRET = old_primary


def test_legacy_jwt_encrypted_secret_is_read_and_rewrapped_on_save(db_mode):
    """升级不能要求学校重新输入 COS 密钥：旧 JWT 密文先兼容读取，再在保存时迁移。"""
    from app.core.config import settings
    from app.services import platform_service
    from app.services.storage import config as sc

    plain = "legacy-cos-secret-needs-safe-migration"
    legacy = sc._legacy_jwt_fernet().encrypt(plain.encode()).decode()
    assert legacy.startswith("gAAAA") and not legacy.startswith("k")
    platform_service.put_config_json(0, "FILE_STORAGE", "-", {
        "backend": "cos",
        "cosRegion": "ap-guangzhou",
        "cosBucket": "legacy-1250000000",
        "cosSecretId": "AKID-legacy",
        "cosSecretKeyEnc": legacy,
    })
    assert sc.effective_config()["cosSecretKey"] == plain

    # 不让操作者重填 secret，普通保存即完成重包。
    sc.save_config({
        "backend": "cos",
        "cosRegion": "ap-shanghai",
        "cosBucket": "legacy-1250000000",
        "cosSecretId": "",
        "cosSecretKey": "",
    })
    migrated = platform_service.get_config_json(0, "FILE_STORAGE", "-")["cosSecretKeyEnc"]
    assert migrated.startswith("k")
    assert migrated != legacy

    old_alias = settings.JWT_SECRET_KEY
    old_primary = settings.JWT_SECRET
    try:
        settings.JWT_SECRET_KEY = "post-migration-jwt-secret-key-000000000000001"
        settings.JWT_SECRET = "post-migration-jwt-secret-key-000000000000002"
        assert sc.effective_config()["cosSecretKey"] == plain
    finally:
        settings.JWT_SECRET_KEY = old_alias
        settings.JWT_SECRET = old_primary


def test_save_cos_missing_fields_rejected(client, db_mode):
    h = _owner_headers()
    res = client.put(FS, headers=h, json={"config": {"backend": "cos", "cosRegion": "ap-guangzhou"}}).json()
    assert res["code"] != 0  # 缺桶名/密钥 → 拒绝


def test_test_connection_on_local_is_noop(client, db_mode):
    h = _owner_headers()
    client.put(FS, headers=h, json={"config": {"backend": "local"}})
    res = client.post(f"{FS}/test", headers=h).json()
    assert res["code"] == 0 and res["data"]["ok"] is False
    assert "本地" in res["data"]["message"]
