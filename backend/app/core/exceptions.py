"""
业务异常 + 全局异常处理器
────────────────────────────────────────────────────────────
统一错误码取自 docs/05-数据接口权限与安全/api/00-API契约冻结总册 §三。所有异常最终都转成
统一失败响应体（见 core/response.fail），绝不返回裸 500 或空白。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.core.response import fail

# 业务码 → 默认 HTTP 状态（冻结契约 §三）
CODE_HTTP = {
    "SUCCESS": 200,
    "VALIDATION_ERROR": 400,
    "REJECT_REASON_REQUIRED": 400,
    "FILE_TYPE_NOT_ALLOWED": 400,
    "LOCATION_PERMISSION_REQUIRED": 400,
    "UNAUTHORIZED": 401,
    "WECHAT_AUTH_REQUIRED": 401,
    "NO_PERMISSION": 403,
    "NO_DATA_SCOPE": 403,
    "MODULE_NOT_AUTHORIZED": 403,
    "MODULE_EXPIRED_READONLY": 403,
    "TENANT_NOT_FOUND": 404,
    "ROLE_NOT_FOUND": 404,
    "DATA_NOT_FOUND": 404,
    "DATA_CONFLICT": 409,
    "APPROVAL_VERSION_CONFLICT": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "FILE_TOO_LARGE": 413,
    "RATE_LIMITED": 429,
    "UPLOAD_FAILED": 500,
    "SERVER_ERROR": 500,
}


class AppException(Exception):
    """业务异常：service/api 层抛出，由全局处理器转统一失败响应。"""

    def __init__(self, code: str, message: str, details=None, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.http_status = http_status or CODE_HTTP.get(code, 400)


# 常用快捷构造
def unauthorized(msg: str = "未登录或令牌失效"):
    return AppException("UNAUTHORIZED", msg)


def no_permission(msg: str = "无权限访问当前数据", details=None):
    return AppException("NO_PERMISSION", msg, details)


def not_found(msg: str = "资源不存在"):
    return AppException("DATA_NOT_FOUND", msg)


def tenant_not_found(msg: str = "租户不存在或已停用"):
    return AppException("TENANT_NOT_FOUND", msg)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _app_exc(request: Request, exc: AppException):
        if exc.code in ("NO_PERMISSION", "NO_DATA_SCOPE", "RATE_LIMITED"):
            try:  # 越权/限流写审计，失败不影响响应
                from app.services import audit_log
                audit_log.record("PERMISSION_DENIED" if exc.code != "RATE_LIMITED" else "RATE_LIMITED",
                                 request.url.path, detail={"message": exc.message})
            except Exception:  # noqa: BLE001
                pass
        return JSONResponse(
            status_code=exc.http_status,
            content=fail(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(x) for x in e.get("loc", [])[1:]) or "body", "msg": e.get("msg")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", "参数校验失败", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_: Request, exc: StarletteHTTPException):
        mapping = {401: "UNAUTHORIZED", 403: "NO_PERMISSION", 404: "DATA_NOT_FOUND",
                   409: "DATA_CONFLICT", 429: "RATE_LIMITED"}
        code = mapping.get(exc.status_code, "SERVER_ERROR" if exc.status_code >= 500 else "VALIDATION_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(code, str(exc.detail) if exc.detail else code),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exc(_: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=fail("SERVER_ERROR", "服务异常，请稍后重试或联系管理员"),
        )
