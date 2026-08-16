"""Request context compatibility facade with the Control Plane platform outer gate.

The pre-B0 middleware implementation is preserved byte-for-byte in
``context_legacy``.  This wrapper inserts one fail-closed identity-plane check
immediately before any route handler executes.
"""
from __future__ import annotations

from starlette.responses import JSONResponse

from app.middleware import context_legacy as _legacy
from app.middleware.context_legacy import *  # noqa: F401,F403


class RequestContextMiddleware(_legacy.RequestContextMiddleware):
    async def dispatch(self, request, call_next):
        async def _platform_gated_call_next(req):
            path = req.url.path
            is_platform_path = path == "/api/v1/platform" or path.startswith("/api/v1/platform/")
            if is_platform_path:
                from app.core.context import get_current_user_ctx
                from app.core.platform_principal import is_platform_principal
                from app.core.response import fail

                actor = get_current_user_ctx()
                # Authentication owns the unauthenticated boundary.  When there is no
                # resolved actor yet, continue into the route dependency so missing or
                # invalid Bearer credentials retain the canonical 401 semantics.  This
                # outer gate only rejects an already-authenticated school-plane actor.
                if actor and not is_platform_principal(actor):
                    try:
                        from app.services import audit_log
                        audit_log.record(
                            "PERMISSION_DENIED",
                            f"platform-plane:{path}",
                            detail={
                                "path": path,
                                "method": req.method,
                                "role": actor.get("currentRoleCode"),
                                "userType": actor.get("userType"),
                                "reason": "PLATFORM_PRINCIPAL_REQUIRED",
                            },
                            result="DENIED",
                        )
                    except Exception:  # deny is authoritative even if best-effort deny-audit fails
                        pass
                    return JSONResponse(
                        status_code=403,
                        content=fail("NO_PERMISSION", "学校身份禁止访问平台控制面"),
                    )
            return await call_next(req)

        return await super().dispatch(request, _platform_gated_call_next)


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))
