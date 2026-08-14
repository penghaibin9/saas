"""D8：成绩 Router 变更必须永久拉起 owner 合同。"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "check" / "select_pytest_targets.py"
    spec = importlib.util.spec_from_file_location("select_pytest_targets_d8", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_d8_grade_router_changes_select_both_owner_contracts():
    mod = _load()
    for path in (
        "backend/app/modules/academic_affairs/routers/grade_core_router.py",
        "backend/app/modules/academic_affairs/routers/grade_read_router.py",
    ):
        targets = mod.select([path])
        assert "tests/test_aa_grade_core_router_contract.py" in targets
        assert "tests/test_aa_grade_read_router_contract.py" in targets
        assert "tests/test_aa_p0_authz.py" in targets
        assert "tests/test_aa_route_registration_main_compat.py" in targets
