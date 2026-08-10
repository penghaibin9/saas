"""请求 traceId 兼容入口。

A1 审批服务只需要读取已有请求上下文的 traceId；真实实现仍位于 app.core.context，
这里不创建第二套 ContextVar，避免审计/响应出现两个 traceId 事实源。
"""
from app.core.context import get_trace_id

__all__ = ["get_trace_id"]
