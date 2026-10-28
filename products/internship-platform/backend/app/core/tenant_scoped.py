from __future__ import annotations
from sqlalchemy import select
def has_tenant_column(model): return hasattr(model,"tenant_id")
def current_tenant_id_int():
    from app.services.db_service import current_tenant_id
    from app.core.exceptions import AppException
    value=current_tenant_id()
    if not value: raise AppException("TENANT_CONTEXT_REQUIRED","缺少租户上下文",http_status=403)
    return int(value)
def tenant_select(model,tenant_id=None):
    stmt=select(model)
    return stmt if not has_tenant_column(model) else stmt.where(model.tenant_id==(tenant_id or current_tenant_id_int()))
def tenant_get(db,model,pk,tenant_id=None,allow_cross_tenant=False):
    if pk is None:return None
    row=db.get(model,pk)
    if row is None or allow_cross_tenant or not has_tenant_column(model):return row
    return row if int(getattr(row,"tenant_id",0) or 0)==int(tenant_id or current_tenant_id_int()) else None
