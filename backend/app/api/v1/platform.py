"""Compatibility facade for the Platform Operations control plane.

Frozen implementation: ``app.modules.platform.routers.platform_bundle``.
Canonical runtime adapters: ``app.modules.platform.routers.platform_router``.
Module-commerce extensions are composed separately so the frozen bundle and its
adapter owner do not need to be rewritten for M1/M2.
"""
from fastapi import APIRouter

from app.modules.platform.routers import module_commerce_router as _commerce
from app.modules.platform.routers import platform_bundle as _bundle
from app.modules.platform.routers import platform_router as _router
from app.modules.platform.routers.platform_bundle import *  # noqa: F401,F403

router = APIRouter()
router.include_router(_router.router)
router.include_router(_commerce.router)
platform_context = _router.platform_context


def __getattr__(name: str):
    if hasattr(_router, name):
        return getattr(_router, name)
    if hasattr(_commerce, name):
        return getattr(_commerce, name)
    return getattr(_bundle, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_bundle)) | set(dir(_router)) | set(dir(_commerce)))
