"""Service package with lazy installation of approved mobile read-cache wrappers."""
from __future__ import annotations

import importlib

_CACHEABLE_MOBILE_MODULES = {"mobile_student_service", "mobile_teacher_service"}


def __getattr__(name: str):
    if name not in _CACHEABLE_MOBILE_MODULES:
        raise AttributeError(name)
    module = importlib.import_module(f"{__name__}.{name}")
    from app.services.mobile_read_cache import install_mobile_read_wrappers

    module = install_mobile_read_wrappers(name, module)
    globals()[name] = module
    return module
