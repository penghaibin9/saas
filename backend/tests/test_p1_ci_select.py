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


def test_workbench_snapshot_change_selects_snapshot_contract():
    mod = _load()
    targets = mod.select(["backend/app/services/workbench_snapshot_service.py"])
    assert "tests/test_workbench_snapshot.py" in targets


def test_help_metrics_change_selects_real_mysql_api_regression():
    mod = _load()
    for path in (
        "backend/app/api/v1/help_metrics.py",
        "backend/app/services/help_metrics_service.py",
    ):
        targets = mod.select([path])
        assert "tests/test_help_metrics.py" in targets


def test_changed_backend_test_is_selected_exactly():
    mod = _load()
    targets = mod.select(["backend/tests/test_aa_prerequisite_api_real.py"])
    assert "tests/test_aa_prerequisite_api_real.py" in targets


def test_academic_change_runs_stable_gate_and_changed_regression_only():
    mod = _load()
    targets = mod.select([
        "backend/app/modules/academic_affairs/services/academic_affairs_selection_service.py",
        "backend/tests/test_aa_prerequisite_api_real.py",
    ])
    assert "tests/test_aa_p0_authz.py" in targets
    assert "tests/test_aa_route_registration_main_compat.py" in targets
    assert "tests/test_aa_prerequisite_api_real.py" in targets
    assert "tests/test_aa_*.py" not in targets
    assert "tests/test_portal_academic*.py" not in targets


def test_academic_source_only_still_runs_permission_gate():
    """P1 批次D：教务源码改动除了权限/路由闸门，还必须带上已知的 MySQL 并发回归——
    行锁/唯一约束竞态原来只有每日定时全量才受保护，PR 阶段一路绿灯。"""
    mod = _load()
    targets = mod.select([
        "backend/app/modules/academic_affairs/routers/stats_snapshot_router.py",
    ])
    assert targets == [
        "tests/test_aa_p0_authz.py",
        "tests/test_aa_route_registration_main_compat.py",
        "tests/test_aa_grade_identity_head_concurrency.py",
        "tests/test_aa_grade_recheck_concurrency.py",
        "tests/test_aa_status_change_concurrency.py",
        "tests/test_aa_exam_facade_contract_and_changes.py",
    ]


def test_existing_targets_expands_globs_before_pytest(tmp_path, monkeypatch):
    """canonical workflow 通过 shell array 调 pytest，选择器必须先展开 glob。"""
    mod = _load()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_portal_alpha.py").write_text("", encoding="utf-8")
    (tests_dir / "test_portal_beta.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    targets = mod.existing_targets([
        "tests/test_portal_*.py",
        "tests/test_missing.py",
    ])

    assert targets == [
        "tests/test_portal_alpha.py",
        "tests/test_portal_beta.py",
    ]
    assert all("*" not in target for target in targets)


def test_large_pr_uses_full_regression_with_main_failure_baseline():
    """大 PR 必须跑全量；只豁免 main 已知失败，禁止新增失败。"""
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'push:\n    branches: [ "main" ]' in workflow
    assert "CHANGED_COUNT" in workflow
    assert 'if [ "$CHANGED_COUNT" -ge 150 ]' in workflow
    assert "--junitxml=test-results/backend-full.xml" in workflow
    assert "compare-pytest-junit-baseline.py" in workflow
    assert "backend-known-failures-main.txt" in workflow
    assert '--base-ref "${{ github.event.pull_request.base.sha }}"' in workflow
    assert 'github.event_name }}" = "schedule"' in workflow
    assert "timeout 80m pytest -q" in workflow
    assert "select_pytest_targets.py" in workflow
