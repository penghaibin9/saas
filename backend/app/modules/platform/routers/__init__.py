"""Platform Operations routers."""
from . import platform_router as _platform_router
from . import platform_code_first_hardening as _code_first_hardening
from . import platform_cross_authority_hardening as _cross_authority_hardening

# W1-W4 exact replacements are installed in-place so the S0 compatibility
# invariant remains true: app.api.v1.platform.router is platform_router.router.
_code_first_hardening.install_into_platform_router(_platform_router.router)
# Reverse audit after W0-W7 found two cross-plane authority leaks: legacy
# FEATURES still influenced runtime gates, and platform BRAND competed with the
# school's canonical TenantBrandConfig. Install these final replacements last.
_cross_authority_hardening.install_into_platform_router(_platform_router.router)
# Commerce is additive, not a second router authority. Install before the real
# route_registration owner copies this graph; the legacy facade aliases it too.
from . import module_commerce_router as _module_commerce
_module_commerce.install_into_platform_router(_platform_router.router)
# M8 finance is intentionally isolated from the frozen M1-M5 24-route contract.
# It is still installed on the same canonical platform router so PAM, identity and
# audit boundaries are shared; no finance route may replace a prior handler.
from . import module_commerce_finance_router as _module_commerce_finance
_module_commerce_finance.install_into_platform_router(_platform_router.router)
# M8 after-sales/SLA/cost governance is isolated again so customer-success bridge
# changes cannot silently expand either frozen commerce or finance contracts.
from . import module_commerce_operations_router as _module_commerce_operations
_module_commerce_operations.install_into_platform_router(_platform_router.router)
router = _platform_router.router

__all__ = ["router"]
