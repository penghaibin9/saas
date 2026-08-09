"""Service package with lazy installation of approved runtime wrappers."""
from __future__ import annotations

import importlib

_CACHEABLE_MOBILE_MODULES = {"mobile_student_service", "mobile_teacher_service"}
_APPROVAL_RUNTIME_MODULE = "approval_runtime_service"


def __getattr__(name: str):
    if name == _APPROVAL_RUNTIME_MODULE:
        module = importlib.import_module(f"{__name__}.{name}")
        from app.services.approval_production_guard import install as install_approval_guard

        module = install_approval_guard(module)
        globals()[name] = module
        return module
    if name not in _CACHEABLE_MOBILE_MODULES:
        raise AttributeError(name)
    module = importlib.import_module(f"{__name__}.{name}")
    from app.services.mobile_read_cache import install_mobile_read_wrappers

    module = install_mobile_read_wrappers(name, module)
    globals()[name] = module
    return module
