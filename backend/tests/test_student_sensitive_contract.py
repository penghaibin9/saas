"""学生敏感字段读取链与投影同步回归锁（学生主档统一整改 阶段 A）。

锁四类已修复的真实缺陷，防回归：
1. 密文列直接交给脱敏函数 → 页面显示「被遮住的 Fernet 密文」；
2. 投影同步用 `College.name` 等不存在的属性 → 带组织的主档一改就 AttributeError；
3. 教务证件完整查看直接回传密文列 → 拿到的不是证件号；
4. 教务更正把密文当明文比较 → Fernet 每次结果不同，证件号更正恒卡 409。
"""
from __future__ import annotations

import pytest

from app.core.field_crypto import (encrypt_field, mask_id_card_encrypted, mask_phone,
                                   mask_phone_encrypted)


# ── 1. 解密后再脱敏 ────────────────────────────────────────────────────────

def test_mask_phone_encrypted_decrypts_before_masking():
    plain = "13812345678"
    cipher = encrypt_field(plain)
    assert cipher and cipher.startswith("gAAAA"), "前提：encrypt_field 产出 Fernet 密文"
    masked = mask_phone_encrypted(cipher)
    assert masked == mask_phone(plain) == "138****5678"
    assert "gAAAA" not in masked, "脱敏结果不得残留密文片段"


def test_mask_id_card_encrypted_decrypts_before_masking():
    plain = "110101199001011234"
    masked = mask_id_card_encrypted(encrypt_field(plain))
    assert masked.startswith("110") and masked.endswith("1234")
    assert "gAAAA" not in masked


def test_mask_encrypted_tolerates_legacy_plaintext_and_empty():
    # 历史行仍是明文时不能报错，也不能把明文原样吐出
    assert mask_phone_encrypted("13812345678") == "138****5678"
    assert mask_phone_encrypted(None) == ""
    assert mask_phone_encrypted("") == ""


def test_mask_encrypted_degrades_on_broken_ciphertext():
    """单行密文损坏不能让整个列表 500，只降级为 ***。"""
    assert mask_phone_encrypted("gAAAA-this-is-not-a-valid-fernet-token-xxxxxxxxxxxx") == "***"


# ── 2. 投影同步字段名 ──────────────────────────────────────────────────────

def test_projection_reads_real_org_column_names():
    """org 模型只有 college_name/major_name/class_name，没有 .name。"""
    from app.models.org import College, Major, SchoolClass

    assert hasattr(College, "college_name") and not hasattr(College, "name")
    assert hasattr(Major, "major_name") and not hasattr(Major, "name")
    assert hasattr(SchoolClass, "class_name") and not hasattr(SchoolClass, "name")


def test_projection_exposes_in_session_variant():
    """主档写路径必须能在自己的事务内同步投影（失败一起回滚）。"""
    from app.services import student_projection_sync as sync

    assert callable(getattr(sync, "sync_student_projections_in_session", None))


def test_master_write_path_uses_in_session_sync():
    """主档写路径的投影必须同事务，且不得在 commit 之后调独立事务版本。

    阶段 B 后投影调用已下沉到 student_master_application_service：
    db_service 只负责委托，实际同步在统一服务内完成。
    """
    import inspect

    from app.services import db_service
    from app.services import student_master_application_service as master

    # 统一服务：用 in_session 版本，且不碰独立事务版本
    src = inspect.getsource(master._sync_projections)
    assert "sync_student_projections_in_session" in src, "统一服务应使用同事务投影"
    assert "sync_student_projections(" not in src.replace(
        "sync_student_projections_in_session(", ""), "统一服务仍在调独立事务投影"

    # db_service 的写路径已收敛为委托，不得自己再拼投影/ORM
    for fn, expect in ((db_service.create_student, "create_student_in_session"),
                       (db_service.update_student, "update_identity_in_session")):
        fsrc = inspect.getsource(fn)
        assert expect in fsrc, f"{fn.__name__} 应委托统一服务（{expect}）"
        assert "sync_student_projections(" not in fsrc, f"{fn.__name__} 不应直接调独立事务投影"


# ── 3 & 4. 教务证件链 ──────────────────────────────────────────────────────

def test_correction_value_helpers_roundtrip_plaintext():
    """更正流程内部一律明文口径：存库加密、读回解密、审计脱敏。"""
    from app.modules.academic_affairs.services import academic_affairs_service as aa

    plain = "110101199001011234"
    stored = aa._correction_store_value("ID_CARD", plain)
    assert stored != plain and stored.startswith("gAAAA"), "证件号必须加密落库"
    assert aa._correction_plain_value("ID_CARD", stored) == plain
    audit = aa._correction_audit_value("ID_CARD", plain)
    assert plain not in audit and audit.endswith("1234"), "审计只能出现脱敏值"

    # 非敏感字段保持原样，不被误加密
    assert aa._correction_store_value("REAL_NAME", "张三") == "张三"
    assert aa._correction_plain_value("REAL_NAME", "张三") == "张三"


def test_correction_plain_value_reads_legacy_plaintext_rows():
    """改造前写入的明文历史行仍要能读回。"""
    from app.modules.academic_affairs.services import academic_affairs_service as aa

    assert aa._correction_plain_value("ID_CARD", "110101199001011234") == "110101199001011234"


def test_ciphertext_comparison_would_always_differ():
    """佐证 4：同一明文两次加密结果不同，故绝不能拿密文列做相等比较。"""
    plain = "110101199001011234"
    assert encrypt_field(plain) != encrypt_field(plain)


@pytest.mark.parametrize("func_name", ["roster", "reveal_roster_sensitive"])
def test_roster_sensitive_paths_do_not_return_raw_ciphertext(func_name):
    """名册脱敏与完整查看都不得把 `id_card_encrypted` 原样交出。"""
    import inspect

    from app.modules.academic_affairs.services import academic_affairs_service as aa

    src = inspect.getsource(getattr(aa, func_name))
    assert "_mask_id_card(s.id_card_encrypted)" not in src, "密文不得直接脱敏"
    assert '"idCard": s.id_card_encrypted' not in src, "完整查看必须先解密"
