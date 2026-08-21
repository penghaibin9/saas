"""Install machine-only DR health authority without rewriting PLAT-12 history APIs."""
from __future__ import annotations

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import disaster_recovery_service as legacy
    from app.services.machine_recovery_evidence_service import governance_overview_with_machine

    original_overview = legacy.governance_overview

    def governance_overview() -> dict:
        return governance_overview_with_machine(original_overview())

    legacy.governance_overview = governance_overview
    _INSTALLED = True
