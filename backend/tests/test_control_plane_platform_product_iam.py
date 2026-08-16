import json
from pathlib import Path

from app.services import audit_log


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
