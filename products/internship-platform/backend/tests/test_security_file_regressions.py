"""File boundaries exercised without shared database or retained files."""
import io
import sys
import unittest
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import load_workbook
from app.core.exceptions import AppException
from app.services import file_service, internship_file_transfer_service as transfer, xlsx_util


class FileSecurityTest(unittest.TestCase):
    def test_missing_scanner_never_releases_document_upload(self):
        with patch('app.services.file_scan_config.get_file_scan_config',return_value=NS(enabled=False,required=False)):
            self.assertEqual(transfer.validate_upload(b'ordinary text','note.txt','text/plain')[3],'QUARANTINED')

    def test_multi_attachment_commands_share_the_owner_guard(self):
        from app.models import InternshipIncident
        from app.modules.internship.services import internship_student_feedback_service as feedback
        from app.modules.internship.services import internship_incident_service as incidents
        from app.modules.internship.services import internship_scope
        actor={'userId':'db-5'}
        for command in ('feedback','incident','followup','plan'):
            for owner in (5,6):
                with self.subTest(command=command,owner=owner),ExitStack() as stack:
                    row=self.file(owner)
                    incident=NS(id=4,internship_id=1,version=0,status='REPORTED',severity='MEDIUM',file_ids=[],risk_id=None)
                    db=MagicMock(); db.get.return_value=NS(id=1,tenant_id=1,is_deleted=False)
                    db.scalars.return_value.all.return_value=[]
                    db.scalar.side_effect=lambda query: incident if query.column_descriptions[0]['entity'] is InternshipIncident else row
                    db.add.side_effect=lambda obj:setattr(obj,'id',4) if getattr(obj,'id',None) is None else None
                    for module in (feedback,incidents,file_service):
                        stack.enter_context(patch.object(module,'_tid',return_value=1))
                    stack.enter_context(patch('app.services.file_business_binding_service._tid',return_value=1))
                    for module in (feedback,incidents):
                        session=stack.enter_context(patch.object(module,'session'))
                        session.return_value.__enter__.return_value=db
                    stack.enter_context(patch.object(file_service,'get_file_meta',return_value={'ext':'png'}))
                    rec=NS(id=1,student_id=10,batch_id=7,enterprise_id=9,advisor_user_id=None)
                    stack.enter_context(patch.object(feedback,'_student_context',return_value=(rec,NS(id=10,real_name='学生'),7)))
                    stack.enter_context(patch.object(internship_scope,'assert_internship_record_scope',return_value=rec))
                    stack.enter_context(patch.object(incidents,'_find_by_idempotency_key',return_value=None))
                    actions={
                        'feedback':lambda:feedback.create(actor,{'title':'反馈问题','content':'实际反馈内容','feedbackLevel':'COLLEGE','imageFileIds':['8']}),
                        'incident':lambda:incidents.report_incident({'idempotencyKey':'test','summary':'情况摘要','internshipId':'1','fileIds':['8']},actor),
                        'followup':lambda:incidents.transition('4','INVESTIGATING',{'expectedVersion':0,'fileIds':['8']},actor),
                        'plan':lambda:incidents.create_plan({'planName':'应急预案','batchId':'7','responsiblePerson':'老师','emergencyContact':'测试联系','responseSteps':'处置步骤','fileIds':['8']},actor),
                    }
                    if owner==5:
                        actions[command](); db.commit.assert_called_once()
                    else:
                        with self.assertRaises(AppException): actions[command]()
                        db.commit.assert_not_called()

    def test_cleanup_failure_does_not_stop_scanning(self):
        from app import file_scan_worker as worker
        factory=MagicMock(); factory.return_value.__enter__.return_value.scalar.return_value=0
        with patch.object(transfer,'cleanup_expired_uploads',side_effect=OSError('busy')), \
             patch.object(worker,'reconcile_pending_uploads',return_value=0), \
             patch.object(worker,'process_next_scan_job',return_value={'processed':False}) as scan, \
             patch.object(worker,'get_sessionmaker',return_value=factory), \
             patch.object(worker,'get_file_scan_config',return_value=NS(enabled=True)), \
             patch.object(worker,'ClamAVClient') as engine:
            engine.return_value.ping.return_value=True
            result=worker.run_once(1)
            scan.assert_called_once(); self.assertFalse(result['healthy'])

    def test_scan_only_processes_enqueued_jobs_without_cleanup_or_historical_reconciliation(self):
        from app import file_scan_worker as worker
        factory=MagicMock();factory.return_value.__enter__.return_value.scalar.return_value=0
        with patch.object(transfer,'cleanup_expired_uploads') as cleanup, \
             patch.object(worker,'reconcile_pending_uploads') as reconcile, \
             patch.object(worker,'process_next_scan_job',side_effect=[{'processed':True,'jobStatus':'SUCCEEDED'},{'processed':False}]) as scan, \
             patch.object(worker,'get_sessionmaker',return_value=factory), \
             patch.object(worker,'get_file_scan_config',return_value=NS(enabled=True)), \
             patch.object(worker,'ClamAVClient') as engine:
            engine.return_value.ping.return_value=True
            result=worker.run_once(2,scan_only=True)
            self.assertEqual(result['processed'],1);self.assertTrue(result['healthy'])
            cleanup.assert_not_called();reconcile.assert_not_called();self.assertEqual(scan.call_count,2)

    def test_temp_count_and_bytes_include_inflight_reservations(self):
        for totals in ([(transfer.MAX_TEMP_FILES-1,0),(1,0)], [(0,transfer.MAX_TEMP_BYTES),(0,0)]):
            db=MagicMock(); db.scalar.side_effect=[NS(id=1),None,0,0]
            db.execute.return_value.one.side_effect=totals
            with patch.object(transfer,'session') as session, patch.object(transfer,'_tid',return_value=1):
                session.return_value.__enter__.return_value=db
                with self.assertRaises(AppException): transfer._reserve_upload('1/test',1,5)
                db.commit.assert_not_called()

    def test_largest_legal_report_can_reserve_its_last_attachment(self):
        from app.modules.internship.schemas.internship import ProcessReportRuleCfg
        from app.modules.internship.services.internship_report_quality_service import MAX_REPORT_DOCUMENTS
        def upper_bound(field):
            return next(rule.le for rule in ProcessReportRuleCfg.model_fields[field].metadata
                        if getattr(rule, 'le', None) is not None)
        required_slots = upper_bound('maxImages') + upper_bound('maxVideos') + MAX_REPORT_DOCUMENTS
        self.assertEqual(required_slots, 49)
        db=MagicMock(); db.scalar.side_effect=[NS(id=1),None,0,0]
        db.execute.return_value.one.side_effect=[(required_slots-2,47),(1,1)]
        def added(row): row.id=33
        db.add.side_effect=added
        with patch.object(transfer,'session') as session, patch.object(transfer,'_tid',return_value=1):
            session.return_value.__enter__.return_value=db
            self.assertEqual(transfer._reserve_upload('1/last-report-attachment',1,5),33)
        self.assertEqual(transfer.MAX_TEMP_FILES,required_slots)
        self.assertEqual(transfer.MAX_UPLOAD_BYTES,20*1024**2)
        self.assertEqual(transfer.MAX_TEMP_BYTES,200*1024**2)
        self.assertEqual(transfer.DEFAULT_TENANT_BYTES,10*1024**3)
        self.assertIsNotNone(db.scalar.call_args_list[0].args[0]._for_update_arg)

    def test_reservation_is_committed_with_expiry_before_return(self):
        db=MagicMock(); db.scalar.side_effect=[NS(id=1),None,0,0]
        db.execute.return_value.one.side_effect=[(0,0),(0,0)]
        def added(row): row.id=33
        db.add.side_effect=added
        with patch.object(transfer,'session') as session, patch.object(transfer,'_tid',return_value=1):
            session.return_value.__enter__.return_value=db
            self.assertEqual(transfer._reserve_upload('1/test',100,5),33)
        reservation=db.add.call_args.args[0]
        self.assertEqual(reservation.expected_size,100); self.assertEqual(reservation.created_by,5)
        self.assertGreater(reservation.expires_at,datetime.utcnow()); db.commit.assert_called_once()
        self.assertIsNotNone(db.scalar.call_args_list[0].args[0]._for_update_arg)

    def test_cleanup_releases_only_unbound_managed_bytes(self):
        for bound in (False,True):
            with TemporaryDirectory() as directory:
                target=Path(directory)/'file'; target.write_bytes(b'kept-until-cleanup')
                reservation=NS(id=1,tenant_id=1,metadata_json={'fileKey':'1/file'},status='COMPLETED')
                row=self.file(); row.legal_hold=False
                db=MagicMock(); db.scalars.return_value.all.return_value=[reservation]
                db.scalar.side_effect=[row, 9 if bound else None]
                storage=MagicMock(); storage.staging_path.return_value=Path(directory)/'stage'; storage.fetch_local.return_value=target
                with patch.object(transfer,'session') as session, patch.object(transfer,'get_backend',return_value=storage):
                    session.return_value.__enter__.return_value=db
                    transfer.cleanup_expired_uploads()
                self.assertEqual(target.exists(),bound)
                self.assertEqual(reservation.status,'RETAINED' if bound else 'EXPIRED')
                if not bound: self.assertEqual(row.storage_zone,'PURGED')

    def test_upload_reserves_before_bytes_when_full(self):
        db = MagicMock()
        db.scalar.side_effect = [NS(id=1), NS(total_quota_bytes=10, hard_limit_enabled=True), 10, 0, 0, 0]
        storage = MagicMock()
        with patch.object(transfer, 'session') as session, patch.object(transfer, '_tid', return_value=1), \
             patch.object(transfer, 'validate_upload', return_value=('a.txt', 'txt', 'text/plain', 'QUARANTINED')), \
             patch.object(transfer, 'actor_for_files', return_value={'userId': 'db-5'}), \
             patch.object(transfer, 'get_backend', return_value=storage), \
             patch.object(transfer, 'cleanup_expired_uploads', create=True), \
             patch.object(transfer, '_reserve_upload', wraps=transfer._reserve_upload) as reserve, \
             patch('app.services.file_scan_service.enqueue_file_scan'), \
             patch('app.modules.internship.services.internship_audit_service.add_audit'), \
             patch.object(transfer.access, 'file_view', return_value={}):
            session.return_value.__enter__.return_value = db
            with self.assertRaises(AppException) as caught:
                transfer.store_upload(b'content', 'a.txt', 'text/plain', 'ATTACHMENT', {'userId': 'db-5','userType':'STUDENT'})
            self.assertEqual(caught.exception.code,'FILE_QUOTA_EXCEEDED')
            reserve.assert_called_once()
            storage.staging_path.return_value.write_bytes.assert_not_called()
            storage.persist.assert_not_called()

    def test_existing_evidence_purposes_reach_validation_without_bypassing_permissions(self):
        for purpose in ('INTERNSHIP_INCIDENT','INTERNSHIP_EMERGENCY','COMPLIANCE_EVIDENCE',
                        'INTERNSHIP_SCORE_ADJUSTMENT','INTERNSHIP_REGULATORY_TEMPLATE'):
            with self.subTest(purpose=purpose), patch.object(transfer,'validate_upload',side_effect=RuntimeError('validation reached')) as validate:
                with self.assertRaisesRegex(RuntimeError,'validation reached'):
                    transfer.store_upload(b'content','a.txt','text/plain',purpose,{'userId':'db-5','userType':'STUDENT'})
                validate.assert_called_once()
                validate.reset_mock()
                with self.assertRaises(AppException):
                    transfer.store_upload(b'content','a.txt','text/plain',purpose,{'userId':'db-5','userType':'TEACHER'})
                validate.assert_not_called()

    def test_actual_multipart_and_query_purposes_reach_authority_and_conflicts_fail(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1 import standalone_files
        from app.core.security import get_current_user
        from app.core.exceptions import register_exception_handlers
        app=FastAPI();app.include_router(standalone_files.router);register_exception_handlers(app)
        app.dependency_overrides[get_current_user]=lambda:{'userId':'db-5'}
        with TestClient(app) as client,patch.object(transfer,'store_upload',return_value={'id':'8'}) as store:
            for path,data,purpose in (
                ('/files',{'bizType':'SYSTEM_BRAND'},'SYSTEM_BRAND'),
                ('/files?bizType=COMPLIANCE_EVIDENCE',{},'COMPLIANCE_EVIDENCE'),
                ('/files',{},'ATTACHMENT')):
                result=client.post(path,data=data,files={'file':('a.txt',b'original bytes','text/plain')})
                self.assertEqual(result.status_code,200)
                self.assertEqual(store.call_args.args[:4],(b'original bytes','a.txt','text/plain',purpose))
            store.reset_mock()
            result=client.post('/files?bizType=ATTACHMENT',data={'bizType':'SYSTEM_BRAND'},files={'file':('a.txt',b'bytes','text/plain')})
            self.assertEqual(result.status_code,400);store.assert_not_called()

    def file(self, owner=5):
        return NS(id=8, tenant_id=1, owner_user_id=owner, created_by=owner, is_deleted=False,
                  status='AVAILABLE', scan_status='CLEAN', biz_type='TEMP_PRIVATE', biz_id=None,
                  visibility='PRIVATE', retention_until=datetime.utcnow()+timedelta(hours=1),
                  upload_source='USER', file_name='a.txt', ext='txt', mime_type='text/plain',
                  size_bytes=1, sha256='a', file_key='1/a', storage_zone='ACTIVE')

    def bind(self, row, bindings=(), user=None):
        db = MagicMock(); db.scalar.return_value=row; db.scalars.return_value.all.return_value=list(bindings)
        with patch.object(file_service, '_tid', return_value=1), \
             patch('app.services.file_business_binding_service._tid', return_value=1):
            return file_service.bind_file_biz('8', 'INTERNSHIP_FEEDBACK', '4', user=user or {'userId': 'db-5'}, db=db)

    def test_binding_rejects_other_uploader_and_other_object(self):
        with self.assertRaises(AppException): self.bind(self.file(owner=6))
        row = self.file(); row.biz_type='INTERNSHIP_INCIDENT'; row.biz_id='4'; row.visibility='BIZ_SCOPED'
        binding = NS(biz_type='INTERNSHIP_INCIDENT', biz_id='4', subject_type='BUSINESS_OBJECT', subject_id='4',
                     id=1, student_id=None, batch_id=None, relation_type='ATTACHMENT')
        with self.assertRaises(AppException): self.bind(row, [binding])

    def test_binding_rejects_expired_and_unscanned_files(self):
        row=self.file(); row.retention_until=datetime.utcnow()-timedelta(seconds=1)
        with self.assertRaises(AppException): self.bind(row)

    def test_legal_upload_binding_and_same_object_preserve_subject(self):
        self.bind(self.file())
        binding=NS(biz_type='INTERNSHIP_FEEDBACK',biz_id='4',subject_type='STUDENT',subject_id='99',
                   id=1,student_id=99,batch_id='7',relation_type='BUSINESS_EVIDENCE')
        row=self.file(); row.biz_type='INTERNSHIP_FEEDBACK'; row.biz_id='4'; row.visibility='BIZ_SCOPED'
        self.bind(row,[binding])
        self.assertEqual((binding.subject_type,binding.subject_id,binding.student_id,binding.batch_id),('STUDENT','99',99,'7'))
        row=self.file(); row.scan_status='PENDING'
        with self.assertRaises(AppException): self.bind(row)

    def test_error_workbook_is_text_and_reimportable(self):
        values=['0001234567890123456789', '=1+1', ' \t@SUM(A1)', '+cmd', '-cmd']
        data=xlsx_util.build_error_rows_xlsx(['学号','姓名','备注','说明','地址'], [values],
            [{'rowNo':1,'field':'=1+1','message':'=1+1'}], lambda row: row, reimportable=True)
        wb=load_workbook(io.BytesIO(data),data_only=False)
        try:
            self.assertEqual(wb.active['A2'].value,values[0])
            for row in wb.active:
                for cell in row: self.assertNotEqual(cell.data_type,'f')
            self.assertEqual(wb.active['B2'].value,xlsx_util.safe_excel_value(values[1]))
        finally: wb.close()
        imported=xlsx_util.read_xlsx(data, {'学号':'studentNo','姓名':'name'})
        self.assertEqual(imported[0]['studentNo'],values[0])
        self.assertTrue(imported[0]['name'])


if __name__ == '__main__': unittest.main()
