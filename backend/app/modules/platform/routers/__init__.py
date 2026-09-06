"""Platform Operations routers."""
from . import platform_router as _platform_router
from . import platform_code_first_hardening as _code_first_hardening

# W1-W4 exact replacements are installed in-place so the S0 compatibility
# invariant remains true: app.api.v1.platform.router is platform_router.router.
_code_first_hardening.install_into_platform_router(_platform_router.router)
router = _platform_router.router

__all__ = ["router"]
