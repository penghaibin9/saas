from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_background_guard_uses_explicit_process_bootstrap_not_service_package_side_effect():
    services_init = (ROOT / "app" / "services" / "__init__.py").read_text(encoding="utf-8")
    middleware_source = (ROOT / "app" / "middleware" / "context.py").read_text(encoding="utf-8")
    scheduler_source = (ROOT / "scripts" / "run_scheduled_jobs.py").read_text(encoding="utf-8")

    # Broad service-package imports are used from SQLAlchemy listeners and many
    # business modules. They must not eagerly import the whole recurring-writer
    # graph while the package is still partially initialized.
    assert "_install_module_commerce_background_guard()" not in services_init
    assert "module_commerce_background_guard import install" not in services_init

    # The two real process entrypoints install the same fail-closed guard before
    # they can serve HTTP or execute the scheduler's first recurring write.
    assert "module_commerce_background_guard import install as _install_module_background_guards" in middleware_source
    assert "_install_module_background_guards()" in middleware_source
    assert "module_commerce_background_guard import install as _install_module_background_guards" in scheduler_source
    assert scheduler_source.index("_install_module_background_guards()") < scheduler_source.index("if not db_enabled()")


def test_explicit_background_guard_install_is_complete_and_idempotent():
    # Importing the guard submodule first lets ``app.services`` finish its normal
    # package bootstrap. Only then do we deliberately import/wrap reviewed writers.
    guard = importlib.import_module("app.services.module_commerce_background_guard")
    guard.install()
    assert guard._TARGETS

    seen: set[tuple[str, str]] = set()
    for module_name, function_name, module_key in guard._TARGETS:
        assert (module_name, function_name) not in seen
        seen.add((module_name, function_name))

        module = importlib.import_module(module_name)
        writer = getattr(module, function_name)
        assert getattr(writer, "_module_commerce_background_fenced", False) is True
        assert getattr(writer, "_module_commerce_module_key", None) == module_key

    # Installation is idempotent; repeated Web/scheduler bootstrap cannot stack
    # wrappers or widen authorization semantics.
    assert guard.install() == 0
