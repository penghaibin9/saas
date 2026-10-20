"""M0 collector tests run directly, without the application pytest conftest."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/check' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
R = load('module-commercial-reconcile')
I = load('module-commercial-inventory')
G = load('module-commercial-references')
SHA = 'a' * 40


def sources():
    return {'models': [{'table': 't_parent', 'model': 'Parent', 'path': 'backend/app/models/parent.py', 'startLine': 1,
                        'inheritedFieldNames': ['id', 'tenant_id'], 'tenantScopedSyntactic': True, 'logicalIdFieldsToReview': []},
                       {'table': 't_child', 'model': 'Child', 'path': 'backend/app/models/child.py', 'startLine': 1,
                        'inheritedFieldNames': ['id', 'parent_id'], 'tenantScopedSyntactic': False, 'logicalIdFieldsToReview': ['parent_id']}],
            'staticMigrationHeads': ['migration_head'], 'sourceSha': SHA, 'sourceManifestHash': 'fixture'}


def meta():
    result = {'tables': {'t_parent': {'columns': {'id': {'nullable': False, 'primaryKey': True}, 'tenant_id': {'nullable': False}}, 'foreignKeys': []},
                       't_child': {'columns': {'id': {'nullable': False, 'primaryKey': True}, 'parent_id': {'nullable': False}}, 'foreignKeys': [{'column': 'parent_id', 'target': 't_parent.id'}]}}}


    for name, table in result['tables'].items():
        table['keyContract'] = {'version': 1, 'primaryKey': ['id'], 'foreignKeys': [], 'uniqueKeys': [], 'unsupported': []}
        if name == 't_child':
            table['keyContract']['foreignKeys'] = [{'name': 'fk_parent', 'columns': ['parent_id'],
                'targets': [{'schema': None, 'table': 't_parent', 'column': 'id'}], 'onDelete': 'RESTRICT', 'onUpdate': 'RESTRICT'}]
    return result


class ReconciliationTests(unittest.TestCase):
    def test_equal_sets_never_authorize_m0_or_deletion(self):
        rt = meta(); db = {**copy.deepcopy(rt), 'schemaHeads': ['migration_head'], 'readOnly': True}
        result = R.reconcile(sources(), rt, db)
        self.assertEqual(result['coverageStatus'], 'STRUCTURAL_SETS_MATCH')
        self.assertFalse(result['m0Complete']); self.assertFalse(result['deletionAuthorized'])

    def test_missing_database_is_not_pass(self):
        self.assertEqual(R.reconcile(sources(), meta(), None)['coverageStatus'], 'NOT_RUN')

    def test_declaration_not_registered_is_explicit(self):
        rt = meta(); del rt['tables']['t_child']
        self.assertEqual(R.reconcile(sources(), rt, None)['astOnlyTables'], ['t_child'])

    def test_runtime_constructed_table_is_explicit(self):
        rt = meta(); rt['tables']['t_feedback'] = copy.deepcopy(rt['tables']['t_child'])
        self.assertEqual(R.reconcile(sources(), rt, None)['runtimeOnlyTables'], ['t_feedback'])

    def test_physical_unmodeled_table_is_not_ignored(self):
        rt = meta(); db = {**copy.deepcopy(rt), 'schemaHeads': ['migration_head'], 'readOnly': True}
        db['tables']['t_unmapped'] = copy.deepcopy(rt['tables']['t_child'])
        result = R.reconcile(sources(), rt, db)
        self.assertEqual(result['mysqlOnlyTables'], ['t_unmapped']); self.assertEqual(result['coverageStatus'], 'REVIEW_REQUIRED')

    def test_missing_physical_model_is_not_ignored(self):
        rt = meta(); db = {**copy.deepcopy(rt), 'schemaHeads': ['migration_head'], 'readOnly': True}
        del db['tables']['t_child']
        self.assertEqual(R.reconcile(sources(), rt, db)['runtimeOnlyVsMysql'], ['t_child'])

    def test_column_alias_and_runtime_extension_remain_reviewable(self):
        src = sources(); src['models'][0]['inheritedFieldNames'] = ['id', '_tenant_id']
        self.assertEqual(R.reconcile(src, meta(), None)['astRuntimeColumns'], [{'table': 't_parent', 'astOnly': ['_tenant_id'], 'runtimeOnly': ['tenant_id']}])

    def test_nullable_primary_key_and_fk_drift_are_not_count_only(self):
        rt = meta(); db = {**copy.deepcopy(rt), 'schemaHeads': ['migration_head'], 'readOnly': True}
        db['tables']['t_child']['columns']['parent_id']['nullable'] = True
        db['tables']['t_child']['columns']['id']['primaryKey'] = False
        db['tables']['t_child']['foreignKeys'] = []
        result = R.reconcile(sources(), rt, db)
        self.assertEqual(result['runtimeMysqlColumns'][0]['nullableDifferences'], ['parent_id'])
        self.assertTrue(result['runtimeMysqlConstraints'][0]['primaryKeyDiffers'])
        self.assertEqual(result['runtimeMysqlConstraints'][0]['runtimeOnlyFK'], [('parent_id', 't_parent.id')])

    def test_wrong_or_multiple_migration_heads_block_agreement(self):
        for heads in [['old'], ['migration_head', 'extra']]:
            result = R.reconcile(sources(), meta(), {**meta(), 'schemaHeads': heads, 'readOnly': True})
            self.assertFalse(result['migrationHeadsMatch']); self.assertEqual(result['coverageStatus'], 'REVIEW_REQUIRED')

    def test_empty_metadata_and_database_never_pass(self):
        for rt, db in [({'tables': {}}, None), (meta(), {'tables': {}}), (meta(), {**meta(), 'schemaHeads': [], 'readOnly': True}), (meta(), {**meta(), 'schemaHeads': ['migration_head'], 'readOnly': False})]:
            with self.assertRaises(ValueError): R.reconcile(sources(), rt, db)

    def test_duplicate_declarations_are_not_silently_overwritten(self):
        src = sources(); src['models'].append(src['models'][0])
        with self.assertRaises(ValueError): R.reconcile(src, meta(), None)

    def test_exact_source_fingerprint_and_sha_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'one.py').write_text('pass\n')
            hashes = {'one.py': __import__('hashlib').sha256(b'pass\n').hexdigest()}
            evidence = {'sourceSha': SHA, 'sourceFiles': hashes, 'sourceManifestHash': I.digest(hashes)}
            R.verify_source(root, evidence, SHA)
            with self.assertRaises(ValueError): R.verify_source(root, evidence, 'b' * 40)
            (root / 'one.py').write_text('changed\n')
            with self.assertRaises(ValueError): R.verify_source(root, evidence, SHA)

    def test_missing_invalid_or_unsafe_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for hashes in [{}, {'../escape.py': 'x'}, {'/etc/passwd': 'x'}]:
                report = {'sourceSha': SHA, 'sourceFiles': hashes, 'sourceManifestHash': I.digest(hashes)}
                with self.assertRaises(ValueError): R.verify_source(Path(tmp), report, SHA)

    def test_digest_tampering_is_rejected(self):
        with self.assertRaises(ValueError): R.verify_source(ROOT, {'sourceSha': SHA, 'sourceFiles': {'x': 'y'}, 'sourceManifestHash': 'fake'}, SHA)

    def test_database_target_requires_both_ci_and_exact_ephemeral_scope(self):
        good = 'mysql+pymysql://m0_reader:test@127.0.0.1:3306/m0_commercial_audit'
        env = {'GITHUB_ACTIONS': 'true', 'M0_EPHEMERAL_MYSQL': '1'}
        R.validate_mysql_target(good, env)
        for other in [good.replace('127.0.0.1', 'example.com'), good.replace('m0_reader', 'root'), good.replace('3306','3307'), good.replace('m0_commercial_audit','production'), good + '?local_infile=1', 'sqlite:///tmp.db']:
            with self.assertRaises(ValueError): R.validate_mysql_target(other, env)
        for other_env in [{}, {'GITHUB_ACTIONS': 'true'}, {'M0_EPHEMERAL_MYSQL': '1'}]:
            with self.assertRaises(ValueError): R.validate_mysql_target(good, other_env)

    def test_workflow_job_env_uses_only_server_available_contexts(self):
        import re
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/module-commerce-foundation.yml').read_text())
        allowed = {'github', 'needs', 'strategy', 'matrix', 'vars', 'secrets', 'inputs'}
        for job in workflow['jobs'].values():
            for value in job.get('env', {}).values():
                for expression in re.findall(r'\$\{\{(.*?)\}\}', str(value)):
                    self.assertTrue(set(re.findall(r'(?<![\w.])(\w+)\.', expression)) <= allowed)
        schema = workflow['jobs']['schema-evidence']
        self.assertEqual(schema['env']['OUT'], '/tmp/module-commerce-schema')
        upload = schema['steps'][-1]
        self.assertEqual(upload['with']['path'], schema['env']['OUT'])

    def test_metadata_guard_blocks_and_restores_connectors(self):
        import socket
        from sqlalchemy.engine import Engine
        saved = (socket.socket.connect, socket.create_connection, Engine.connect)
        with R.no_connections():
            with self.assertRaises(RuntimeError): socket.create_connection(('localhost',3306))
            with self.assertRaises(RuntimeError): Engine.connect(None)
        self.assertEqual(saved, (socket.socket.connect, socket.create_connection, Engine.connect))


class ReferenceIndexTests(unittest.TestCase):
    def scan(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / 'backend/app/services/consumer.py'; path.parent.mkdir(parents=True); path.write_text(text)
            return G.index_references(root, sources())

    def test_alias_reexport_and_qualified_names_have_symbol_evidence(self):
        report = self.scan('from app.models import Parent as P\nimport app.models.child as c\ndef read():\n    return query(P).join(c.Child)\n')
        refs = [r for r in report['references'] if r['symbol'] == 'read']
        self.assertEqual({r['table'] for r in refs}, {'t_parent','t_child'})
        self.assertTrue(all(r['reviewStatus'] == 'CANDIDATE' for r in refs))

    def test_strings_remain_candidates_not_sql_selectors(self):
        report = self.scan('def read():\n    return "SELECT * FROM t_child WHERE parent_id=:p"\n')
        self.assertEqual(report['references'][0]['kind'], 'TABLE_STRING_REVIEW')
        self.assertFalse(report['deletionAuthorized'])

    def test_no_references_does_not_mean_no_consumers(self):
        report = self.scan('pass\n')
        self.assertEqual(set(report['summary']['resourcesWithoutExternalReferences']), {'t_parent','t_child'})
        self.assertTrue(all(r['consumerClosure']=='UNRESOLVED' for r in report['resources']))

    def test_child_without_tenant_keeps_parent_resolution_requirement(self):
        report = self.scan('pass\n'); child = next(r for r in report['resources'] if r['table'] == 't_child')
        self.assertEqual(child['tenantScope'], 'PARENT_OR_GLOBAL_REVIEW')
        self.assertEqual(child['logicalIdFieldsToReview'], ['parent_id'])
        self.assertFalse(child['purgeAuthorized'])

    def test_dynamic_dispatch_does_not_disappear(self):
        report = self.scan('def handle():\n    return getattr(models, name)\n')
        self.assertEqual(report['dynamicDispatchSites'][0]['symbol'], 'handle')

    def test_unresolved_import_is_reported(self):
        report = self.scan('from app.unverified import Parent\n')
        self.assertEqual(report['unresolvedImports'][0]['name'], 'Parent')

    def test_scanning_never_executes_source(self):
        report = self.scan('raise RuntimeError("must never run")\n')
        self.assertFalse(report['m0Complete'])

    def test_broken_python_does_not_yield_partial_success(self):
        with self.assertRaises(SyntaxError): self.scan('def broken(:')


    def test_schema_evidence_must_match_both_sha_and_manifest(self):
        schema = {'sourceSha': SHA, 'sourceManifestHash': 'fixture', 'metadata': meta(), 'mysql': None}
        self.assertEqual(G.schema_tables(sources(), schema), {'t_parent','t_child'})
        for key in ['sourceSha', 'sourceManifestHash']:
            wrong = {**schema, key: 'wrong'}
            with self.assertRaises(ValueError): G.schema_tables(sources(), wrong)

    def test_sql_only_table_is_a_resource_even_with_no_model(self):
        schema = {'sourceSha': SHA, 'sourceManifestHash': 'fixture', 'metadata': meta(),
                  'mysql': {'tables': {**meta()['tables'], 't_sql_only': {'columns': {}}},
                            'readOnly': True, 'schemaHeads': ['migration_head']}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); target = root/'backend/alembic/versions/one.py'; target.parent.mkdir(parents=True)
            target.write_text('def upgrade():\n    op.create_table("t_sql_only")\n')
            report = G.index_references(root, sources(), schema)
        extra = next(r for r in report['resources'] if r['table'] == 't_sql_only')
        self.assertIsNone(extra['declaration']); self.assertFalse(extra['purgeAuthorized'])
        self.assertEqual(extra['consumerClosure'], 'UNRESOLVED')
        self.assertEqual(report['references'][0]['sourceKind'], 'MIGRATION')
        self.assertEqual(report['additionalSchemaResources'], ['t_sql_only'])

    def test_dynamic_metadata_tables_do_not_need_mysql_to_be_visible(self):
        rt = meta(); rt['tables']['t_dynamic'] = {'columns': {}}
        schema = {'sourceSha': SHA, 'sourceManifestHash': 'fixture', 'metadata': rt, 'mysql': None}
        with tempfile.TemporaryDirectory() as tmp:
            report = G.index_references(Path(tmp), sources(), schema)
        self.assertEqual(report['additionalSchemaResources'], ['t_dynamic'])
        self.assertFalse(report['m0Complete'])

    def test_empty_or_untrusted_schema_does_not_extend_inventory(self):
        base = {'sourceSha': SHA, 'sourceManifestHash': 'fixture', 'metadata': meta()}
        for schema in [{**base, 'metadata': {'tables': {}}}, {**base, 'mysql': {'tables': {}, 'readOnly': True}},
                       {**base, 'mysql': {'tables': meta()['tables'], 'readOnly': False, 'schemaHeads': ['x']}}]:
            with self.assertRaises(ValueError): G.schema_tables(sources(), schema)

    def test_schema_name_is_not_an_executable_selector(self):
        rt = meta(); rt['tables']['t_a;DELETE FROM t_parent'] = {'columns': {}}
        with self.assertRaises(ValueError):
            G.schema_tables(sources(), {'sourceSha': SHA, 'sourceManifestHash': 'fixture', 'metadata': rt})

    def test_empty_model_inventory_is_rejected(self):
        with self.assertRaises(ValueError): G.index_references(ROOT, {'models': []})


if __name__ == '__main__':
    unittest.main()
