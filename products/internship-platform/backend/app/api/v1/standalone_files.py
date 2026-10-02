"""Authenticated local evidence transport; no public object keys or implicit binding."""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from app.core.security import get_current_user
from app.core.response import success
from app.core.exceptions import AppException, not_found
from app.services import internship_file_transfer_service as transfer
from app.services.storage import get_backend
from app.services.db_service import session
from app.modules.internship.services.internship_audit_service import add_audit

router=APIRouter(prefix='/files',tags=['Standalone evidence files'])

@router.post('')
def upload(file: UploadFile=File(...),bizType: str=Query('ATTACHMENT',max_length=80),
           bizId: str|None=Query(None,max_length=64),user=Depends(get_current_user)):
    # A supplied purpose/id never grants file access or binds a business record.
    try:
        data=file.file.read(transfer.MAX_UPLOAD_BYTES+1)
        return success(transfer.store_upload(data,file.filename,file.content_type,bizType,user))
    finally:
        file.file.close()


def response_file(file_id,user,inline):
    row,meta=transfer.authorized_file(file_id,user,'preview' if inline else 'download')
    path=get_backend().fetch_local(row.file_key)
    if path is None or not path.is_file(): raise not_found('文件字节不存在')
    from hashlib import sha256
    digest = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if path.stat().st_size != row.size_bytes or digest.hexdigest() != row.sha256:
        raise AppException('FILE_INTEGRITY_ERROR','附件完整性校验失败，请联系学校管理员',http_status=409)
    with session() as db:
        add_audit(db,target_type='FILE',target_id=row.id,action='FILE_PREVIEW' if inline else 'FILE_DOWNLOAD',
                  user=user,detail={'fileId':str(row.id),'sha256':row.sha256})
        db.commit()
    safe_inline=inline and row.mime_type in {'application/pdf','image/png','image/jpeg','image/gif','video/mp4','video/webm'}
    return FileResponse(path,filename=row.file_name,media_type=row.mime_type,
        content_disposition_type='inline' if safe_inline else 'attachment',
        headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
                 'Content-Security-Policy':"sandbox; default-src 'none'; media-src 'self'; img-src 'self'"})

@router.get('/download/{file_id}')
def download(file_id: str,user=Depends(get_current_user)):
    return response_file(file_id,user,False)

@router.get('/preview/{file_id}')
def preview(file_id: str,user=Depends(get_current_user)):
    return response_file(file_id,user,True)

@router.get('/{file_id}/url')
def url(file_id: str,user=Depends(get_current_user)):
    row,_=transfer.authorized_file(file_id,user,'preview')
    return success({'delivery':'LOCAL_PROXY','requiresAuth':True,'url':f'/api/v1/files/preview/{row.id}'})

@router.get('/{file_id}')
def metadata(file_id: str,user=Depends(get_current_user)):
    _,meta=transfer.authorized_file(file_id,user,'meta')
    return success(meta)
