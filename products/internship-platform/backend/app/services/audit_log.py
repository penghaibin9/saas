import logging
from app.core.context import get_request_meta,get_trace_id
_log=logging.getLogger("internship.audit")
def record(action,target,detail=None):
    meta=get_request_meta();_log.info("audit action=%s target=%s trace=%s path=%s detail=%s",action,target,get_trace_id(),meta.get("path"),detail or {})
