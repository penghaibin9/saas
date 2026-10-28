from __future__ import annotations
class AppException(Exception):
    def __init__(self,code,message,details=None,http_status=None,decision_trace=None):
        super().__init__(message);self.code=code;self.message=message;self.details=details
        self.http_status=http_status or 400;self.decision_trace=decision_trace
def unauthorized(msg="未登录或令牌失效"): return AppException("UNAUTHORIZED",msg,http_status=401)
def no_permission(msg="无权限访问当前数据",details=None): return AppException("NO_PERMISSION",msg,details,http_status=403)
def no_data_scope(msg="当前账号无可用数据范围",details=None): return AppException("NO_DATA_SCOPE",msg,details,http_status=403)
def not_found(msg="资源不存在"): return AppException("DATA_NOT_FOUND",msg,http_status=404)
def tenant_not_found(msg="租户不存在或已停用"): return AppException("TENANT_NOT_FOUND",msg,http_status=404)
def check_version(current_version,expected_version):
    if expected_version is None or int(expected_version)!=int(current_version or 0):
        raise AppException("APPROVAL_VERSION_CONFLICT","数据已被他人修改，请刷新后重试",http_status=409)
def register_exception_handlers(app):
    from starlette.responses import JSONResponse
    from app.core.response import fail
    @app.exception_handler(AppException)
    async def _handler(_request,exc):
        return JSONResponse(status_code=exc.http_status,content=fail(exc.code,exc.message,exc.details))
