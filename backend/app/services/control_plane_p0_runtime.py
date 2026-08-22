"""Canonical startup authority for the control-plane P0 cutovers.

Keep the application router coupled to one control-plane startup boundary while
preserving the independently testable auth, DR and tenant-offboarding
implementation guards.  This avoids growing the global runtime patch graph with
three separate router-level installers.
"""
from __future__ import annotations

_INSTALLED = False


def install() -> None:
    """Install all control-plane P0 authorities exactly once per process."""
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services.control_plane_p0_auth_guard import install as install_auth
    from app.services.control_plane_p0_dr_guard import install as install_dr
    from app.services.control_plane_p0_offboarding_guard import install as install_offboarding

    # Order matters: authentication authority is established first, DR health
    # overlay second, then the destructive offboarding retry semantics.  Each
    # component is independently idempotent, so a partial startup failure can be
    # retried safely without double-wrapping an already-installed authority.
    install_auth()
    install_dr()
    install_offboarding()
    _INSTALLED = True
