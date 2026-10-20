from __future__ import annotations
import hashlib,mimetypes,uuid
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException,not_found
from app.models.file import FileBinding,FileObject
from app.services.db_service import _tid,session
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

_READY_STATUS={"AVAILABLE","STORED"}
_READY_SCAN={"CLEAN","NOT_REQUIRED"}

def _safe_name(filename):
    name=Path(str(filename or "file.bin")).name.strip()
    if not name or name in {".",".."}: raise AppException("VALIDATION_ERROR","文件名无效")
    return name

def _meta(row):
    return {"fileId":str(row.id),"fileName":row.file_name,"ext":row.ext or "","mimeType":row.mime_type or "",
            "sizeBytes":int(row.size_bytes or 0),"sha256":row.sha256 or "","fileKey":row.file_key,
            "bizType":row.biz_type or "","bizId":row.biz_id or "","status":row.status,
            "scanStatus":row.scan_status,"readyForBusiness":str(row.status).upper() in _READY_STATUS and str(row.scan_status or "NOT_REQUIRED").upper() in _READY_SCAN}

def _row(file_id,db):
    if not str(file_id or "").isdigit(): return None
    return db.scalar(select(FileObject).where(FileObject.id==int(file_id),FileObject.tenant_id==_tid(),FileObject.is_deleted.is_(False)))

def get_file_meta(file_id,user=None,*,require_ready=True):
    with session() as db:
        row=_row(file_id,db)
        if not row:return None
        meta=_meta(row)
        if require_ready and not meta["readyForBusiness"]:
            raise AppException("FILE_NOT_READY","文件尚未安全就绪",http_status=409)
        return meta

def attachment_view(file_id):
    if not file_id:return None
    meta=get_file_meta(file_id)
    if not meta:return None
    return {"fileId":meta["fileId"],"fileName":meta["fileName"],"ext":meta["ext"],"mimeType":meta["mimeType"],"sizeBytes":meta["sizeBytes"],"canPreview":True,"canDownload":True}

def store_bytes(data,filename,biz_type="ATTACHMENT",mime_type=None,*,biz_id=None,user=None,visibility="PRIVATE",security_level="NORMAL",db=None):
    if not isinstance(data,(bytes,bytearray)): raise AppException("VALIDATION_ERROR","文件内容必须为 bytes")
    filename=_safe_name(filename)
    ext=Path(filename).suffix.lower().lstrip(".")
    key=f"{_tid()}/{datetime.utcnow():%Y%m%d}/{uuid.uuid4().hex}{('.'+ext) if ext else ''}"
    backend=get_backend();tmp=backend.staging_path(key);tmp.write_bytes(bytes(data));backend.persist(key,tmp)
    digest=hashlib.sha256(bytes(data)).hexdigest();mime=mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    actor=user or get_current_user_ctx() or {};uid=resolve_message_user_id(actor) or None
    owns=db is None;working=db or session()
    try:
        row=FileObject(tenant_id=_tid(),file_key=key,file_name=filename,ext=ext or None,mime_type=mime,size_bytes=len(data),
            sha256=digest,biz_type=biz_type,biz_id=str(biz_id) if biz_id is not None else None,owner_user_id=uid,
            visibility=visibility or "PRIVATE",security_level=security_level or "NORMAL",status="AVAILABLE",
            storage_backend="local",storage_zone="ACTIVE",upload_source="SYSTEM",scan_required=False,
            scan_status="NOT_REQUIRED",available_at=datetime.utcnow())
        working.add(row);working.flush()
        if biz_id is not None:
            _bind_in_session(working,row,biz_type,str(biz_id),actor)
        if owns:working.commit();working.refresh(row)
        return _meta(row)
    except Exception:
        if owns:working.rollback()
        raise
    finally:
        if owns:working.close()

def _bind_in_session(db,row,biz_type,biz_id,actor):
    existing=db.scalar(select(FileBinding).where(FileBinding.tenant_id==_tid(),FileBinding.file_id==row.id,
        FileBinding.biz_type==str(biz_type).upper(),FileBinding.biz_id==str(biz_id),FileBinding.is_deleted.is_(False)))
    if not existing:
        db.add(FileBinding(tenant_id=_tid(),file_id=row.id,biz_type=str(biz_type).upper(),biz_id=str(biz_id),
            relation_type="ATTACHMENT",subject_type="BUSINESS_OBJECT",subject_id=str(biz_id),version_no=1,
            is_current=True,status="ACTIVE",module_code="INTERNSHIP"))
    row.biz_type=str(biz_type).upper();row.biz_id=str(biz_id);row.visibility="BIZ_SCOPED"

def bind_file_biz(file_id,biz_type,biz_id,user=None,db=None):
    owns=db is None;working=db or session()
    try:
        row=_row(file_id,working)
        if not row:raise not_found("文件不存在")
        if not _meta(row)["readyForBusiness"]:raise AppException("FILE_NOT_READY","文件尚未安全就绪",http_status=409)
        _bind_in_session(working,row,biz_type,biz_id,user or get_current_user_ctx() or {})
        if owns:working.commit()
        else:working.flush()
    except Exception:
        if owns:working.rollback()
        raise
    finally:
        if owns:working.close()

def resolve_download(file_id,*,allow_graduation_material=False,user=None):
    with session() as db:
        row=_row(file_id,db)
        if not row or not _meta(row)["readyForBusiness"]:return None
        path=get_backend().fetch_local(row.file_key)
        return (path,row.file_name or path.name) if path and path.exists() else None
