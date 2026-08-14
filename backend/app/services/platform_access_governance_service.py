"""Compatibility facade for replay-safe canonical Platform Workforce / PAM service."""
from app.modules.platform.services import platform_access_governance_runtime as _canonical
from app.modules.platform.services.platform_access_governance_runtime import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_canonical)))
