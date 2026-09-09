"""Real read-only preflight with instrumented SQL IO; not a migrated-MySQL proof."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class ExitReviewTests(unittest.TestCase):
    def setUp(self):
        from app.services import module_commerce_m6_preflight as service
        from app.services import module_commerce_m345_hardening as hardening, tenant_purge_registry
        from app.models import TenantModuleOffboardingJob
        self.service = service
        self.model = TenantModuleOffboardingJob
        self.job = SimpleNamespace(id=9, tenant_id=42, version=0, module_key='internship',
            module_generation=2, state='FROZEN', scope_hash='a'*64, accepted_at=None,
            acceptance_ref=None, export_job_id=None, manifest_id=None, export_file_id=None,
            retention_until=None)
        self.state = SimpleNamespace(generation=2, data_state='FROZEN')
        self.queries = []
        self.db = Mock()
        self.db.scalars.side_effect = self.scalars
        for method in ('add', 'add_all', 'flush', 'commit', 'delete', 'execute'):
            getattr(self.db, method).side_effect = AssertionError('read-only preflight attempted a mutation')
        self.factory = Mock(return_value=self.db)
        settings = [
            (service, 'db_enabled', Mock(return_value=True)),
            (service, 'get_sessionmaker', Mock(return_value=self.factory)),
            (service, '_module_file_risk', Mock(return_value={
                'logicalModuleFileCount': 3, 'legalHoldFileCount': 1,
                'crossModuleReferencedFileCount': 2, 'activeReservationCount': 1,
                'physicalFileDeletionAuthorized': False})),
            (service, 'module_table_inventory', Mock(return_value={
                'inventoryDigest':'b'*64, 'selectorCoverageComplete':False,
                'unsafeSelectorTables':['t_internship_record'], 'candidateTables':[], 'deletionAuthorized':False})),
            (hardening, '_consumer_dependencies', Mock(return_value={'dependencyDigest':'c'*64})),
            (hardening, '_purge_blockers', Mock(return_value=[])),
            (tenant_purge_registry, 'inventory', Mock(return_value={
                'complete':False, 'unknownTables':['t_unreviewed'], 'registryVersion':'fixture', 'reviewedAlembicHead':'fixture'})),
        ]
        self.dependencies = settings[4][2]
        for obj, name, replacement in settings:
            handle = patch.object(obj, name, replacement)
            handle.start(); self.addCleanup(handle.stop)

    def scalars(self, statement):
        self.queries.append(statement)
        self.assertIsNone(statement._for_update_arg, 'read-only review must not lock business writers')
        params = statement.compile().params
        entity = statement.column_descriptions[0]['entity']
        if entity is self.model:
            # A missing tenant predicate would expose the row, so the negative
            # test detects a reader that filters only after collecting details.
            row = self.job if (params.get('id_1') == 9 and params.get('tenant_id_1', 42) == 42) else None
        else:
            self.assertEqual(params['tenant_id_1'], 42)
            row = self.state
        return SimpleNamespace(first=lambda: row)

    def read(self, **kwargs):
        return self.service.preview_module_purge(9, tenant_id=42, expected_generation=2, expected_version=0, **kwargs)

    def test_current_scope_returns_all_fixed_prohibitions_without_writing(self):
        result = self.read()
        self.assertEqual((result['tenantId'], result['jobId'], result['jobVersion']), ('42', '9', 0))
        self.assertEqual(result['moduleGeneration'], 2)
        self.assertTrue(result['dryRunOnly'])
        for field in ('deletionAuthorized', 'physicalPurgeAuthorized', 'canExecutePhysicalPurge',
                      'destructiveExecutionAvailable', 'fullResourceClosureComplete'):
            self.assertIs(result[field], False)
        self.assertEqual(result['destructiveStatements'], [])
        self.assertTrue(all(row['disposition'] == 'PRESERVE' and row['purgeAuthorized'] is False for row in result['sharedFoundation']))
        codes = {row['code'] for row in result['blockers']}
        self.assertTrue({'M0_FULL_RESOURCE_CLOSURE_REQUIRED','MODULE_PURGE_EXECUTION_DISABLED',
                         'BACKUP_DISPOSITION_POLICY_REQUIRED','LEGAL_HOLD_ACTIVE',
                         'SHARED_FILE_REFERENCE_ACTIVE','ACTIVE_STORAGE_RESERVATION'}.issubset(codes))
        self.db.commit.assert_not_called(); self.db.close.assert_called_once()

    def test_other_school_is_rejected_before_consumer_collection(self):
        with self.assertRaises(self.service.AppException) as caught:
            self.service.preview_module_purge(9, tenant_id=43, expected_generation=2, expected_version=0)
        self.assertEqual(caught.exception.http_status, 404)
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(self.queries[0].compile().params['tenant_id_1'], 43)
        self.dependencies.assert_not_called(); self.db.close.assert_called_once()

    def test_old_version_or_generation_is_rejected_before_dependency_queries(self):
        for gen, version in [(1, 0), (2, 1)]:
            with self.subTest(generation=gen, version=version), self.assertRaises(self.service.AppException) as caught:
                self.service.preview_module_purge(9, tenant_id=42, expected_generation=gen, expected_version=version)
            self.assertEqual(caught.exception.http_status, 409)
        self.dependencies.assert_not_called()
        self.assertEqual(len(self.queries), 2)

    def test_unknown_task_has_no_consumer_leak(self):
        with self.assertRaises(self.service.AppException) as caught:
            self.service.preview_module_purge(10, tenant_id=42, expected_generation=2, expected_version=0)
        self.assertEqual(caught.exception.http_status, 404)
        self.dependencies.assert_not_called()

    def test_new_current_module_generation_remains_a_blocker_not_permission(self):
        self.state.generation = 3
        result = self.read()
        self.assertIn('MODULE_GENERATION_CONFLICT', result['blockerCodes'])
        self.assertIs(result['canExecutePhysicalPurge'], False)

    def test_resolved_retention_never_removes_implementation_and_backup_blockers(self):
        self.job.state='RETENTION'; self.state.data_state='RETAINED'
        self.job.accepted_at=datetime(2025,1,1); self.job.acceptance_ref='fixture accepted'
        self.job.export_job_id=3; self.job.manifest_id=4; self.job.export_file_id=5
        self.job.retention_until=datetime(2025,1,2)
        result=self.read()
        self.assertNotIn('RETENTION_ACTIVE',result['blockerCodes'])
        self.assertIn('MODULE_PURGE_EXECUTION_DISABLED',result['blockerCodes'])
        self.assertIs(result['physicalPurgeAuthorized'],False)

    def test_old_internal_reader_still_returns_non_authorizing_evidence(self):
        result=self.service.preview_module_purge(9)
        self.assertIs(result['deletionAuthorized'],False)
        self.assertEqual(result['jobVersion'],0)

    def test_invalid_input_never_opens_a_session(self):
        for field, values in {'job_id':[None,True,'9',1.5,-1,0,2**63], 'tenant_id':[True,'42',0],
                              'expected_generation':[True,0,'2'], 'expected_version':[True,-1,'0']}.items():
            for value in values:
                args=dict(job_id=9,tenant_id=42,expected_generation=2,expected_version=0); args[field]=value
                with self.subTest(field=field,value=value), self.assertRaises(self.service.AppException):
                    self.service.preview_module_purge(**args)
        self.factory.assert_not_called()

    def test_consumer_service_failure_propagates_without_success_report(self):
        self.dependencies.side_effect=RuntimeError('consumer service unavailable')
        with self.assertRaisesRegex(RuntimeError,'consumer service unavailable'): self.read()
        self.db.commit.assert_not_called(); self.db.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
