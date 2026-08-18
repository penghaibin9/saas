"""Compatibility facade for hardened canonical Platform Workforce / PAM service."""
from app.modules.platform.services import platform_access_governance_hardening as _hardened
from app.modules.platform.services.platform_access_governance_hardening import *  # noqa: F401,F403

# Public calls stay on the hardening facade. This private authority hook must
# point at the runtime module because the re-exported runtime functions close
# over that module's globals (for example _validate_support_ticket/_existing).
# Keeping the hook aligned with the real closure preserves deterministic
# authority substitution in production contracts without bypassing hardening.
_canonical = _hardened._runtime


def __getattr__(name: str):
    return getattr(_hardened, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_hardened)) | set(dir(_canonical)))
