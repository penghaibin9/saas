"""Standalone authenticated upload/read boundary for internship evidence files.
User uploads remain private until a canonical business transaction binds them.
"""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.models.file import FileObject, FileBinding
from app.services import file_access_service as access, file_content_security as security
from app.services.db_service import _tid, session
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset({'png','jpg','jpeg','gif','pdf','doc','docx','xls','xlsx','txt','csv','zip','rar','mp4','webm'})
UPLOAD_PURPOSES = frozenset({'ATTACHMENT','INTERNSHIP','INTERNSHIP_REPORT','INTERNSHIP_WEEKLY_REPORT',
    'INTERNSHIP_INSURANCE_POLICY','INTERNSHIP_INSURANCE','INTERNSHIP_PLAN_TASK',
    'INTERNSHIP_APPLICATION_EVIDENCE','INTERNSHIP_STUDENT_EVAL','INTERNSHIP_LEAVE'})


def actor_for_files(db, user):
    actor = dict(user or {})
    if not resolve_message_user_id(actor):
        raise no_permission('文件操作需要有效账号')
    if str(actor.get('userType') or '').upper() == 'STUDENT':
        from app.services.mobile_student_service import resolve_student
        student = resolve_student(db, actor)
        if not student:
            raise no_permission('当前账号未绑定有效学生主档')
        actor.update(studentId=str(student.id),studentNo=student.student_no)
    elif not has_permission(actor, 'internship.student.view'):
        raise no_permission('当前角色不能操作实习文件')
    return actor


def validate_upload(data, filename, content_type):
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise AppException('VALIDATION_ERROR','文件不能为空且不得超过20MB',http_status=413)
    name = security.sanitize_filename(filename)
    ext = Path(name).suffix.lower().lstrip('.')
    if ext not in ALLOWED_EXTENSIONS:
        raise AppException('FILE_TYPE_NOT_ALLOWED','不支持该附件格式')
    if ext in {'mp4','webm','rar'}:
        valid = (ext=='mp4' and len(data)>=12 and data[4:8]==b'ftyp') or (ext=='webm' and data.startswith(b'\x1aE\xdf\xa3')) or (ext=='rar' and data.startswith(b'Rar!\x1a\x07'))
        if not valid:
            raise AppException('FILE_TYPE_MISMATCH','文件内容与扩展名不一致')
        mime = {'mp4':'video/mp4','webm':'video/webm','rar':'application/vnd.rar'}[ext]
        from app.services.file_scan_config import get_file_scan_config
        scan = get_file_scan_config()
        state = 'QUARANTINED' if scan.required or scan.enabled else 'AVAILABLE'
    else:
        mime,state = security.validate_content(filename=name,declared_content_type=content_type,
            data=data,ext=ext,biz_type='INTERNSHIP',source='USER')
    if ext in {'doc','xls'} and not data.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        raise AppException('FILE_TYPE_MISMATCH','Office文件内容与扩展名不一致')
    if ext in {'png','jpg','jpeg','gif'}:
        try:
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > 25_000_000:
                    raise AppException('FILE_TYPE_NOT_ALLOWED','图片像素尺寸过大')
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise AppException('FILE_TYPE_MISMATCH','图片损坏或内容不合法') from exc
    # Documents must not become available in production before required scanning.
    from app.services.file_scan_config import get_file_scan_config
    scan = get_file_scan_config()
    if ext not in {'png','jpg','jpeg','gif'} and (scan.required or scan.enabled):
        state = 'QUARANTINED'
    return name,ext,mime,state


def store_upload(data, filename, content_type, purpose, user):
    if str(purpose).upper() not in UPLOAD_PURPOSES:
        raise AppException('VALIDATION_ERROR','附件业务类型不属于已开放实习业务')
    name,ext,mime,state = validate_upload(data,filename,content_type)
    key = f'{_tid()}/{datetime.utcnow():%Y%m%d}/{uuid4().hex}.{ext}'
    storage = get_backend()
    stage = storage.staging_path(key)
    target = None
    commit_started = False
    with session() as db:
        actor = actor_for_files(db,user)
        try:
            stage.write_bytes(data)
            row = FileObject(tenant_id=_tid(),file_key=key,file_name=name,ext=ext,mime_type=mime,
                size_bytes=len(data),sha256=sha256(data).hexdigest(),biz_type='TEMP_PRIVATE',
                owner_user_id=resolve_message_user_id(actor),visibility='PRIVATE',security_level='SENSITIVE',
                status=state,upload_source='USER',storage_backend='local',storage_zone='ACTIVE',
                scan_required=state=='QUARANTINED',scan_status='PENDING' if state=='QUARANTINED' else 'NOT_REQUIRED',
                available_at=datetime.utcnow() if state=='AVAILABLE' else None)
            db.add(row); db.flush()
            from app.services.file_scan_service import enqueue_file_scan
            enqueue_file_scan(db, row)
            from app.modules.internship.services.internship_audit_service import add_audit
            add_audit(db,target_type='FILE',target_id=row.id,action='FILE_UPLOAD',user=actor,
                      detail={'fileId':str(row.id),'sha256':row.sha256,'sizeBytes':len(data),'purpose':purpose,'status':state})
            target = storage.persist(key,stage)
            commit_started = True
            db.commit()
            return access.file_view(row,user=actor,bindings=[],db=db)
        except Exception:
            db.rollback()
            stage.unlink(missing_ok=True)
            # A lost COMMIT acknowledgement is ambiguous: keep private bytes for reconciliation.
            # Deleting here could destroy a file whose database transaction actually committed.
            if target is not None and not commit_started: Path(target).unlink(missing_ok=True)
            raise


def authorized_file(file_id, user, action='meta'):
    value=str(file_id or '')
    if not value.isascii() or not value.isdigit() or len(value)>19 or not 0<int(value)<=9223372036854775807:
        raise not_found('文件不存在')
    with session() as db:
        actor = actor_for_files(db,user)
        row,bindings = access._load(db,_tid(),int(value))
        if not row or not access.authorize_file_object(row,bindings,actor,action,db=db):
            raise not_found('文件不存在或不在可访问范围内')
        # Bound report/insurance files are checked against current business scope, not uploader history.
        from app.models import InternshipInsurance, InternshipProcessReport, WeeklyReport, InternshipRecord
        mapping={'INTERNSHIP_INSURANCE':(InternshipInsurance,'internship.insurance.view'),
                 'INTERNSHIP_REPORT':(InternshipProcessReport,'internship.report.view'),
                 'INTERNSHIP_WEEKLY_REPORT':(WeeklyReport,'internship.report.view')}
        if row.biz_type in mapping:
            model,permission=mapping[row.biz_type]
            business=db.scalar(select(model).where(model.tenant_id==_tid(),model.id==int(row.biz_id),model.is_deleted.is_(False))) if str(row.biz_id or '').isdigit() else None
            record=db.get(InternshipRecord,business.internship_id) if business else None
            if not record or record.tenant_id!=_tid() or record.is_deleted:
                raise not_found('业务附件不存在')
            if str(actor.get('userType') or '').upper()=='STUDENT':
                if str(record.student_id)!=actor['studentId']: raise not_found('业务附件不存在')
            else:
                from app.modules.internship.services.internship_scope import assert_internship_record_scope
                if not has_permission(actor,permission): raise no_permission('无权查看该业务附件')
                assert_internship_record_scope(db,record.id,actor,'查看实习附件')
        return row, access.file_view(row,user=actor,bindings=bindings,db=db)
