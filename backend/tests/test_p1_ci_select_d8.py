"""D8：成绩 Router/结构/认定读侧变更必须永久拉起 owner、并发、证据与规模合同。"""
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


def test_d8_grade_changes_select_all_owner_concurrency_and_recognition_contracts():
    mod = _load()
    for path in (
        "backend/app/modules/academic_affairs/routers/grade_core_router.py",
        "backend/app/modules/academic_affairs/routers/grade_read_router.py",
        "backend/app/modules/academic_affairs/routers/grade_change_recheck_router.py",
        "backend/app/modules/academic_affairs/routers/grade_recognition_router.py",
        "backend/app/modules/academic_affairs/services/academic_affairs_recognition_read_service.py",
        "backend/tests/test_aa_grade_core_router_contract.py",
        "backend/tests/test_aa_grade_read_router_contract.py",
        "backend/tests/test_aa_grade_change_recheck_router_contract.py",
        "backend/tests/test_aa_grade_recognition_router_contract.py",
        "backend/tests/test_aa_recognition_pagination_scaling.py",
        "backend/tests/test_p1_ci_select_d8.py",
    ):
        targets = mod.select([path])
        assert "tests/test_aa_grade_core_router_contract.py" in targets
        assert "tests/test_aa_grade_read_router_contract.py" in targets
        assert "tests/test_aa_grade_change_recheck_router_contract.py" in targets
        assert "tests/test_aa_grade_recognition_router_contract.py" in targets
        assert "tests/test_aa_grade_identity_head_concurrency.py" in targets
        assert "tests/test_aa_grade_recheck_concurrency.py" in targets
        assert "tests/test_aa_recognition.py" in targets
        assert "tests/test_aa_recognition_evidence_and_mutex.py" in targets
        assert "tests/test_aa_recognition_pagination_scaling.py" in targets
        assert "tests/test_aa_service_entrypoint_integrity.py" in targets
        assert "tests/test_aa_p0_authz.py" in targets
        assert "tests/test_aa_route_registration_main_compat.py" in targets
