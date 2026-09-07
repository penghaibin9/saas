"""Service package with installation of approved runtime wrappers."""
from __future__ import annotations

import importlib

_CACHEABLE_MOBILE_MODULES = {"mobile_student_service", "mobile_teacher_service"}
_APPROVAL_RUNTIME_MODULE = "approval_runtime_service"
_ACADEMIC_SERVICE_MODULE = "academic_service"
_PLATFORM_SERVICE_MODULE = "platform_service"


def _install_platform_service_guards():
    """Install commercial order invariants before any caller can import platform_service.

    Python initializes this package before resolving ``app.services.platform_service``.
    Eager installation therefore covers both direct submodule imports and
    ``from app.services import platform_service``; the former bypassed the old lazy
    ``__getattr__`` path and made Actions depend on import order.
    """
    module = importlib.import_module(f"{__name__}.{_PLATFORM_SERVICE_MODULE}")
    from app.services.platform_order_schedule_guard import install as install_order_schedule_guard

    module = install_order_schedule_guard(module)
    globals()[_PLATFORM_SERVICE_MODULE] = module
    return module


def __getattr__(name: str):
    if name == _PLATFORM_SERVICE_MODULE:
        return globals()[_PLATFORM_SERVICE_MODULE]
    if name == _APPROVAL_RUNTIME_MODULE:
        module = importlib.import_module(f"{__name__}.{name}")
        from app.services.approval_production_guard import install as install_approval_guard

        module = install_approval_guard(module)
        globals()[name] = module
        return module
    if name == _ACADEMIC_SERVICE_MODULE:
        module = importlib.import_module(f"{__name__}.{name}")
        from app.services.academic_warning_close_audit_guard import install as install_warning_close_audit_guard

        module = install_warning_close_audit_guard(module)
        globals()[name] = module
        return module
    if name not in _CACHEABLE_MOBILE_MODULES:
        raise AttributeError(name)
    module = importlib.import_module(f"{__name__}.{name}")
    from app.services.mobile_read_cache import install_mobile_read_wrappers

    module = install_mobile_read_wrappers(name, module)
    globals()[name] = module
    return module


_install_platform_service_guards()
