"""Compatibility facade for the school System Administration control plane.

Frozen implementation: ``app.modules.system_admin.routers.system_bundle``.
B0-B7 adapters: ``system_router``.
I1/I2 legacy-import adapters: ``system_control_plane_router``.
I4 page-bounded scale projections: ``system_i4_router``.
Route registration remains untouched until S0-06 after E-A01 releases writer.
"""
from app.modules.system_admin.routers import system_bundle as _bundle
from app.modules.system_admin.routers import system_control_plane_router as _control
from app.modules.system_admin.routers import system_i4_router as _i4
from app.modules.system_admin.routers import system_router as _router
from app.modules.system_admin.routers.system_bundle import *  # noqa: F401,F403

router = _i4.router
get_system_context = _router.get_system_context
get_system_user = _router.get_system_user
assign_system_user_roles = _router.assign_system_user_roles
create_system_role = _router.create_system_role
copy_system_role = _router.copy_system_role
save_system_role_permissions = _router.save_system_role_permissions
get_system_role = _i4.role_detail
export_role_config = _router.export_role_config


def __getattr__(name: str):
    for module in (_i4, _control, _router, _bundle):
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(name)


def __dir__():
    return sorted(set(globals()) | set(dir(_bundle)) | set(dir(_router)) | set(dir(_control)) | set(dir(_i4)))
