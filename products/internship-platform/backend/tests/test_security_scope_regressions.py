"""Focused security boundaries; no shared database writes or cleanup."""
import sys
import io
import json
import zipfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.exceptions import AppException, no_permission
from app.modules.internship.services import internship_evidence_package_service as packages
from app.modules.internship.services import internship_guardian_consent_delivery_service as guardian
from app.modules.internship.services import internship_scope
from app.services import mobile_teacher_service as teachers, file_access_service


class ScopeSecurityTest(unittest.TestCase):
    def test_plain_file_download_does_not_bypass_frozen_package_scope(self):
        file=NS(id=90,tenant_id=1,is_deleted=False,biz_type='COMPLIANCE_EVIDENCE',
                owner_user_id=5,status='AVAILABLE',scan_status='NOT_REQUIRED')
        db=MagicMock(); db.scalars.return_value.all.return_value=[self.package()]
        with patch.object(file_access_service,'current_tenant_id',return_value=1), \
             patch.object(packages,'_tid',return_value=1), \
             patch.object(internship_scope,'assert_internship_record_scope',side_effect=no_permission()):
            self.assertFalse(file_access_service.authorize_file_object(file,[],
                {'userId':'db-5','permissions':['internship.evidence.export']},'download',db))

    def test_guardian_authorized_rotation_keeps_lock_version_audit(self):
        row=NS(id=1,internship_id=4,consent_type='GUARDIAN',status='PENDING',version=2,guardian_token_hash='old')
        db=MagicMock(); db.scalar.return_value=row; db.get.return_value=row
        with patch.object(guardian,'session') as session, patch.object(guardian,'_tid',return_value=1), \
             patch.object(internship_scope,'assert_internship_record_scope'), \
             patch.object(guardian,'_guardian_context'), patch.object(guardian,'_send',return_value={'deliveryStatus':'SENT'}) as send, \
             patch.object(guardian.consent,'_audit') as audit:
            session.return_value.__enter__.return_value=db
            result=guardian.redeliver('1',2,{'userId':'5'})
            self.assertEqual(result['version'],3); self.assertNotEqual(row.guardian_token_hash,'old')
            self.assertIsNotNone(db.scalar.call_args.args[0]._for_update_arg)
            audit.assert_called_once(); db.commit.assert_called_once(); send.assert_called_once()

    def test_visit_plan_owner_uses_stable_creator_id(self):
        from app.modules.internship.services import internship_visit_plan_service as plans
        scope={'mode':'SCOPED','advisorUserIds':{5},'advisorNames':set()}
        plan=NS(id=8,created_by=5,owner_name='原姓名',collaborators='',college_id=None)
        self.assertTrue(plans._scope_ok(scope,plan))
        plan.created_by=6; plan.owner_name='同名老师'
        self.assertFalse(plans._scope_ok(scope,plan))

    def test_enterprise_package_only_includes_authorized_record_complaints(self):
        from app.models import InternshipComplaint
        from sqlalchemy.sql import operators
        from sqlalchemy.sql.elements import False_
        complaints = [NS(id=i, tenant_id=t, enterprise_id=e, internship_id=r, is_deleted=False)
                      for i, t, e, r in [(1,1,7,11), (2,1,7,22), (3,2,7,11), (4,1,8,11), (5,1,7,None)]]
        def select_rows(query):
            rows = []
            if query.column_descriptions[0]['entity'] is InternshipComplaint:
                rows = complaints
                for expr in query._where_criteria:
                    value = False if isinstance(expr.right, False_) else expr.right.value
                    rows = [r for r in rows if (getattr(r, expr.left.key) in value
                            if expr.operator is operators.in_op else getattr(r, expr.left.key) == value)]
            return NS(all=lambda: rows)
        db = MagicMock(); db.scalar.return_value=0; db.scalars.side_effect=select_rows; db.get.return_value=None
        rec=NS(id=11, student_id=101, version=0)
        with patch.object(packages,'session') as session, patch.object(packages,'_tid',return_value=1), \
             patch.object(packages,'_resolve_records',return_value=([rec],None)), \
             patch.object(packages,'_record_entries',return_value={'passed':True,'ruleVersion':'v1'}), \
             patch.object(packages,'_summary_xlsx',return_value=b'xlsx'), \
             patch.object(packages,'_safe_row',side_effect=lambda row: {'id': row.id} if hasattr(row,'id') else {}), \
             patch('app.modules.internship.services.internship_audit_service.assert_high_risk_write_available'), \
             patch.object(packages.file_service,'store_bytes',return_value={'sizeBytes':1,'sha256':'hash','fileId':'90'}) as store:
            session.return_value.__enter__.return_value=db
            packages.generate('ENTERPRISE', '7', {'userId':'5'})
        with zipfile.ZipFile(io.BytesIO(store.call_args.args[0])) as archive:
            self.assertEqual(json.loads(archive.read('evidence/enterprise-complaints-rectification.json')), [{'id':1}])

    def package(self, members=(1, 2), files=()):
        return NS(id=9, package_type='BATCH', target_id=7, status='READY',
                  package_file_id='90', package_version=1, package_sha256='digest',
                  row_count=len(members), manifest_json={'tenantId': '1',
                  'sourceObjectVersions': [{'type': 'INTERNSHIP_RECORD', 'id': str(i)} for i in members],
                  'files': [{'fileId': str(i), 'included': True} for i in files]})

    def download(self, package, allowed, file_allowed=True):
        db = MagicMock(); db.scalar.return_value = package
        def check(_db, rid, *_args, **_kwargs):
            if int(rid) not in allowed: raise no_permission()
            return NS(id=int(rid))
        with patch.object(packages, 'session') as session, patch.object(packages, '_tid', return_value=1), \
             patch.object(packages, '_resolve_records', return_value=([NS(id=i) for i in allowed], 7)), \
             patch.object(internship_scope, 'assert_internship_record_scope', side_effect=check), \
             patch('app.services.internship_file_transfer_service.authorized_file', side_effect=None if file_allowed else no_permission()), \
             patch.object(packages.file_service, 'resolve_download', return_value=('path', 'name')):
            session.return_value.__enter__.return_value = db
            return packages.resolve_package_download('9', {'userId': '5', 'permissions': ['internship.evidence.export']})

    def test_frozen_members_must_all_be_allowed(self):
        for allowed in (set(), {1}):
            with self.subTest(allowed=allowed), self.assertRaises(AppException):
                self.download(self.package(), allowed)
        self.assertEqual(self.download(self.package(), {1, 2}), ('path', 'name'))

    def test_frozen_attachments_and_manifest_fail_closed(self):
        with self.assertRaises(AppException): self.download(self.package(files=(8,)), {1, 2}, False)
        with self.assertRaises(AppException): self.download(self.package(members=()), {1})
        package = self.package(); package.manifest_json['tenantId'] = '2'
        with self.assertRaises(AppException): self.download(package, {1, 2})

    def test_guardian_denied_before_rotation_and_delivery(self):
        row = NS(id=1, internship_id=4, consent_type='GUARDIAN', status='PENDING', version=2,
                 guardian_token_hash='old')
        db = MagicMock(); db.scalar.return_value = row
        with patch.object(guardian, 'session') as session, patch.object(guardian, '_tid', return_value=1), \
             patch.object(internship_scope, 'assert_internship_record_scope', side_effect=no_permission()), \
             patch.object(guardian, '_guardian_context'), patch.object(guardian, '_send') as send, \
             patch.object(guardian.consent, '_audit'):
            session.return_value.__enter__.return_value = db
            with self.assertRaises(AppException): guardian.redeliver('1', 2, {'userId': '5'})
            self.assertEqual(row.guardian_token_hash, 'old')
            db.commit.assert_not_called(); send.assert_not_called()

    def test_guardian_keeps_status_and_version_conflicts(self):
        for status, version in [('CONFIRMED', 2), ('PENDING', 3)]:
            row=NS(id=1, internship_id=4, consent_type='GUARDIAN', status=status, version=version,
                   guardian_token_hash='old')
            db=MagicMock(); db.scalar.return_value=row
            with patch.object(guardian,'session') as session, patch.object(guardian,'_tid',return_value=1), \
                 patch.object(internship_scope,'assert_internship_record_scope'), patch.object(guardian,'_send') as send:
                session.return_value.__enter__.return_value=db
                with self.assertRaises(AppException): guardian.redeliver('1',2,{'userId':'5'})
                self.assertEqual(row.guardian_token_hash,'old'); db.commit.assert_not_called(); send.assert_not_called()

    def test_same_name_never_grants_advisor_access(self):
        scope = {'mode': 'SCOPED', 'roleCode': 'TEACHER', 'advisorUserIds': {5}, 'advisorNames': {'同名老师'}}
        self.assertFalse(teachers.scope_match_row(scope, advisor_name='同名老师', advisor_user_id=6))
        self.assertFalse(teachers.scope_match_row(scope, advisor_name='同名老师'))
        self.assertTrue(teachers.scope_match_row(scope, advisor_name='改名老师', advisor_user_id=5))

    def test_real_name_is_not_a_scope_lookup_key(self):
        db = MagicMock(); db.scalars.return_value.all.return_value = []
        with patch.object(teachers, 'session') as session, patch.object(teachers, '_tid', return_value=1):
            session.return_value.__enter__.return_value = db
            teachers.resolve_teacher_scope({'userId': 'db-5', 'loginName': 'teacher5', 'realName': '同名老师', 'currentRoleCode': 'COLLEGE_ADMIN'})
        values = db.scalars.call_args.args[0].compile().params.values()
        self.assertFalse(any(isinstance(v, (set, list)) and '同名老师' in v for v in values))


if __name__ == '__main__': unittest.main()
