"""Execute durable school import/export jobs with their original commands and current authorization.

No second task store or partial person writes. A crash rolls back the transaction; the queued
job remains available after restart. Concurrent processes converge on the command's DB locks.
"""
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from sqlalchemy import select
from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException, no_permission
from app.db.session import get_sessionmaker
from app.models import ExcelImportJob, User
from app.services.system_authorization import authorize_subject, audit
from app.services import system_identity_import as identity
from app.services import system_directory_export as directory_exports


def process_next(identifier=None):
    with get_sessionmaker()() as db:
        query=select(ExcelImportJob).where(ExcelImportJob.module_key=='system',
            ExcelImportJob.biz_type.in_(['IDENTITY_STUDENTS','IDENTITY_STAFF','IDENTITY_ORGANIZATIONS','DIRECTORY_EXPORT']),
            ExcelImportJob.status=='QUEUED',ExcelImportJob.is_deleted.is_(False))
        if identifier is not None: query=query.where(ExcelImportJob.id==identifier)
        job=db.scalar(query.order_by(ExcelImportJob.id).limit(1))
        if not job: return False
        identifier,version,exporting=job.id,job.version,job.biz_type=='DIRECTORY_EXPORT'
        user={'userId':str(job.operator_id),'tenantId':str(job.tenant_id),'realName':job.operator_name,
              'currentRoleCode':(job.data_scope_snapshot or {}).get('roleCode','')}
    try:
        with get_sessionmaker()() as db:
            account=db.get(User,int(user['userId']))
            if not account or account.tenant_id!=int(user['tenantId']) or account.is_deleted or account.status!='ACTIVE' or account.must_change_password:
                raise no_permission('上传人的账号已不可用，请重新核对后办理')
            user=authorize_subject(db,account,user)
        set_tenant({'tenantId':user['tenantId']});set_current_user(user)
        if exporting: directory_exports.execute(user,identifier,version)
        else: identity.confirm(user,identifier,version,queued=True)
    except Exception as exc:
        with get_sessionmaker()() as db:
            job=db.scalar(select(ExcelImportJob).where(ExcelImportJob.id==identifier).with_for_update())
            if job and job.status=='QUEUED' and job.version==version:
                job.status='FAILED';job.failed_rows=job.total_rows;job.finished_at=datetime.utcnow();job.version+=1
                job.remark=exc.message if isinstance(exc,AppException) else ('导出失败，未生成可领取结果；请重试或联系实施人员' if exporting else '执行失败，整批未生效；请重试或联系实施人员')
                audit(db,user,'DIRECTORY_EXPORT_FAILED' if exporting else 'IDENTITY_JOB_FAILED','import',identifier,{'reason':job.remark,'rows':job.total_rows})
                db.commit()
    finally:
        set_current_user(None);set_tenant(None)
    return True


@asynccontextmanager
async def lifespan(_app):
    async def drain():
        while True:
            try:
                processed=await asyncio.to_thread(process_next)
            except Exception:
                # A database outage never drops jobs; readiness reports the unavailable service.
                processed=False
            await asyncio.sleep(0 if processed else 5)
    runner=asyncio.create_task(drain())
    try:
        yield
    finally:
        runner.cancel()
        with suppress(asyncio.CancelledError): await runner
