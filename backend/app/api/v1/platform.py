"""Compatibility facade for the Platform Operations control plane.

Canonical owner: ``app.modules.platform.routers.platform_bundle``.
S0 Move Only deliberately keeps every public and private attribute reachable so
legacy imports and route registration preserve behavior while ownership moves.
"""
from app.modules.platform.routers import platform_bundle as _bundle
from app.modules.platform.routers.platform_bundle import *  # noqa: F401,F403

router = _bundle.router


def __getattr__(name: str):
    return getattr(_bundle, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_bundle)))
