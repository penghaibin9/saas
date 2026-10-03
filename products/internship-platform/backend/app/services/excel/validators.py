"""公共 Excel 底座 · 可复用字段校验器（V1.1）。

每个校验器签名统一：fn(value: str, col) -> str | None
- 返回 None 表示通过；返回中文错误信息表示不通过。
- value 已被 pipeline 规整为 str（空值为 ""）。
业务模块可在 ColumnSpec.validators 里追加自定义校验，复用本文件同一套原子校验，
避免「Excel 导入」和「高级粘贴导入」两套规则不一致（CLAUDE.md §38.12）。
"""
from __future__ import annotations

import re
from datetime import datetime

# ── 常用正则（学校真实业务高频）──
RE_PHONE = re.compile(r"^1[3-9]\d{9}$")                       # 大陆手机号
RE_IDCARD = re.compile(r"^\d{17}[\dXx]$")                     # 18 位身份证
RE_CREDIT = re.compile(r"^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}$")  # 统一社会信用代码
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S")


def check_required(value: str, col) -> str | None:
    if value is None or str(value).strip() == "":
        return f"{col.title} 必填"
    return None


def check_max_length(value: str, col) -> str | None:
    if col.max_length and value and len(value) > col.max_length:
        return f"{col.title} 超过最大长度 {col.max_length}（当前 {len(value)}）"
    return None


def check_int(value: str, col) -> str | None:
    if value == "":
        return None
    try:
        int(str(value).strip())
    except (TypeError, ValueError):
        return f"{col.title} 必须为整数（当前：{value}）"
    return None


def check_decimal(value: str, col) -> str | None:
    if value == "":
        return None
    try:
        float(str(value).strip())
    except (TypeError, ValueError):
        return f"{col.title} 必须为数字（当前：{value}）"
    return None


def parse_date(value: str):
    """尝试按常见格式解析日期；失败返回 None。数字（Excel 序列号）不在此处理。"""
    s = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def check_date(value: str, col) -> str | None:
    if value == "":
        return None
    if parse_date(value) is None:
        return f"{col.title} 日期格式不正确（应形如 2026-07-07）"
    return None


def check_phone(value: str, col) -> str | None:
    if value == "":
        return None
    if not RE_PHONE.match(str(value).strip()):
        return f"{col.title} 手机号格式不正确"
    return None


def check_idcard(value: str, col) -> str | None:
    if value == "":
        return None
    if not RE_IDCARD.match(str(value).strip()):
        return f"{col.title} 身份证号格式不正确（应为 18 位）"
    return None


def check_credit_code(value: str, col) -> str | None:
    if value == "":
        return None
    if not RE_CREDIT.match(str(value).strip().upper()):
        return f"{col.title} 统一社会信用代码格式不正确（应为 18 位）"
    return None


def check_email(value: str, col) -> str | None:
    if value == "":
        return None
    if not RE_EMAIL.match(str(value).strip()):
        return f"{col.title} 邮箱格式不正确"
    return None


def check_enum(value: str, col) -> str | None:
    if value == "" or not col.options:
        return None
    if str(value).strip() not in col.options:
        return f"{col.title} 取值须为 {'/'.join(col.options)} 之一（当前：{value}）"
    return None


# type → 内置类型校验器（required / max_length / enum 由 pipeline 统一先行）
TYPE_VALIDATORS = {
    "str": [],
    "int": [check_int],
    "decimal": [check_decimal],
    "date": [check_date],
    "phone": [check_phone],
    "idcard": [check_idcard],
    "creditcode": [check_credit_code],
    "email": [check_email],
    "enum": [check_enum],
}
