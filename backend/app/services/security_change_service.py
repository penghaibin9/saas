"""Compatibility facade for canonical System Admin SecurityChange service."""
from app.modules.system_admin.services import security_change_service as _canonical
from app.modules.system_admin.services.security_change_service import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_canonical)))
