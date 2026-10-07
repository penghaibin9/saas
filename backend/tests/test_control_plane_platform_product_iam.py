import json
from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.services import audit_log
from app.modules.platform.routers import product_iam_router


def test_product_iam_keeps_single_internship_top_level_module():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "shared/contracts/module-manifest.json").read_text(encoding="utf-8"))
    keys = [str(item.get("moduleKey") or "") for item in manifest.get("modules") or []]
    assert keys.count("internship") == 1
    assert "recruitment" not in {key.lower() for key in keys}
    assert "recruitmentcenter" not in {key.lower() for key in keys}
    assert "enterpriserecruitment" not in {key.lower() for key in keys}


def test_product_iam_publish_is_critical_audit_action():
    assert "PLATFORM_PRODUCT_IAM_PUBLISH" in audit_log.CRITICAL_ACTIONS


def test_product_iam_router_does_not_touch_e_authority():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/platform/routers/product_iam_router.py").read_text(encoding="utf-8")
    assert "app.modules.internship" not in source
    assert "enterprise-portal" not in source


def test_template_menu_impact_uses_published_baseline_not_draft_predecessor(monkeypatch):
    monkeypatch.setattr(product_iam_router, "_view", lambda _user: None)
    monkeypatch.setattr(product_iam_router.template_svc, "list_versions", lambda _code: pytest.fail("second template read"))
    monkeypatch.setattr(product_iam_router, "_template_preview", lambda _row: pytest.fail("second menu read"))
    monkeypatch.setattr(product_iam_router.template_svc, "impact", lambda _id: {
        "templateCode": "COLLEGE_ADMIN", "publishStatus": "DRAFT", "baselineTemplateVersion": 1,
        "baselineTemplateId": "1", "menuAdded": [], "menuRemoved": ["a", "b"],
        "navigationDigest": "navigation", "removedPermissions": ["p1", "p2"],
    })
    monkeypatch.setattr(product_iam_router.svc, "source_snapshot", lambda: {
        "navigationDigest": "navigation", "sourceDigest": "source",
        "roleTemplates": [{"templateCode": "COLLEGE_ADMIN", "templateVersion": 1}],
    })

    result = product_iam_router.school_role_template_impact("COLLEGE_ADMIN", 3, user={})
    assert result["data"]["menuRemoved"] == ["a", "b"]
    assert result["data"]["sourceDigest"] == "source"


def test_template_impact_rejects_published_change_after_preview_read(monkeypatch):
    monkeypatch.setattr(product_iam_router, "_view", lambda _user: None)
    monkeypatch.setattr(product_iam_router.template_svc, "impact", lambda _id: {
        "templateCode": "COLLEGE_ADMIN", "publishStatus": "DRAFT",
        "baselineTemplateVersion": 1, "navigationDigest": "navigation",
    })
    monkeypatch.setattr(product_iam_router.svc, "source_snapshot", lambda: {
        "navigationDigest": "navigation", "sourceDigest": "source",
        "roleTemplates": [{"templateCode": "COLLEGE_ADMIN", "templateVersion": 2}],
    })

    with pytest.raises(AppException) as exc:
        product_iam_router.school_role_template_impact("COLLEGE_ADMIN", 3, user={})
    assert exc.value.code == "DATA_CONFLICT"
