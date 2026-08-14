"""Compatibility facade for the school System Administration control plane.

Canonical implementation bundle: ``app.modules.system_admin.routers.system_bundle``.
Runtime Control Plane adapters: ``app.modules.system_admin.routers.system_router``.
Route registration remains untouched until S0-06 after E-A01 releases the shared writer.
"""
from app.modules.system_admin.routers import system_bundle as _bundle
from app.modules.system_admin.routers import system_router as _router
from app.modules.system_admin.routers.system_bundle import *  # noqa: F401,F403

router = _router.router
get_system_context = _router.get_system_context
copy_system_role = _router.copy_system_role
save_system_role_permissions = _router.save_system_role_permissions


def __getattr__(name: str):
    if hasattr(_router, name):
        return getattr(_router, name)
    return getattr(_bundle, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_bundle)) | set(dir(_router)))
