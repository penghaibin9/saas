"""复审合同：动态材料审核端点必须落到材料代码级原子权限并默认拒绝未知映射。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.core.graduation_permissions import (
    GRADUATION_DYNAMIC_PERMISSION_ENDPOINTS, GRADUATION_PERMISSION_CODES,
    graduation_permission_for_endpoint,
)
from app.modules.graduation.materials.command_service import review_permission_code
from app.modules.graduation.materials.definitions import (
    DEFAULT_MATERIAL_DEFINITIONS, REVIEW_PERMISSION_BY_CODE,
)
from app.modules.graduation.materials.rule_service import _normalize_item
from app.modules.graduation.routers.graduation_material_center import review_material_item


def test_dynamic_material_review_endpoint_is_registered_for_permission_inventory():
    endpoint_key = f"{review_material_item.__module__.rsplit('.', 1)[-1]}.{review_material_item.__name__}"
    assert endpoint_key in GRADUATION_DYNAMIC_PERMISSION_ENDPOINTS
    assert graduation_permission_for_endpoint(review_material_item) == "graduationDesign.review.submit"


def test_every_reviewable_default_material_has_an_atomic_permission():
    reviewable = {
        row["materialCode"] for row in DEFAULT_MATERIAL_DEFINITIONS
        if row.get("reviewRequired")
    }
    assert reviewable <= set(REVIEW_PERMISSION_BY_CODE)
    assert set(REVIEW_PERMISSION_BY_CODE.values()) <= GRADUATION_PERMISSION_CODES
    for material_code in reviewable:
        assert review_permission_code(material_code) == REVIEW_PERMISSION_BY_CODE[material_code]


def test_custom_reviewable_material_without_atomic_permission_fails_closed():
    raw = {
        "materialCode": "CUSTOM_REVIEW", "materialName": "自定义审核材料",
        "stage": "FINAL_APPROVED", "ownerRole": "STUDENT",
        "allowedExtensions": ["pdf"], "maxSizeBytes": 1024,
        "reviewRequired": True, "archiveRequired": True,
    }
    with pytest.raises(AppException) as exc_info:
        _normalize_item(raw, 1)
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert "原子审核权限" in exc_info.value.message
