from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_admin_pc_cos_sdk_is_exact_npm_dependency_and_not_runtime_cdn():
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    source = (ROOT / "frontend/src/services/file/cosBrowserSdk.js").read_text(encoding="utf-8")

    assert package["dependencies"]["cos-js-sdk-v5"] == "1.10.1"
    assert lock["packages"][""]["dependencies"]["cos-js-sdk-v5"] == "1.10.1"
    sdk = lock["packages"]["node_modules/cos-js-sdk-v5"]
    assert sdk["version"] == "1.10.1"
    assert sdk.get("resolved", "").startswith("https://registry.npmjs.org/cos-js-sdk-v5/")
    assert sdk.get("integrity", "").startswith("sha512-")

    assert "import COS from 'cos-js-sdk-v5'" in source
    assert "cdn.jsdelivr.net" not in source
    assert "document.createElement('script')" not in source
    assert "document.head.appendChild" not in source
    assert "tmpSecretKey" not in source
    assert "SecretKey:" not in source
