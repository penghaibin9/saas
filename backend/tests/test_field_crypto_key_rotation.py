"""字段加密密钥轮换回归锁。

历史问题：只有一把 FIELD_ENCRYPTION_KEY，密文不带版本号。换钥＝所有历史
手机号/身份证密文永久解不开（列表只会降级显示 ***，看起来"还活着"）。
现在密文带 `k<版本>:` 信封，旧密钥进 FIELD_ENCRYPTION_PREVIOUS_KEYS 后仍可解。
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core import field_crypto as fc


@pytest.fixture
def rotate(monkeypatch):
    """返回一个可以把"当前密钥"换掉、并把旧钥挪进历史列表的工具。"""
    def _apply(current_key: str, key_id: str, previous: str = ""):
        monkeypatch.setattr(settings, "FIELD_ENCRYPTION_KEY", current_key, raising=False)
        monkeypatch.setattr(settings, "FIELD_ENCRYPTION_KEY_ID", key_id, raising=False)
        monkeypatch.setattr(settings, "FIELD_ENCRYPTION_PREVIOUS_KEYS", previous, raising=False)
    return _apply


def test_new_ciphertext_carries_key_version():
    cipher = fc.encrypt_field("13812345678")
    kid, body = fc.split_key_id(cipher)
    assert kid == settings.field_encryption_key_id
    assert body.startswith("gAAAA")
    assert fc.decrypt_field(cipher) == "13812345678"


def test_old_ciphertext_still_decrypts_after_key_rotation(rotate):
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()

    rotate(old_key, "1")
    old_cipher = fc.encrypt_field("110101199001011234")

    # 换钥：新钥当值班，旧钥进历史列表。
    rotate(new_key, "2", previous=f"1:{old_key}")
    assert fc.decrypt_field(old_cipher) == "110101199001011234", "换钥后历史密文必须仍可解"
    assert fc.split_key_id(fc.encrypt_field("x"))[0] == "2", "新写入必须用新版本"


def test_rotation_without_keeping_old_key_is_detectable(rotate):
    """把旧钥丢了就是解不开——但必须是显式失败/降级，不能假装是"未填写"。"""
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    rotate(old_key, "1")
    old_cipher = fc.encrypt_field("13800000000")

    rotate(new_key, "2")  # 故意不带 previous
    assert fc.decrypt_field(old_cipher) is None
    assert fc.mask_phone_encrypted(old_cipher) == "***"


def test_rewrap_migrates_ciphertext_to_current_key(rotate):
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    rotate(old_key, "1")
    old_cipher = fc.encrypt_field("13800000000")

    rotate(new_key, "2", previous=f"1:{old_key}")
    rewrapped = fc.rewrap(old_cipher)
    assert fc.split_key_id(rewrapped)[0] == "2"
    assert fc.decrypt_field(rewrapped) == "13800000000"

    # 已是当前版本的密文重加密应是幂等的（不重复消耗、不改变可解性）。
    assert fc.rewrap(rewrapped) == rewrapped


def test_rewrap_raises_when_no_key_can_decrypt(rotate):
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    rotate(old_key, "1")
    old_cipher = fc.encrypt_field("13800000000")
    rotate(new_key, "2")
    with pytest.raises(ValueError):
        fc.rewrap(old_cipher)


def test_rewrap_encrypts_legacy_plaintext_rows(rotate):
    """加密上线前留下的明文行：重加密任务要顺手加密它，而不是报"解不开"。"""
    rotate(Fernet.generate_key().decode(), "3")
    out = fc.rewrap("13800000000")
    assert fc.split_key_id(out)[0] == "3"
    assert fc.decrypt_field(out) == "13800000000"


def test_legacy_ciphertext_without_version_prefix_still_decrypts(rotate):
    """换钥机制上线前写入的无前缀密文必须继续可读。"""
    key = Fernet.generate_key().decode()
    rotate(key, "1")
    legacy = Fernet(key.encode()).encrypt(b"13700000000").decode()
    assert not legacy.startswith("k")
    assert fc.decrypt_field(legacy) == "13700000000"


def test_search_hmac_does_not_change_when_encryption_key_rotates(rotate):
    """检索哈希必须与加密密钥解耦，否则换钥会让所有检索列失配。"""
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    hmac_key = Fernet.generate_key().decode()

    rotate(old_key, "1")
    settings.SENSITIVE_SEARCH_HMAC_KEY = hmac_key
    try:
        before = fc.hash_sensitive("13812345678", "phone")
        rotate(new_key, "2", previous=f"1:{old_key}")
        assert fc.hash_sensitive("13812345678", "phone") == before
    finally:
        settings.SENSITIVE_SEARCH_HMAC_KEY = ""


def test_invalid_previous_key_is_rejected_at_startup(rotate):
    rotate(Fernet.generate_key().decode(), "2", previous="1:这不是一把合法密钥")
    with pytest.raises(RuntimeError):
        fc.assert_field_encryption_safe()
