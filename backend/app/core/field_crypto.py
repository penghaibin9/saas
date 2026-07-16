"""强敏感字段静态加密（家庭经济收入/负债、手机号等 `_encrypted` 列）。

安全审计 2026-07-17 发现：这些列名/model 注释长期宣称"密文"，实际写入时直接落明文
字符串，全仓无任何加密调用——脱敏只在 API 响应层生效，数据库层（含备份/拖库）明文
可见。本模块提供 Fernet 对称加密的 encrypt_field/decrypt_field，写入前加密、读出后
解密，脱敏（区间/掩码）仍在各 service 的 _mask_* 函数上做，二者职责不重叠。

存量兼容：decrypt_field 对"不是本模块加密产物"的值（历史明文行、空值）原样返回，不抛异常、
不阻塞读取；这些历史明文行会在下一次该记录被更新时自动转为密文（写路径统一走 encrypt_field），
无需停机批量回填、无需数据库迁移。
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    from app.core.config import settings
    return Fernet(settings.field_encryption_key.encode())


def encrypt_field(value) -> str | None:
    """加密后落库。None/空字符串原样返回（不加密空值，避免空态判断复杂化）。"""
    if value is None or value == "":
        return None
    return _fernet().encrypt(str(value).encode()).decode()


def decrypt_field(stored) -> str | None:
    """从库里取出后解密。非本模块加密产物（存量明文/空值）按原值返回，兼容迁移窗口。"""
    if not stored:
        return stored
    try:
        return _fernet().decrypt(str(stored).encode()).decode()
    except (InvalidToken, ValueError):
        return stored
