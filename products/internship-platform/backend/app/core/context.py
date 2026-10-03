from __future__ import annotations
from contextvars import ContextVar

_trace_id=ContextVar("trace_id",default="-")
_tenant=ContextVar("tenant",default=None)
_user=ContextVar("current_user",default=None)
_request_meta=ContextVar("request_meta",default=None)
_internship_batch_id=ContextVar("internship_batch_id",default=None)

def set_trace_id(value): _trace_id.set(str(value))
def get_trace_id(): return _trace_id.get()
def set_tenant(value):
    if value is None: _tenant.set(None)
    elif isinstance(value,dict): _tenant.set(value)
    else: _tenant.set({"tenantId":str(value)})
def get_tenant(): return _tenant.get()
def current_tenant_id():
    value=_tenant.get()
    return value.get("tenantId") if value else None
def set_current_user(value): _user.set(value)
def get_current_user_ctx(): return _user.get()
def set_request_meta(value): _request_meta.set(value)
def get_request_meta(): return _request_meta.get() or {}
def set_current_internship_batch_id(value): _internship_batch_id.set(str(value) if value else None)
def get_current_internship_batch_id(): return _internship_batch_id.get()
