"""Standalone authenticated upload/read boundary for internship evidence files.
User uploads remain private until a canonical business transaction binds them.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select, update
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.models.file import FileObject, FileBinding, FileJob, FileUploadSession, TenantStorageQuota
from app.services import file_access_service as access, file_content_security as security
from app.services.db_service import _tid, session
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_TENANT_BYTES = 10 * 1024**3
# One legal report can contain 30 images, 10 videos and 9 documents before binding.
MAX_TEMP_FILES = 49
MAX_TEMP_BYTES = 200 * 1024**2
TEMP_LIFETIME = timedelta(hours=24)
UPLOAD_RESERVATION_SOURCE = 'INTERNSHIP_QUOTA_V1'
ALLOWED_EXTENSIONS = frozenset({'png','jpg','jpeg','gif','pdf','doc','docx','xls','xlsx','txt','csv','zip','rar','mp4','webm'})
UPLOAD_PURPOSES = frozenset({'ATTACHMENT','INTERNSHIP','INTERNSHIP_REPORT','INTERNSHIP_WEEKLY_REPORT',
    'INTERNSHIP_INSURANCE_POLICY','INTERNSHIP_INSURANCE','INTERNSHIP_PLAN_TASK',
    'INTERNSHIP_APPLICATION_EVIDENCE','INTERNSHIP_STUDENT_EVAL','INTERNSHIP_LEAVE','INTERNSHIP_EMPLOYMENT','INTERNSHIP_VISIT',
    'INTERNSHIP_CHECKIN_PHOTO','INTERNSHIP_CHECKIN_EXEMPTION','INTERNSHIP_TEACHER_CHECKIN_PHOTO',
    'INTERNSHIP_CUSTOM_MATERIAL','INTERNSHIP_MATERIAL_TEMPLATE',
    'INTERNSHIP_INCIDENT','INTERNSHIP_EMERGENCY','COMPLIANCE_EVIDENCE',
    'INTERNSHIP_SCORE_ADJUSTMENT','INTERNSHIP_REGULATORY_TEMPLATE',
    'INTERNSHIP_APPLICATION','INTERNSHIP_FEEDBACK','INTERNSHIP_NOTICE','INTERNSHIP_TEACHER_MAKEUP',
    'INTERNSHIP_ENTERPRISE_EVAL','INTERNSHIP_ENTERPRISE_LOGO','TEMP_PRIVATE',
    'SYSTEM_BRAND','SYSTEM_DOCUMENT','SYSTEM_MIGRATION'})


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
    elif not has_permission(actor, 'internship.student.view') and not any(has_permission(actor,f'system.{key}.{action}')
            for key in ('brand','delivery','migration') for action in ('view','manage')):
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
        state = 'QUARANTINED'
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
    # A missing engine is a blocked upload, including the shared local acceptance runtime.
    if ext not in {'png','jpg','jpeg','gif'}:
        state = 'QUARANTINED'
    return name,ext,mime,state


def _reserve_upload(key, size, actor_id):
    """Reserve before any bytes exist. A fresh transaction avoids stale snapshot totals."""
    from app.models import Tenant
    with session() as db:
        # ponytail: one short lock per school; a counter is only needed at higher upload throughput.
        tenant = db.scalar(select(Tenant).where(Tenant.id == _tid(), Tenant.status == 'ACTIVE',
            Tenant.is_deleted.is_(False)).with_for_update())
        if not tenant:
            raise no_permission('学校已停用，无法上传附件')
        quota = db.scalar(select(TenantStorageQuota).where(
            TenantStorageQuota.tenant_id == _tid(), TenantStorageQuota.is_deleted.is_(False)))
        limit = int(quota.total_quota_bytes) if quota and quota.hard_limit_enabled else DEFAULT_TENANT_BYTES
        used = int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
            FileObject.tenant_id == _tid(), FileObject.storage_zone != 'PURGED')) or 0)
        pending = (FileUploadSession.tenant_id == _tid(), FileUploadSession.source == UPLOAD_RESERVATION_SOURCE,
                   FileUploadSession.status == 'CREATED', FileUploadSession.is_deleted.is_(False))
        reserved = int(db.scalar(select(func.coalesce(func.sum(FileUploadSession.expected_size), 0)).where(*pending)) or 0)
        if size + used + reserved > limit:
            raise AppException('FILE_QUOTA_EXCEEDED', '学校附件存储容量已满，请联系管理员', http_status=413)
        temporary = (FileObject.tenant_id == _tid(), FileObject.owner_user_id == actor_id,
                     FileObject.biz_type == 'TEMP_PRIVATE', FileObject.storage_zone != 'PURGED')
        count, temp_bytes = db.execute(select(func.count(), func.coalesce(func.sum(FileObject.size_bytes), 0))
            .select_from(FileObject).where(*temporary)).one()
        pending_count, pending_bytes = db.execute(select(func.count(), func.coalesce(func.sum(FileUploadSession.expected_size), 0))
            .select_from(FileUploadSession).where(*pending, FileUploadSession.created_by == actor_id)).one()
        if int(count) + int(pending_count) >= MAX_TEMP_FILES or int(temp_bytes) + int(pending_bytes) + size > MAX_TEMP_BYTES:
            raise AppException('FILE_TEMP_QUOTA_EXCEEDED', '待提交附件数量或容量已达上限，请先完成已有材料提交', http_status=413)
        reservation = FileUploadSession(tenant_id=_tid(), session_key=uuid4().hex,
            source=UPLOAD_RESERVATION_SOURCE, status='CREATED', expected_size=size, received_size=0,
            created_by=actor_id, expires_at=datetime.utcnow()+TEMP_LIFETIME, metadata_json={'fileKey': key})
        db.add(reservation); db.flush(); db.commit()
        return reservation.id


def _release_reservation(reservation_id):
    with session() as db:
        row = db.scalar(select(FileUploadSession).where(FileUploadSession.id == reservation_id,
            FileUploadSession.tenant_id == _tid(), FileUploadSession.source == UPLOAD_RESERVATION_SOURCE).with_for_update())
        if row and row.status == 'CREATED':
            row.status = 'FAILED'
            db.commit()


def cleanup_expired_uploads(limit=20, tenant_id=None):
    """Only new managed reservations are eligible; historical uploads are never swept."""
    with session() as db:
        query = select(FileUploadSession).where(FileUploadSession.source == UPLOAD_RESERVATION_SOURCE,
            FileUploadSession.status.in_(['CREATED', 'COMPLETED']),
            FileUploadSession.expires_at <= datetime.utcnow(), FileUploadSession.is_deleted.is_(False))
        if tenant_id is not None:
            query = query.where(FileUploadSession.tenant_id == tenant_id)
        rows = db.scalars(query.order_by(FileUploadSession.id).limit(limit).with_for_update(skip_locked=True)).all()
        storage = get_backend()
        for reservation in rows:
            key = (reservation.metadata_json or {}).get('fileKey')
            if not key or not key.startswith(f'{reservation.tenant_id}/'):
                raise AppException('FILE_QUOTA_RECONCILE_REQUIRED', '附件容量记录需要管理员核对', http_status=503)
            file = db.scalar(select(FileObject).where(FileObject.tenant_id == reservation.tenant_id,
                FileObject.file_key == key).with_for_update())
            if file:
                bound = db.scalar(select(FileBinding.id).where(FileBinding.tenant_id == reservation.tenant_id,
                    FileBinding.file_id == file.id, FileBinding.is_deleted.is_(False)).limit(1))
                if file.legal_hold or bound or file.biz_type != 'TEMP_PRIVATE' or file.biz_id:
                    reservation.status = 'RETAINED'
                    continue
            # Release capacity only after both staging and final bytes are actually gone.
            storage.staging_path(key).unlink(missing_ok=True)
            target = storage.fetch_local(key)
            if target: target.unlink(missing_ok=True)
            if file:
                file.is_deleted = True; file.deleted_at = datetime.utcnow(); file.storage_zone = 'PURGED'
                db.execute(update(FileJob).where(FileJob.tenant_id == reservation.tenant_id,
                    FileJob.file_id == file.id, FileJob.job_type == 'FILE_SCAN',
                    FileJob.status.in_(['PENDING', 'RUNNING', 'RETRY', 'DEAD']), FileJob.is_deleted.is_(False))
                    .values(status='CANCELLED', locked_at=None, locked_by=None, last_error='TemporaryUploadExpired'))
            reservation.status = 'EXPIRED'
        db.commit()
        return len(rows)


def store_upload(data, filename, content_type, purpose, user):
    if str(purpose).upper() not in UPLOAD_PURPOSES:
        raise AppException('VALIDATION_ERROR','附件业务类型不属于已开放实习业务')
    if str(purpose).upper().startswith('SYSTEM_'):
        from app.core.permissions import enforce_permission
        category={'SYSTEM_BRAND':'brand','SYSTEM_DOCUMENT':'delivery','SYSTEM_MIGRATION':'migration'}[str(purpose).upper()]
        enforce_permission(user,f'system.{category}.manage')
    elif str(user.get('userType') or '').upper()!='STUDENT' and not has_permission(user,'internship.student.view'):
        raise no_permission('当前身份没有实习附件上传权限')
    name,ext,mime,state = validate_upload(data,filename,content_type)
    key = f'{_tid()}/{datetime.utcnow():%Y%m%d}/{uuid4().hex}.{ext}'
    storage = get_backend()
    stage = storage.staging_path(key)
    target = None
    commit_started = False
    with session() as db:
        actor = actor_for_files(db,user)
        cleanup_expired_uploads(tenant_id=_tid())
        reservation_id = _reserve_upload(key, len(data), resolve_message_user_id(actor))
        try:
            reservation = db.scalar(select(FileUploadSession).where(FileUploadSession.id == reservation_id,
                FileUploadSession.tenant_id == _tid(), FileUploadSession.status == 'CREATED').with_for_update())
            if not reservation:
                raise AppException('FILE_QUOTA_RECONCILE_REQUIRED', '上传预留已失效，请重试', http_status=409)
            stage.write_bytes(data)
            row = FileObject(tenant_id=_tid(),file_key=key,file_name=name,ext=ext,mime_type=mime,
                size_bytes=len(data),sha256=sha256(data).hexdigest(),biz_type='TEMP_PRIVATE',
                owner_user_id=resolve_message_user_id(actor),visibility='PRIVATE',security_level='SENSITIVE',
                status=state,upload_source='USER',storage_backend='local',storage_zone='ACTIVE',
                retention_until=reservation.expires_at,
                scan_required=state=='QUARANTINED',scan_status='PENDING' if state=='QUARANTINED' else 'NOT_REQUIRED',
                available_at=datetime.utcnow() if state=='AVAILABLE' else None)
            db.add(row); db.flush()
            reservation.file_id = row.id; reservation.status = 'COMPLETED'
            reservation.received_size = len(data); reservation.completed_at = datetime.utcnow()
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
            if not commit_started:
                persisted = storage.fetch_local(key)
                if persisted: persisted.unlink(missing_ok=True)
                _release_reservation(reservation_id)
            raise


def authorized_file(file_id, user, action='meta'):
    value=str(file_id or '')
    if not value.isascii() or not value.isdigit() or len(value)>19 or not 0<int(value)<=9223372036854775807:
        raise not_found('文件不存在')
    with session() as db:
        row,bindings = access._load(db,_tid(),int(value))
        actor = dict(user) if row and str(row.biz_type or '').startswith('SYSTEM_') else actor_for_files(db,user)
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
