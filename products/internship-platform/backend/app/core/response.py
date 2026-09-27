from __future__ import annotations
from datetime import datetime,timedelta,timezone
from app.core.config import settings
from app.core.context import get_trace_id

def _now_iso():
    return datetime.now(timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))).isoformat(timespec="seconds")
def success(data=None,message="success",code="SUCCESS"):
    return {"code":0,"bizCode":code,"message":message,"data":data if data is not None else {},"traceId":get_trace_id(),"timestamp":_now_iso()}
def fail(code,message,details=None):
    body={"code":1,"bizCode":code,"message":message,"data":None,"traceId":get_trace_id(),"timestamp":_now_iso()}
    if details is not None: body["details"]=details
    return body
def paginate(items,total,page=1,page_size=20,next_cursor=None,**extra):
    data={"items":items,"page":page,"pageSize":page_size,"total":total,"nextCursor":next_cursor}
    data.update({k:v for k,v in extra.items() if v is not None})
    return data
