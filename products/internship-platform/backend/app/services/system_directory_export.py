"""Large directory exports reuse the durable school task queue and current authorization."""
from datetime import datetime, timedelta
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from openpyxl import Workbook
from sqlalchemy import or_
from app.core.exceptions import AppException, no_permission, check_version
from app.core.permissions import enforce_permission
from app.models import ExcelImportJob, FileObject
from app.services import system_management as sm
from app.services.system_authorization import audit
from app.services.xlsx_util import safe_excel_value

PAGE_SIZE=1000
# Excel permits 1,048,576 rows, including the header; reject excess before enqueuing.
MAX_ROWS=1048575


def query_for(db,user,kind):
    return sm.scoped_students(db,user) if kind=='student' else sm.scoped_staff(db,user) if kind=='staff' else sm.org_query(db,user,kind)


def view_permission(kind):
    return f'system.{kind}.view' if kind in ('student','staff') else 'system.org.view'


def check_objects(db,user,job):
    enforce_permission(user,'system.person.export')
    snapshot=job.preview_json or {};kind=snapshot['kind']
    enforce_permission(user,view_permission(kind))
    model=sm.StudentProfile if kind=='student' else sm.StaffProfile if kind=='staff' else sm.ORG[kind][0]
    identifiers=snapshot['objectIds']
    for offset in range(0,len(identifiers),PAGE_SIZE):
        chunk=[int(v) for v in identifiers[offset:offset+PAGE_SIZE]]
        allowed=set(db.scalars(query_for(db,user,kind).with_only_columns(model.id).where(model.id.in_(chunk))))
        if allowed!=set(chunk): raise no_permission('任务包含已移出当前管理范围的资料，请按现有范围重新导出')


def enqueue(user,kind,keyword='',account_status=''):
    with sm.transaction(user,'system.person.export') as db:
        enforce_permission(user,view_permission(kind))
        if kind in ('student','staff'):
            model=sm.StudentProfile if kind=='student' else sm.StaffProfile
            query=sm.people_query(db,user,kind,keyword,account_status)
        else:
            model,name,code,_=sm.ORG[kind];query=sm.org_query(db,user,kind)
            if keyword: query=query.where(or_(getattr(model,name).contains(keyword,autoescape=True),getattr(model,code).contains(keyword,autoescape=True)))
        # Store only stable IDs and filters, never a second copy of the personnel rows.
        identifiers=[str(v) for v in db.scalars(query.with_only_columns(model.id).order_by(model.id).limit(MAX_ROWS+1)).yield_per(PAGE_SIZE)]
        if len(identifiers)>MAX_ROWS: raise AppException('VALIDATION_ERROR','结果超过单张表格容量，请缩小筛选条件')
        job=ExcelImportJob(tenant_id=sm.ids(user)[0],module_key='system',biz_type='DIRECTORY_EXPORT',
            file_name=sm.DIRECTORY_LABELS[kind]+'资料导出.xlsx',status='QUEUED',total_rows=len(identifiers),
            operator_id=sm.ids(user)[1],operator_name=user.get('realName'),
            expires_at=datetime.utcnow()+timedelta(hours=24),data_scope_snapshot={'roleCode':user['currentRoleCode']},
            preview_json={'kind':kind,'keyword':keyword,'accountStatus':account_status,'objectIds':identifiers})
        db.add(job);db.flush();audit(db,user,'DIRECTORY_EXPORT_QUEUE',kind,job.id,{'rows':len(identifiers),'keyword':keyword,'accountStatus':account_status})
        return {'id':str(job.id),'status':'QUEUED','total':job.total_rows,'message':'导出任务已登记，请在导入导出任务中查看结果'}


