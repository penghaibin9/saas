"""P1：CI 变更感知脚本自检。"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "check" / "select_pytest_targets.py"
    spec = importlib.util.spec_from_file_location("select_pytest_targets", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_core_change_selects_security_suite():
    mod = _load()
    targets = mod.select(["backend/app/middleware/context.py", "backend/app/core/config.py"])
    assert any("tenant_readonly" in t for t in targets)
    assert any("config_guards" in t for t in targets)


def test_file_change_selects_file_tests():
    mod = _load()
    targets = mod.select(["backend/app/services/file_content_security.py"])
    assert any("file" in t for t in targets)
