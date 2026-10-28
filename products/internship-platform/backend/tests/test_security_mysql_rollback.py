"""Opt-in shared MySQL checks. Every write is enclosed in an outer rollback.

No schema creation, seed, table cleanup, retained files, or existing business-row updates.
Run only with SECURITY_MYSQL_ROLLBACK_URL pointing at the expressly authorized local DB.
"""
import os
import sys
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.exceptions import AppException
from app.models import Tenant, College, StudentProfile, InternshipRecord, InternshipVisitPlan
from app.models.file import FileObject, FileBinding, FileUploadSession, FileJob, TenantStorageQuota
from app.services import internship_file_transfer_service as transfer, file_service
from app.modules.internship.services import internship_visit_plan_service as plans


@unittest.skipUnless(os.environ.get('SECURITY_MYSQL_ROLLBACK_URL'), 'explicit local rollback connection required')
class SecurityMySQLRollbackTest(unittest.TestCase):
    def setUp(self):
        url=make_url(os.environ['SECURITY_MYSQL_ROLLBACK_URL'])
        if url.host != '127.0.0.1' or url.port != 3318 or url.database != 'internship_pr275_test_20261003':
            raise RuntimeError('refusing a database outside the authorized target')
        self.engine=create_engine(url,hide_parameters=True)
        self.connection=self.engine.connect()
        self.outer=self.connection.begin()
        self.stack=ExitStack()
        self.tid=-int(uuid4().hex[:12],16)
        self.factory=sessionmaker(bind=self.connection,join_transaction_mode='create_savepoint',expire_on_commit=False)
        self.addCleanup(self.cleanup)
        tables=[Tenant,College,FileObject,FileBinding,FileUploadSession,FileJob,TenantStorageQuota,StudentProfile,InternshipRecord,InternshipVisitPlan]
        self.tables=tables
        engines=dict(self.connection.execute(text('SELECT table_name, engine FROM information_schema.tables WHERE table_schema=DATABASE()')).all())
        if any(engines.get(model.__tablename__) != 'InnoDB' for model in tables):
            raise RuntimeError('rollback checks require transactional tables')
        self.connection.execute(text('SET SESSION innodb_lock_wait_timeout=3'))
        with self.factory() as db:
            db.add(Tenant(id=self.tid,tenant_code=f'security-rollback-{uuid4().hex}',school_name='事务回滚测试',status='ACTIVE'))
            db.commit()
        for module in (transfer,file_service,plans):
            self.stack.enter_context(patch.object(module,'_tid',return_value=self.tid))
        self.stack.enter_context(patch('app.services.file_business_binding_service._tid',return_value=self.tid))
        self.stack.enter_context(patch.object(transfer,'session',self.factory))

    def cleanup(self):
        self.stack.close()
        self.outer.rollback()
        self.connection.close()
        try:
            with self.engine.connect() as check:
                for model in getattr(self,'tables',[]):
                    key=model.id if model is Tenant else model.tenant_id
                    self.assertEqual(check.scalar(select(func.count()).select_from(model).where(key==self.tid)),0)
        finally:
            self.engine.dispose()

    def file(self, db, **values):
        row=FileObject(tenant_id=self.tid,file_key=f'{self.tid}/{uuid4().hex}',file_name='test.txt',
            size_bytes=1,owner_user_id=5,biz_type='TEMP_PRIVATE',visibility='PRIVATE',
            status='AVAILABLE',scan_status='CLEAN',retention_until=datetime.utcnow()+timedelta(hours=1),**values)
        db.add(row); db.flush()
        return row

    def test_reserve_release_and_cross_tenant_capacity(self):
        with self.factory() as db:
            db.add(TenantStorageQuota(tenant_id=self.tid,total_quota_bytes=10,hard_limit_enabled=True))
            db.commit()
        first=transfer._reserve_upload(f'{self.tid}/one',6,5)
        with self.assertRaises(AppException): transfer._reserve_upload(f'{self.tid}/two',5,6)
        transfer._release_reservation(first)
        second=transfer._reserve_upload(f'{self.tid}/two',5,6)
        with self.factory() as db:
            self.assertEqual(db.get(FileUploadSession,first).status,'FAILED')
            self.assertEqual(db.get(FileUploadSession,second).status,'CREATED')
            self.assertEqual(db.get(FileUploadSession,second).expected_size,5)

    def test_binding_owner_subject_and_cross_tenant(self):
        with self.factory() as db:
            row=self.file(db); db.commit()
            with self.assertRaises(AppException):
                file_service.bind_file_biz(str(row.id),'INTERNSHIP_FEEDBACK','4',user={'userId':'db-6'},db=db)
            file_service.bind_file_biz(str(row.id),'INTERNSHIP_FEEDBACK','4',user={'userId':'db-5'},db=db)
            db.commit()
            binding=db.scalar(select(FileBinding).where(FileBinding.file_id==row.id,FileBinding.tenant_id==self.tid))
            original=(binding.subject_type,binding.subject_id)
            file_service.bind_file_biz(str(row.id),'INTERNSHIP_FEEDBACK','4',user={'userId':'db-5'},db=db)
            with self.assertRaises(AppException):
                file_service.bind_file_biz(str(row.id),'INTERNSHIP_INCIDENT','4',user={'userId':'db-5'},db=db)
            self.assertEqual((binding.subject_type,binding.subject_id),original)
            with patch.object(file_service,'_tid',return_value=self.tid-1),self.assertRaises(AppException):
                file_service.bind_file_biz(str(row.id),'INTERNSHIP_FEEDBACK','4',user={'userId':'db-5'},db=db)

    def test_expired_pending_scan_is_cancelled(self):
        with TemporaryDirectory() as directory:
            target=Path(directory)/'temporary.txt'; target.write_bytes(b'x')
            with self.factory() as db:
                row=self.file(db); row.status='QUARANTINED'; row.scan_status='PENDING'
                row.scan_required=True; row.retention_until=datetime.utcnow()-timedelta(days=1)
                db.add(FileUploadSession(tenant_id=self.tid,session_key=uuid4().hex,source=transfer.UPLOAD_RESERVATION_SOURCE,
                    status='COMPLETED',file_id=row.id,expected_size=1,expires_at=row.retention_until,metadata_json={'fileKey':row.file_key}))
                job=FileJob(tenant_id=self.tid,file_id=row.id,dedupe_key=f'FILE_SCAN:{row.id}',status='PENDING')
                db.add(job); db.commit(); fid,jid=row.id,job.id
            from types import SimpleNamespace
            storage=SimpleNamespace(staging_path=lambda _:Path(directory)/'stage',fetch_local=lambda _:target)
            with patch.object(transfer,'get_backend',return_value=storage):
                self.assertEqual(transfer.cleanup_expired_uploads(tenant_id=self.tid),1)
            with self.factory() as db:
                self.assertEqual(db.get(FileObject,fid).storage_zone,'PURGED')
                self.assertEqual(db.get(FileJob,jid).status,'CANCELLED')
                self.assertFalse(target.exists())

    def test_teacher_plan_uses_advisor_id_and_frozen_student_number(self):
        with self.factory() as db:
            student=StudentProfile(tenant_id=self.tid,student_no='000123',real_name='虚构学生')
            db.add(student); db.flush()
            db.add(InternshipRecord(tenant_id=self.tid,student_id=student.id,batch_id=7,advisor_user_id=5,advisor_name='同名老师'))
            plan=InternshipVisitPlan(tenant_id=self.tid,batch_id=7,owner_name='同名老师',student_scope='000123')
            other=InternshipVisitPlan(tenant_id=self.tid,batch_id=7,owner_name='同名老师',student_scope='只有姓名')
            db.add_all([plan,other]); db.flush()
            scope={'mode':'SCOPED','advisorUserIds':{5},'advisorNames':set()}
            self.assertTrue(plans._scope_ok(scope,plan,db))
            self.assertFalse(plans._scope_ok(scope,other,db))
            visible=db.scalars(select(InternshipVisitPlan.id).where(InternshipVisitPlan.tenant_id==self.tid,plans.plan_scope_clause(scope))).all()
            self.assertEqual(visible,[plan.id])
            self.assertFalse(plans._scope_ok({**scope,'advisorUserIds':{6}},plan,db))

    def test_frozen_package_rejects_partial_or_empty_college_scope(self):
        from types import SimpleNamespace
        from app.modules.internship.services import internship_evidence_package_service as packages
        from app.modules.internship.services import internship_scope, internship_student_service
        with self.factory() as db,ExitStack() as stack:
            for module in (packages,internship_scope):
                stack.enter_context(patch.object(module,'_tid',return_value=self.tid))
            stack.enter_context(patch('app.services.db_service._tid',return_value=self.tid))
            colleges=[College(tenant_id=self.tid,college_name=name) for name in ('甲院','乙院')]
            db.add_all(colleges); db.flush()
            students=[StudentProfile(tenant_id=self.tid,student_no=str(i),real_name='虚构学生',college_id=c.id) for i,c in enumerate(colleges)]
            db.add_all(students); db.flush()
            records=[InternshipRecord(tenant_id=self.tid,student_id=s.id,batch_id=7) for s in students]
            db.add_all(records); db.flush()
            package=SimpleNamespace(row_count=2,package_type='BATCH',manifest_json={
                'tenantId':str(self.tid),'sourceObjectVersions':[{'type':'INTERNSHIP_RECORD','id':str(r.id)} for r in records]})
            user={'permissions':['internship.evidence.export']}
            for ids in (set(),{colleges[0].id},{c.id for c in colleges}):
                scope={'mode':'SCOPED','roleCode':'COLLEGE_ADMIN','collegeIds':ids}
                with patch.object(internship_student_service,'_current_scope',return_value=scope):
                    if len(ids)==2:
                        packages.assert_package_scope(db,package,user)
                    else:
                        with self.assertRaises(AppException): packages.assert_package_scope(db,package,user)


if __name__=='__main__': unittest.main()
