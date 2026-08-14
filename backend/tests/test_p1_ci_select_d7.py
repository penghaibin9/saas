"""D7-U selector 自检：考务便利性 source 变化必须拉起 MySQL 与 canonical 回归。"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_selector():
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "check" / "select_pytest_targets.py"
    spec = importlib.util.spec_from_file_location("select_pytest_targets_d7", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_d7_exam_convenience_sources_select_mysql_and_canonical_contracts():
    selector = _load_selector()
    required = {
        "tests/test_aa_exam_convenience.py",
        "tests/test_aa_exam_facade_contract_and_changes.py",
        "tests/test_aa_p0_authz.py",
        "tests/test_aa_route_registration_main_compat.py",
    }
    for source in (
        "backend/app/modules/academic_affairs/services/exam_convenience_service.py",
        "backend/app/modules/academic_affairs/routers/exam_core_router.py",
    ):
        assert required <= set(selector.select([source]))
