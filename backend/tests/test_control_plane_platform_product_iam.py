import json
from pathlib import Path

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
    versions = [
        {"id": "3", "previousTemplateId": "2"},
        {"id": "2", "previousTemplateId": "1"},
        {"id": "1", "previousTemplateId": None},
    ]
    menus = {"1": ["a", "b", "c"], "2": ["b", "c"], "3": ["c"]}
    monkeypatch.setattr(product_iam_router, "_view", lambda _user: None)
    monkeypatch.setattr(product_iam_router.template_svc, "list_versions", lambda _code: versions)
    monkeypatch.setattr(product_iam_router.template_svc, "impact", lambda _id: {"baselineTemplateId": "1"})
    monkeypatch.setattr(product_iam_router, "_template_preview", lambda row: {
        "menuPreview": [{"surfaceKey": key} for key in menus[row["id"]]],
        "navigationDigest": "navigation", "sourceDigest": "source",
    })

    result = product_iam_router.school_role_template_impact("COLLEGE_ADMIN", 3, user={})
    assert result["data"]["menuRemoved"] == ["a", "b"]
