"""School-scoped dictionary workspace backed by the existing platform config table.

Platform defaults remain the product baseline.  A school may only persist an
override for its own tenant; callers never supply a tenant id.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import PlatformConfig
from app.services import audit_log
from app.services import platform_defaults as defaults


DICTIONARY_META = {
    "schoolType": ("学校类型", "学校类型由平台统一维护"),
    "studentStatus": ("学生状态", "学生在校状态的显示名称"),
    "riskLevel": ("风险等级", "风险提醒和处置等级"),
    "approvalStatus": ("审批状态", "申请和审核结果的显示名称"),
    "fileType": ("文件类型", "导入、导出和业务附件分类"),
    "serviceType": ("在校服务类型", "学生在校服务分类"),
    "internshipStatus": ("实习状态", "岗位实习进度状态"),
    "graduationStatus": ("毕设阶段", "毕业设计办理阶段"),
    "employmentStatus": ("就业状态", "毕业去向和就业状态"),
    "noticeType": ("公告类型", "平台公告分类，由平台统一维护"),
    "tenantStatus": ("租户状态", "学校开通与停用状态，由平台统一维护"),
    "packageType": ("套餐类型", "学校订购套餐类型，由平台统一维护"),
}

SCHOOL_EDITABLE_DICTIONARIES = {
    "studentStatus",
    "riskLevel",
    "approvalStatus",
    "fileType",
    "serviceType",
    "internshipStatus",
    "graduationStatus",
    "employmentStatus",
}

# Dictionaries are display vocabulary, not a second business state machine.
# Each consumer owns its canonical values; a school override may only change
# the label of a value that consumer already understands.
EFFECTIVE_CONSUMERS = {
    "studentCenter": {
        "studentStatus": [
            ("ADMITTED", "已录取"),
            ("ACTIVE", "在读"),
            ("SUSPENDED", "休学/保留学籍"),
            ("GRADUATED", "已毕业"),
            ("DROPPED", "退学"),
            ("VOIDED", "已作废"),
            ("UNKNOWN", "未知"),
        ],
        "riskLevel": [
            ("NONE", "无"),
            ("LOW", "低"),
            ("MEDIUM", "中"),
            ("HIGH", "高"),
        ],
    },
}

_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _row(db, tenant_id: int, *, for_update: bool = False):
    stmt = select(PlatformConfig).where(
        PlatformConfig.tenant_id == int(tenant_id),
        PlatformConfig.config_type == "DICT",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def _payload(row) -> dict:
    return dict(row.config_json) if row is not None and isinstance(row.config_json, dict) else {}


def get_workspace(tenant_id: int) -> dict:
    if int(tenant_id or 0) <= 0:
        raise AppException("NO_TENANT", "当前登录身份未绑定学校", http_status=403)
    db = get_sessionmaker()()
    try:
        global_overrides = _payload(_row(db, 0))
        tenant_row = _row(db, tenant_id)
        tenant_overrides = _payload(tenant_row)
        dictionaries = []
        for code, (label, description) in DICTIONARY_META.items():
            items = (
                tenant_overrides.get(code)
                or global_overrides.get(code)
                or defaults.DEFAULT_DICTIONARIES.get(code)
                or []
            )
            dictionaries.append({
                "code": code,
                "label": label,
                "description": description,
                "source": "SCHOOL" if code in tenant_overrides else "PLATFORM",
                "editable": code in SCHOOL_EDITABLE_DICTIONARIES,
                "consumers": [
                    consumer for consumer, specs in EFFECTIVE_CONSUMERS.items() if code in specs
                ],
                "items": [dict(item) for item in items],
            })
        return {
            "version": int(tenant_row.version or 0) if tenant_row is not None else 0,
            "dictionaries": dictionaries,
        }
    finally:
        db.close()


def get_effective_options(tenant_id: int, consumer: str) -> dict:
    """Return safe school labels for one authenticated business consumer.

    Unknown school codes and attempts to hide required states are ignored.
    This keeps workflow/state validation authoritative in the owning domain.
    """
    if int(tenant_id or 0) <= 0:
        raise AppException("NO_TENANT", "当前登录身份未绑定学校", http_status=403)
    spec = EFFECTIVE_CONSUMERS.get(str(consumer or "").strip())
    if spec is None:
        raise AppException("VALIDATION_ERROR", "未知的数据字典使用场景")

    db = get_sessionmaker()()
    try:
        global_overrides = _payload(_row(db, 0))
        school_overrides = _payload(_row(db, tenant_id))
        result = {}
        for dict_code, canonical_items in spec.items():
            configured = school_overrides.get(dict_code) or global_overrides.get(dict_code) or []
            configured_labels = {
                str(item.get("code") or "").upper(): str(item.get("label") or "").strip()
                for item in configured
                if isinstance(item, dict) and str(item.get("label") or "").strip()
            }
            result[dict_code] = [
                {"value": code, "label": configured_labels.get(code, default_label)}
                for code, default_label in canonical_items
            ]
        return {"consumer": consumer, "statusOptions": result}
    finally:
        db.close()


def _clean_items(items) -> list[dict]:
    if not isinstance(items, list) or not items:
        raise AppException("VALIDATION_ERROR", "至少保留一个字典项")
    if len(items) > 200:
        raise AppException("VALIDATION_ERROR", "单类字典最多 200 项")
    cleaned = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise AppException("VALIDATION_ERROR", "字典项格式不正确")
        code = str(item.get("code") or "").strip()
        label = str(item.get("label") or "").strip()
        if not _CODE_RE.fullmatch(code):
            raise AppException("VALIDATION_ERROR", "字典编码只能使用字母、数字、点、横线和下划线，最多 64 位")
        if not label or len(label) > 80:
            raise AppException("VALIDATION_ERROR", "显示名称不能为空且最多 80 个字")
        normalized = code.upper()
        if normalized in seen:
            raise AppException("VALIDATION_ERROR", f"字典编码 {code} 重复")
        seen.add(normalized)
        cleaned.append({"code": code, "label": label, "enabled": bool(item.get("enabled", True))})
    return cleaned


def save_dictionary(tenant_id: int, dict_code: str, *, items, expected_version) -> dict:
    if int(tenant_id or 0) <= 0:
        raise AppException("NO_TENANT", "当前登录身份未绑定学校", http_status=403)
    if dict_code not in SCHOOL_EDITABLE_DICTIONARIES:
        raise AppException("VALIDATION_ERROR", "该字典不允许由学校维护")
    if expected_version is None:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法防止覆盖他人修改")
    try:
        expected = int(expected_version)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须为整数") from None
    cleaned = _clean_items(items)

    db = get_sessionmaker()()
    try:
        row = _row(db, tenant_id, for_update=True)
        current_version = int(row.version or 0) if row is not None else 0
        if expected != current_version:
            raise AppException(
                "DATA_CONFLICT",
                "字典已被其他人修改，请刷新后再保存",
                http_status=409,
                details={"expectedVersion": expected, "currentVersion": current_version},
            )
        payload = _payload(row)
        payload[dict_code] = cleaned
        if row is None:
            row = PlatformConfig(
                tenant_id=int(tenant_id),
                config_type="DICT",
                config_key="-",
                config_json=payload,
                enabled=True,
                version=1,
            )
            db.add(row)
        else:
            row.config_json = payload
            row.enabled = True
            row.version = current_version + 1
        db.commit()
        version = int(row.version or current_version + 1)
    except IntegrityError as exc:
        db.rollback()
        raise AppException("DATA_CONFLICT", "字典刚刚被其他人创建，请刷新后再保存", http_status=409) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    audit_log.record(
        "SCHOOL_DICTIONARY_UPDATE",
        f"本校数据字典：{DICTIONARY_META[dict_code][0]}",
        detail={"dictCode": dict_code, "itemCount": len(cleaned), "version": version},
        tenant_id=int(tenant_id),
    )
    return {"dictCode": dict_code, "items": cleaned, "version": version, "source": "SCHOOL"}
