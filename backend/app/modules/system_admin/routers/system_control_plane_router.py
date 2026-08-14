"""System Control Plane composition after B7 + I1/I2.

This wrapper replaces only deprecated identity-import routes with canonical
Data Exchange adapters. All pre-existing System/B0-B7 routes are reused.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.system_admin.routers import identity_import_compat_router as _identity
from app.modules.system_admin.routers import system_router as _base


def _key(route) -> tuple[str, str]:
    methods = tuple(sorted(getattr(route, "methods", set()) or set()))
    return (",".join(methods), getattr(route, "path", ""))


def _compose() -> APIRouter:
    replacement = {_key(route): route for route in _identity.router.routes}
    composed = APIRouter()
    routes = []
    for route in _base.router.routes:
        routes.append(replacement.pop(_key(route), route))
    if replacement:
        unexpected = sorted(replacement)
        raise RuntimeError(f"Identity Import compatibility route has no legacy target: {unexpected}")
    composed.routes = routes
    return composed


router = _compose()


def __getattr__(name: str):
    return getattr(_base, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_base)))
