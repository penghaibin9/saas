"""Browser bootstrap must own real purchases, never legacy FEATURES overrides."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlparse

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SEED = BACKEND / "scripts" / "e2e_seed_playwright_tenants.py"
POSITIVE_IDS = (1000000000000000003, 1000000000000000007, 1000000000000000911)


def _safety_guard():
    # Execute the actual guard without importing _mysql_env and mutating pytest's DB configuration.
    tree = ast.parse(SEED.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "assert_safe_target")
    scope = {"os": os, "urlparse": urlparse, "unquote": unquote}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SEED), "exec"), scope)
    return scope["assert_safe_target"]


@pytest.mark.parametrize("change", [
    {"APP_ENV": "production"},
    {"APP_ENV": " production "},
    {"DEPLOYMENT_MODE": "prod"},
    {"E2E_ALLOW_DESTRUCTIVE_TESTS": "false"},
    {"DATABASE_URL": "mysql+pymysql://u:p@db.example.org/e2e_test"},
    {"DATABASE_URL": "mysql+pymysql://u:p@127.0.0.1/customer_data"},
    {"DATABASE_URL": "mysql+pymysql://test_user:test_password@127.0.0.1/customer_data"},
    {"DATABASE_URL": "mysql+pymysql://u:p@127.0.0.1/%70roduction_test"},
    {"DATABASE_URL": "postgresql://u:p@127.0.0.1/e2e_test"},
    {"DATABASE_URL": "mysql+pymysql://u:p@127.0.0.1/staging_test"},
])
def test_seed_rejects_unsafe_targets(change, monkeypatch):
    env = {"APP_ENV": "test", "DEPLOYMENT_MODE": "local", "E2E_ALLOW_DESTRUCTIVE_TESTS": "true",
           "DATABASE_URL": "mysql+pymysql://u:p@127.0.0.1/e2e_test"}
    for key, value in {**env, **change}.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(SystemExit):
        _safety_guard()()


def test_browser_seed_has_no_legacy_feature_writer():
    source = SEED.read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_values = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "FEATURES" not in string_values, "Browser prerequisites must not buy features by legacy KV writes"
    assert "mark-paid" in string_values
    assert "repair-activation" in string_values


def test_browser_seed_activates_real_orders_and_reuses_them_in_fresh_process(db_mode):
    from sqlalchemy import select
    from app.db.session import get_engine, get_sessionmaker
    from app.models import PlatformConfig, PlatformOrder
    from app.services import commercial_entitlement_authority_service as commercial

    url = get_engine().url.render_as_string(hide_password=False)
    # APP_ENV describes testing; DEPLOYMENT_MODE describes the local topology.
    # Keep the real Settings validation active in the child process.
    env = {**os.environ, "APP_ENV": "test", "DEPLOYMENT_MODE": "local", "DB_ENABLED": "true",
           "DATABASE_URL": url, "TEST_DATABASE_URL": url, "E2E_ALLOW_DESTRUCTIVE_TESTS": "true"}

    def run_seed():
        result = subprocess.run([sys.executable, str(SEED)], cwd=BACKEND, env=env,
                                capture_output=True, text=True, timeout=90, check=False)
        assert result.returncode == 0, result.stderr.replace(url, "<test-database>")[-4000:]
        assert "[e2e-seed] ready:" in result.stdout

    def orders():
        with get_sessionmaker()() as db:
            return list(db.execute(select(PlatformOrder.tenant_id, PlatformOrder.order_no, PlatformOrder.status).where(
                PlatformOrder.tenant_id.in_(POSITIVE_IDS), PlatformOrder.is_deleted.is_(False),
            ).order_by(PlatformOrder.tenant_id, PlatformOrder.id)).all())

    run_seed()
    initial_orders = orders()
    assert len(initial_orders) == len(POSITIVE_IDS)
    assert all(row.status == "paid" for row in initial_orders)
    for tid in POSITIVE_IDS:
        state = commercial.commercial_state(tid)
        assert state["verified"] is True
        assert state["authoritySource"] == "PAID_ORDER"
        assert all(state["features"][key] is True for key in ("academicAffairs", "internship", "fileUpload"))
    with get_sessionmaker()() as db:
        assert list(db.scalars(select(PlatformConfig.id).where(
            PlatformConfig.tenant_id.in_(POSITIVE_IDS), PlatformConfig.config_type == "FEATURES",
        )).all()) == []
    run_seed()
    assert orders() == initial_orders, "A successful bootstrap replay must not create duplicate paid orders"


@pytest.mark.parametrize("order_status,expected_action", [("unpaid", "mark-paid"), ("paid", "repair-activation")])
def test_interrupted_bootstrap_resumes_its_order_without_another_purchase(order_status, expected_action, monkeypatch):
    """Control-flow unit test; the separate subprocess case verifies actual MySQL commands."""
    from types import ModuleType, SimpleNamespace
    from unittest.mock import Mock

    order = {"orderNo": "PO-SEED-OWNED", "status": order_status, "version": 2,
             "remark": "Isolated Playwright paid commercial prerequisite",
             "packageCode": "professional", "orderType": "NEW", "amount": 1}
    initial = {"verified": False, "authoritySource": "PAID_ORDER_ACTIVATION_REPAIR_REQUIRED",
               "packageCode": "professional"}
    complete = {"verified": True, "authoritySource": "PAID_ORDER", "commercialOrderNo": order["orderNo"],
                "features": {key: True for key in ("academicAffairs", "internship", "fileUpload")}}
    platform = SimpleNamespace(list_orders=Mock(return_value=[order]), create_order=Mock(),
                               order_action=Mock(return_value={"tenantActivated": True}))
    services = ModuleType("app.services")
    services.platform_service = platform
    services.commercial_entitlement_authority_service = SimpleNamespace(commercial_state=Mock(side_effect=[initial, complete]))
    app = ModuleType("app")
    app.services = services
    monkeypatch.setitem(sys.modules, "app", app)
    monkeypatch.setitem(sys.modules, "app.services", services)
    tree = ast.parse(SEED.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "ensure_commercial_entitlement")
    scope = {"assert_safe_target": lambda: None, "TENANTS": [{"id": POSITIVE_IDS[0]}]}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SEED), "exec"), scope)
    assert scope["ensure_commercial_entitlement"](POSITIVE_IDS[0]) == order["orderNo"]
    platform.create_order.assert_not_called()
    assert platform.order_action.call_args.args == (order["orderNo"], expected_action)
    assert platform.order_action.call_args.kwargs["expected_version"] == 2
