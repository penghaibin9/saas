import ast,pathlib,unittest
from datetime import date,datetime
from types import SimpleNamespace
from sqlalchemy.schema import CreateTable,CreateIndex
from sqlalchemy.dialects import mysql
from optimizer.schema import metadata,jobs,snapshots
from optimizer.persistence import Repository
from optimizer.contracts import InputError,Snapshot
from fixtures import snapshot
ROOT=pathlib.Path(__file__).resolve().parents[2]

class SchemaAndRepositoryReview(unittest.TestCase):
    def test_frozen_migration_matches_candidate_schema(self):
        path=ROOT/'backend/alembic/versions/20260914_aa_opt_candidates.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        values={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)}
        actual=[]
        for table in metadata.sorted_tables:
            actual.append(str(CreateTable(table).compile(dialect=mysql.dialect())))
            actual.extend(str(CreateIndex(i).compile(dialect=mysql.dialect())) for i in sorted(table.indexes,key=lambda x:x.name))
        normalize=lambda sql:sql.replace('CHARSET=utf8mb4 ENGINE=InnoDB','ENGINE=InnoDB CHARSET=utf8mb4')
        self.assertEqual(tuple(map(normalize,actual)),tuple(map(normalize,values['DDL'])))
        self.assertEqual(values['down_revision'],'20260914_aa_grade_analysis_perf')
    def test_snapshot_job_relationship_is_tenant_qualified(self):
        keys=[tuple(c.parent.name for c in constraint.elements) for constraint in jobs.foreign_key_constraints]
        self.assertIn(('tenant_id','snapshot_id'),keys)
    def test_user_reason_is_persisted_not_discarded(self):
        self.assertFalse(jobs.c.requested_reason.nullable)
        self.assertEqual(jobs.c.requested_reason.type.length,500)
    def test_bound_tenant_rejected_before_opening_session(self):
        def network_forbidden():raise AssertionError('Session must not be opened')
        repo=Repository(network_forbidden,tenant_id='1000000000000000007')
        with self.assertRaisesRegex(InputError,'TENANT_SCOPE_MISMATCH'):
            repo.get('1000000000000000008','123')
    def test_bad_object_id_rejected_before_session(self):
        def network_forbidden():raise AssertionError('Session must not be opened')
        repo=Repository(network_forbidden,tenant_id='1000000000000000007')
        for value in [123,True,'0','-1','1e3','99999999999999999999']:
            with self.subTest(value=value),self.assertRaises(InputError):
                repo.get('1000000000000000007',value)
    def test_missing_audit_cannot_enqueue(self):
        def network_forbidden():raise AssertionError('Session must not be opened')
        repo=Repository(network_forbidden,tenant_id='1000000000000000007')
        with self.assertRaisesRegex(InputError,'AUDIT_HOOK_REQUIRED'):
            repo.enqueue_verified(Snapshot.parse(snapshot()),actor='user',idempotency_key='test-12345',options={},reason='test reason',actor_context={'userId':'user','tenantId':'1000000000000000007','roleCode':'TEST'})
    def test_missing_admission_cannot_enqueue(self):
        repo=Repository(lambda:None,tenant_id='1000000000000000007',audit_hook=lambda *args:None)
        with self.assertRaisesRegex(InputError,'ADMISSION_HOOK_REQUIRED'):
            repo.enqueue_verified(Snapshot.parse(snapshot()),actor='user',idempotency_key='test-12345',options={},reason='test reason',actor_context={'userId':'user','tenantId':'1000000000000000007','roleCode':'TEST'})
    def test_source_dto_preserves_large_ids(self):
        path=ROOT/'backend/app/modules/academic_affairs/services/schedule_optimizer_source_service.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_scalar','_row'}]
        scope={'date':date,'datetime':datetime}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'isolated-actual-dto-code','exec'),scope)
        out=scope['_row'](SimpleNamespace(id=1000000000000000007,term_id=1000000000000000008,weekly_hours=4),'id term_id weekly_hours')
        self.assertEqual(out['id'],'1000000000000000007')
        self.assertEqual(out['term_id'],'1000000000000000008')
        self.assertEqual(out['weekly_hours'],4)