def execute(user,identifier,version):
    from app.services.generated_file_path_service import store_generated_path
    with sm.transaction(user,'system.person.export') as db:
        job=sm.row(db,ExcelImportJob,identifier,user)
        if job.biz_type!='DIRECTORY_EXPORT' or job.module_key!='system' or job.operator_id!=sm.ids(user)[1]:raise no_permission()
        if job.status=='SUCCESS':return
        check_version(job.version,version)
        if job.status!='QUEUED' or not job.expires_at or job.expires_at<=datetime.utcnow():
            raise AppException('RESULT_EXPIRED','导出任务已过期，请重新导出',http_status=410)
        check_objects(db,user,job)
        snapshot=job.preview_json;kind=snapshot['kind'];identifiers=snapshot['objectIds']
        job.started_at=datetime.utcnow()
        with TemporaryDirectory(prefix='internship-directory-') as temporary:
            path=Path(temporary)/'result.xlsx';book=Workbook(write_only=True);sheet=book.create_sheet('基础资料');sheet.freeze_panes='A2'
            try:
                for offset in range(0,max(1,len(identifiers)),PAGE_SIZE):
                    chunk=identifiers[offset:offset+PAGE_SIZE]
                    result=sm.list_people(user,kind,1,PAGE_SIZE,object_ids=chunk) if kind in ('student','staff') else sm.list_organizations(user,kind,1,PAGE_SIZE,object_ids=chunk)
                    if {r['id'] for r in result['items']}!=set(chunk):raise no_permission('导出对象已变化，请重新核对后导出')
                    headers,rows=sm.directory_rows(db,user,kind,result)
                    if offset==0:sheet.append([safe_excel_value(v) for v in headers])
                    for values in rows:sheet.append([safe_excel_value(v) for v in values])
                book.save(path)
            except Exception:
                # Finalize write-only XML inside the disposable directory, never publish partial rows.
                with suppress(Exception):book.save(path)
                raise
            finally:
                book.close()
            file=store_generated_path(path,job.file_name,biz_type='SYSTEM_DIRECTORY_EXPORT',user=user,db=db,security_level='SENSITIVE')
            db.get(FileObject,int(file['fileId'])).biz_id=str(job.id)
        job.preview_json={**snapshot,'fileId':file['fileId']};job.status='SUCCESS';job.success_rows=len(identifiers)
        job.failed_rows=0;job.remark=None;job.finished_at=datetime.utcnow();job.version+=1
        audit(db,user,'DIRECTORY_EXPORT',kind,job.id,{'rows':job.success_rows,'fileId':file['fileId']})


def retry(user,identifier,version):
    with sm.transaction(user,'system.person.export') as db:
        job=sm.row(db,ExcelImportJob,identifier,user)
        if job.module_key!='system' or job.biz_type!='DIRECTORY_EXPORT' or job.operator_id!=sm.ids(user)[1]:raise no_permission('仅任务发起人可重试')
        check_version(job.version,version)
        if job.status!='FAILED' or not job.expires_at or job.expires_at<=datetime.utcnow():raise AppException('VALIDATION_ERROR','仅未过期的失败任务可重试')
        check_objects(db,user,job)
        job.status='QUEUED';job.failed_rows=0;job.remark=None;job.version+=1
        job.data_scope_snapshot={'roleCode':user['currentRoleCode']}
        audit(db,user,'DIRECTORY_EXPORT_RETRY','import',job.id,{'rows':job.total_rows})
        return {'id':str(job.id),'message':'失败任务已重新排队；已成功的任务不会重做'}


def authorize_file(db,file,user):
    if file.biz_type!='SYSTEM_DIRECTORY_EXPORT' or not str(file.biz_id or '').isdigit():return False
    job=db.scalar(sm.tenant_query(ExcelImportJob,user).where(ExcelImportJob.id==int(file.biz_id)))
    if not job or job.module_key!='system' or job.biz_type!='DIRECTORY_EXPORT' or job.operator_id!=sm.ids(user)[1]:return False
    if job.status!='SUCCESS' or not job.expires_at or job.expires_at<=datetime.utcnow() or (job.preview_json or {}).get('fileId')!=str(file.id):return False
    check_objects(db,user,job)
    return True


def result_file(user,identifier):
    with sm.transaction(user,'system.person.export') as db:
        job=sm.row(db,ExcelImportJob,identifier,user)
        if job.module_key!='system' or job.biz_type!='DIRECTORY_EXPORT' or job.operator_id!=sm.ids(user)[1]:raise no_permission('仅导出任务发起人可领取结果')
        if job.status!='SUCCESS':raise AppException('VALIDATION_ERROR','任务尚未成功完成，请查看任务状态',http_status=409)
        file_id=(job.preview_json or {}).get('fileId')
        if not file_id:return None
        file=db.get(FileObject,int(file_id))
        if not file or file.tenant_id!=sm.ids(user)[0] or file.is_deleted or not authorize_file(db,file,user):raise no_permission('导出结果已过期或不可领取，请重新导出')
        audit(db,user,'EXPORT_RESULT_DOWNLOAD','import',job.id,{'rows':job.total_rows})
        return str(file.id)
