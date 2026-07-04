"""
统一响应结构 —— 双码兼容（BACKEND-OVERNIGHT 阶段4 拍板）：
- `code`    数字业务码：0 成功；400001 参数错误；401001 未登录；403001 无权限；
            403002 数据范围越权；404001 不存在；409001 冲突；422001 校验失败；500001 系统异常。
            与 frontend（res.code === 0）及本任务规范对齐。
- `bizCode` 冻结契约字符串码（SUCCESS / NO_PERMISSION / ...），保持与
            docs/api/00-API契约冻结总册 §二/§三 兼容，不破坏既有契约。

成功：{ "code":"SUCCESS", "message":"success", "data":{...}, "traceId":"req-...", "timestamp":"...+08:00" }
失败：{ "code":"NO_PERMISSION", "message":"...", "data":null, "details":{...}, "traceId":"...", "timestamp":"..." }

注意：`code` 为「业务字符串码」（SUCCESS / NO_PERMISSION / VALIDATION_ERROR ...），
HTTP 状态码另作传输层语义。前后端、PC、小程序 mock 必须与此结构 100% 一致，
故此处严格采用冻结契约，而非数字码。traceId = 请求链路 ID（= 审计表 request_id）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.context import get_trace_id


def _now_iso() -> str:
    tz = timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))
    return datetime.now(tz).isoformat(timespec="seconds")


# 字符串契约码 → 数字码映射（未列出的失败码回落 500001）
BIZ_TO_NUM = {
    "SUCCESS": 0,
    "VALIDATION_ERROR": 422001,
    "BAD_REQUEST": 400001,
    "REJECT_REASON_REQUIRED": 400001,
    "FILE_TYPE_NOT_ALLOWED": 400001,
    "LOCATION_PERMISSION_REQUIRED": 400001,
    "UNAUTHORIZED": 401001,
    "WECHAT_AUTH_REQUIRED": 401001,
    "NO_PERMISSION": 403001,
    "NO_DATA_SCOPE": 403002,
    "MODULE_NOT_AUTHORIZED": 403001,
    "MODULE_EXPIRED_READONLY": 403001,
    "TENANT_NOT_FOUND": 404001,
    "ROLE_NOT_FOUND": 404001,
    "DATA_NOT_FOUND": 404001,
    "DATA_CONFLICT": 409001,
    "APPROVAL_VERSION_CONFLICT": 409001,
    "IDEMPOTENCY_CONFLICT": 409001,
    "FILE_TOO_LARGE": 400001,
    "RATE_LIMITED": 429001,
    "UPLOAD_FAILED": 500001,
    "SERVER_ERROR": 500001,
}


def success(data: Any = None, message: str = "success", code: str = "SUCCESS") -> dict:
    """构造统一成功响应体（code=0，bizCode=SUCCESS）。"""
    return {
        "code": BIZ_TO_NUM.get(code, 0),
        "bizCode": code,
        "message": message,
        "data": data if data is not None else {},
        "traceId": get_trace_id(),
        "timestamp": _now_iso(),
    }


def fail(code: str, message: str, details: Any = None) -> dict:
    """构造统一失败响应体（code=数字码，bizCode=字符串契约码；HTTP 状态另行设置）。"""
    body = {
        "code": BIZ_TO_NUM.get(code, 500001),
        "bizCode": code,
        "message": message,
        "data": None,
        "traceId": get_trace_id(),
        "timestamp": _now_iso(),
    }
    if details is not None:
        body["details"] = details
    return body


def paginate(items: list, total: int, page: int = 1, page_size: int = 20,
             next_cursor: str | None = None) -> dict:
    """分页数据结构（放入 data），对齐冻结契约 §四。"""
    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "total": total,
        "nextCursor": next_cursor,
    }
