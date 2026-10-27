from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import select
from app.services import job_registry as jobs
from app.core.exceptions import AppException


def test_version_reason_audit_rollback_and_competing_cancel(db_mode, monkeypatch):
    from app.core.context import set_tenant, set_current_user
    from app.models import ExportJob, SecurityAuditLog
    from app.db.session import get_sessionmaker
    from app.services import db_service
    tid=1000000000000000001
    actor={'userId':'db-1','realName':'任务验收经办人','tenantId':str(tid),'currentRoleCode':'SCHOOL_ADMIN'}
    def context():
        set_tenant({'tenantId':tid}); set_current_user(actor)
    context()
    with get_sessionmaker()() as db:
        task=ExportJob(tenant_id=tid,module_code='systemAdmin',export_type='AUDIT_EVIDENCE_PACK',status='CREATED',operator_id=1)
        db.add(task); db.commit(); identifier=f'EXPORT:{task.id}'; pk=task.id
    for version,reason in [(None,'测试缺少版本必须拒绝'),(True,'测试布尔版本必须拒绝'),(99,'测试旧版本必须拒绝'),(0,''),(0,{'reason':'不能转换对象作为原因'})]:
        with get_sessionmaker()() as db:
            with pytest.raises(AppException): jobs.cancel_job(db,identifier,actor=actor,expected_version=version,reason=reason)
    original=db_service.audit_insert_in_session
    def fail_audit(*_args,**_kwargs): raise RuntimeError('isolated audit failure')
    monkeypatch.setattr(db_service,'audit_insert_in_session',fail_audit)
    with get_sessionmaker()() as db:
        with pytest.raises(RuntimeError): jobs.cancel_job(db,identifier,actor=actor,expected_version=0,reason='核验审计失败回滚任务')
        db.rollback()
    monkeypatch.setattr(db_service,'audit_insert_in_session',original)
    with get_sessionmaker()() as db:
        row=db.get(ExportJob,pk)
        assert (row.status,row.version)==('CREATED',0)
    barrier=Barrier(2)
    def cancel(_):
        context()
        with get_sessionmaker()() as db:
            barrier.wait(timeout=10)
            try:
                jobs.cancel_job(db,identifier,actor=actor,expected_version=0,reason='独立并发取消同一测试任务')
                return 'success'
            except AppException as error:
                db.rollback()
                assert error.http_status==409
                return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(cancel,[1,2]))==['conflict','success']
    with get_sessionmaker()() as db:
        row=db.get(ExportJob,pk)
        assert (row.status,row.version)==('CANCELLED',1)
        events=db.scalars(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==tid,
            SecurityAuditLog.action=='JOB_CANCEL',SecurityAuditLog.resource_id==identifier)).all()
        assert len(events)==1
        assert events[0].detail_json['expectedVersion']==0 and events[0].detail_json['version']==1
        assert events[0].detail_json['reason']=='独立并发取消同一测试任务'


def test_job_page_and_overview_count_beyond_old_per_kind_cap(db_mode):
    from app.core.context import set_tenant
    from app.models import Tenant, ExportJob
    from app.db.session import get_sessionmaker
    tid=1000000000000000999
    with get_sessionmaker()() as db:
        db.add(Tenant(id=tid,tenant_code='d603-paging',school_name='独立分页验收学校',status='ACTIVE'))
        db.add_all([ExportJob(tenant_id=tid,module_code='systemAdmin',export_type='AUDIT_EVIDENCE_PACK',status='CREATED') for _ in range(501)])
        db.commit()
    set_tenant({'tenantId':tid})
    with get_sessionmaker()() as db:
        items,total=jobs.list_jobs(db,kind='EXPORT',page=26,page_size=20)
        assert total==501 and len(items)==1
        beyond,total_again=jobs.list_jobs(db,kind='EXPORT',page=10**25,page_size=20)
        assert beyond==[] and total_again==501
        overview=jobs.job_overview(db)
        export=next(item for item in overview['perKind'] if item['kind']=='EXPORT')
        assert export['total']==501 and export['backlog']==501
