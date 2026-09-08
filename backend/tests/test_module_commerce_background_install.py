from __future__ import annotations

import importlib


def test_service_bootstrap_installs_all_reviewed_module_background_writers():
    # Importing the service package is the common bootstrap for web, scheduler and
    # CLI processes. M4 must therefore have installed every reviewed recurring
    # module-owned writer before callers can cache an unfenced function reference.
    import app.services  # noqa: F401

    guard = importlib.import_module("app.services.module_commerce_background_guard")
    assert guard._TARGETS

    seen: set[tuple[str, str]] = set()
    for module_name, function_name, module_key in guard._TARGETS:
        assert (module_name, function_name) not in seen
        seen.add((module_name, function_name))

        module = importlib.import_module(module_name)
        writer = getattr(module, function_name)
        assert getattr(writer, "_module_commerce_background_fenced", False) is True
        assert getattr(writer, "_module_commerce_module_key", None) == module_key

    # Installation is idempotent; a second bootstrap cannot stack wrappers.
    assert guard.install() == 0
