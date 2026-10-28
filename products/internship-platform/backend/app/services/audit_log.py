import logging
from app.core.context import get_request_meta,get_trace_id,current_tenant_id
_log=logging.getLogger("internship.audit")
def record(action,target,detail=None,*,tenant_id=None):
    meta=get_request_meta();_log.info("audit action=%s target=%s tenant=%s trace=%s path=%s detail=%s",
        action,target,tenant_id if tenant_id is not None else current_tenant_id(),get_trace_id(),meta.get("path"),detail or {})
