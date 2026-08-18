"""Compatibility facade for the Platform Operations control plane.

Frozen implementation: ``app.modules.platform.routers.platform_bundle``.
Canonical runtime adapters: ``app.modules.platform.routers.platform_router``.
"""
from app.modules.platform.routers import platform_bundle as _bundle
from app.modules.platform.routers import platform_router as _router
from app.modules.platform.routers.platform_bundle import *  # noqa: F401,F403

router = _router.router
platform_context = _router.platform_context


def __getattr__(name: str):
    if hasattr(_router, name):
        return getattr(_router, name)
    return getattr(_bundle, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_bundle)) | set(dir(_router)))
