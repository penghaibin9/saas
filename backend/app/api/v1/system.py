"""Compatibility facade for the school System Administration control plane.

Canonical owner: ``app.modules.system_admin.routers.system_bundle``.
S0 Move Only deliberately keeps every public and private attribute reachable so
legacy imports and route registration preserve behavior while ownership moves.
"""
from app.modules.system_admin.routers import system_bundle as _bundle
from app.modules.system_admin.routers.system_bundle import *  # noqa: F401,F403

router = _bundle.router


def __getattr__(name: str):
    return getattr(_bundle, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_bundle)))
