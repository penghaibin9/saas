"""M0 source-completeness and paired-key regressions; no application/database I/O."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/check' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


I = load('module-commercial-inventory')
R = load('module-commercial-reconcile')
K = load('module-commercial-key-contracts')
SHA = 'a' * 40


class SourceCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for directory in ('backend/app/models', 'backend/alembic/versions', 'backend/alembic/frozen', 'shared/contracts'):
            (self.root / directory).mkdir(parents=True)
        self.put('backend/app/models/one.py', 'class Parent(Base):\n __tablename__="t_parent"\n id=mapped_column(BigInteger)\n')
        self.put('backend/alembic/versions/one.py', 'revision="one"\ndown_revision=None\n')
        self.put('backend/alembic/frozen/baseline.sql', 'CREATE TABLE t_parent(id BIGINT);\n')
        self.put('backend/alembic/env.py', '# official migration entry\n')
        self.put('backend/alembic.ini', '[alembic]\nscript_location=alembic\n')
        self.put('backend/requirements.txt', 'sqlalchemy==2.0.52\n')
        self.put('shared/contracts/module-manifest.json', json.dumps({'modules': [
            {'moduleKey': key, 'featureKey': value, 'aliases': ['graduation'] if key == 'graduationDesign' else []}
            for key, value in I.MODULE_FEATURES.items()] + [{'moduleKey': 'employment', 'featureKey': 'employment'}]}))

    def put(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')

    def evidence(self):
        return {**I.inventory(self.root), 'sourceSha': SHA}

    def test_frozen_sql_and_environment_are_fingerprinted(self):
        result = self.evidence()
        for name in ('backend/alembic/frozen/baseline.sql', 'backend/alembic/env.py', 'backend/alembic.ini', 'backend/requirements.txt'):
            self.assertIn(name, result['sourceFiles'])
        R.verify_current_inventory(self.root, result, SHA)
        self.assertFalse(result['gates']['m0Complete'])

    def test_changing_only_frozen_sql_invalidates_prior_report(self):
        result = self.evidence()
        self.put('backend/alembic/frozen/baseline.sql', 'CREATE TABLE t_other(id BIGINT);\n')
        self.assertNotEqual(result['sourceManifestHash'], self.evidence()['sourceManifestHash'])
        with self.assertRaises(ValueError):
            R.verify_current_inventory(self.root, result, SHA)

    def test_migration_helper_json_changes_fingerprint(self):
        before = self.evidence()['sourceManifestHash']
        self.put('backend/alembic/versions/decisions.json', '{"tables": []}')
        self.assertNotEqual(before, self.evidence()['sourceManifestHash'])

    def test_changed_dependency_graph_invalidates_prior_report(self):
        report = self.evidence()
        self.put('backend/requirements.txt', 'sqlalchemy==2.0.50\n')
        with self.assertRaises(ValueError):
            R.verify_current_inventory(self.root, report, SHA)

    def test_new_unlisted_model_is_not_hidden_by_old_manifest(self):
        report = self.evidence()
        self.put('backend/app/models/two.py', 'class Child(Base):\n __tablename__="t_child"\n')
        R.verify_source(self.root, report, SHA)  # Individual old files are unchanged.
        with self.assertRaisesRegex(ValueError, 'RECOLLECTION'):
            R.verify_current_inventory(self.root, report, SHA)

    def test_self_consistent_partial_manifest_is_rejected(self):
        report = self.evidence()
        del report['sourceFiles']['backend/alembic/frozen/baseline.sql']
        report['sourceManifestHash'] = I.digest(report['sourceFiles'])
        R.verify_source(self.root, report, SHA)
        with self.assertRaisesRegex(ValueError, 'RECOLLECTION'):
            R.verify_current_inventory(self.root, report, SHA)

    def test_model_payload_tamper_cannot_keep_a_valid_file_manifest(self):
        for key, value in [('models', []), ('staticMigrationHeads', ['other']), ('moduleMapping', {}), ('additionalTableSites', [{}])]:
            report = self.evidence()
            report[key] = value
            with self.assertRaisesRegex(ValueError, 'RECOLLECTION'):
                R.verify_current_inventory(self.root, report, SHA)

    def test_schema_symlink_is_reported_not_read(self):
        target = self.root / 'outside.sql'
        target.write_text('DO NOT READ')
        (self.root / 'backend/alembic/frozen/link.sql').symlink_to(target)
        result = self.evidence()
        self.assertNotIn('backend/alembic/frozen/link.sql', result['sourceFiles'])
        self.assertEqual(result['gates']['staticScan'], 'FAIL')

    def test_unknown_schema_asset_blocks_instead_of_vanishing(self):
        self.put('backend/alembic/frozen/unreviewed.csv', 'unreviewed data')
        result = self.evidence()
        self.assertEqual(result['gates']['staticScan'], 'FAIL')
        with self.assertRaises(ValueError):
            R.verify_current_inventory(self.root, result, SHA)

    def test_schema_dependency_symlink_is_not_read(self):
        path = self.root / 'backend/requirements.txt'
        path.unlink()
        path.symlink_to(self.root / 'backend/alembic/frozen/baseline.sql')
        result = self.evidence()
        self.assertNotIn('backend/requirements.txt', result['sourceFiles'])
        self.assertEqual(result['gates']['staticScan'], 'FAIL')


class KeyContractTests(unittest.TestCase):
    def metadata(self, composite=True, ondelete=None):
        from sqlalchemy import BigInteger, Column, ForeignKey, ForeignKeyConstraint, MetaData, Table, UniqueConstraint
        metadata = MetaData()
        Table('t_parent', metadata, Column('tenant_id', BigInteger, primary_key=True), Column('id', BigInteger, primary_key=True))
        args = [Column('id', BigInteger, primary_key=True), Column('tenant_id', BigInteger), Column('parent_id', BigInteger)]
        if composite:
            args.append(ForeignKeyConstraint(['tenant_id', 'parent_id'], ['t_parent.tenant_id', 't_parent.id'], name='paired', ondelete=ondelete))
        else:
            args[1].append_foreign_key(ForeignKey('t_parent.tenant_id'))
            args[2].append_foreign_key(ForeignKey('t_parent.id'))
        args.append(UniqueConstraint('tenant_id', 'parent_id', name='one_parent'))
        return K.metadata_contract(Table('t_child', metadata, *args))

    def physical(self, delete='RESTRICT', paired=True):
        fk = [('t_child', 'db_pair', 1, 'tenant_id', 'audit', 't_parent', 'tenant_id', delete, 'RESTRICT'),
              ('t_child', 'db_pair' if paired else 'db_other', 2 if paired else 1, 'parent_id', 'audit', 't_parent', 'id', delete, 'RESTRICT')]
        indexes = [('t_child', 'PRIMARY', 0, 1, 'id', None, None, 'A'),
                   ('t_child', 'db_unique', 0, 1, 'tenant_id', None, None, 'A'),
                   ('t_child', 'db_unique', 0, 2, 'parent_id', None, None, 'A')]
        return K.mysql_contracts(['t_child'], fk, indexes, 'audit')['t_child']

    def test_real_sqlalchemy_composite_and_separate_keys_are_not_equivalent(self):
        self.assertEqual(K.compare(self.metadata(), self.physical())['status'], 'MATCH')
        self.assertIn('foreignKeys', K.compare(self.metadata(False), self.physical())['differences'])
        self.assertIn('foreignKeys', K.compare(self.metadata(), self.physical(paired=False))['differences'])

    def test_cascade_changes_are_not_hidden_by_same_column_pairs(self):
        self.assertEqual(K.compare(self.metadata(), self.physical('CASCADE'))['status'], 'REVIEW_REQUIRED')
        self.assertEqual(K.compare(self.metadata(ondelete='CASCADE'), self.physical('CASCADE'))['status'], 'MATCH')

    def test_constraint_names_do_not_cause_false_semantic_differences(self):
        self.assertEqual(K.compare(self.metadata(), self.physical())['status'], 'MATCH')

    def test_default_no_action_and_restrict_match(self):
        self.assertEqual(K.compare(self.metadata(ondelete='NO ACTION'), self.physical())['status'], 'MATCH')

    def test_primary_key_order_is_compared(self):
        before = self.physical()
        before['primaryKey'] = ['id', 'tenant_id']
        after = copy.deepcopy(before)
        after['primaryKey'].reverse()
        self.assertIn('primaryKey', K.compare(before, after)['differences'])

    def test_cross_schema_target_is_not_treated_as_local(self):
        after = self.physical()
        after['foreignKeys'][0]['targets'][0]['schema'] = 'another_school_db'
        self.assertIn('foreignKeys', K.compare(self.metadata(), after)['differences'])

    def test_unique_key_removed_is_explicit(self):
        after = self.physical()
        after['uniqueKeys'] = []
        self.assertIn('uniqueKeys', K.compare(self.metadata(), after)['differences'])

    def test_unique_prefix_length_is_not_full_column_uniqueness(self):
        after = self.physical()
        after['uniqueKeys'][0]['parts'][0]['prefixLength'] = 8
        self.assertIn('uniqueKeys', K.compare(self.metadata(), after)['differences'])

    def test_nonunique_index_does_not_become_uniqueness(self):
        keys = K.mysql_contracts(['t_child'], [], [('t_child', 'lookup', 1, 1, 'tenant_id', None, None, 'A')], 'audit')
        self.assertEqual(keys['t_child']['uniqueKeys'], [])

    def test_reordered_rows_keep_member_ordinal(self):
        rows = [('t_child', 'fk', 2, 'parent_id', 'audit', 't_parent', 'id', 'RESTRICT', 'RESTRICT'),
                ('t_child', 'fk', 1, 'tenant_id', 'audit', 't_parent', 'tenant_id', 'RESTRICT', 'RESTRICT')]
        self.assertEqual(K.mysql_contracts(['t_child'], rows, [], 'audit')['t_child']['foreignKeys'][0]['columns'], ['tenant_id', 'parent_id'])

    def test_incomplete_fk_evidence_is_not_accepted(self):
        rows = [('t_child', 'fk', 2, 'parent_id', 'audit', 't_parent', 'id', 'RESTRICT', 'RESTRICT')]
        with self.assertRaises(ValueError):
            K.mysql_contracts(['t_child'], rows, [], 'audit')

    def test_duplicate_fk_and_index_position_rejected(self):
        fk = ('t_child', 'fk', 1, 'parent_id', 'audit', 't_parent', 'id', 'RESTRICT', 'RESTRICT')
        index = ('t_child', 'ix', 0, 1, 'id', None, None, 'A')
        with self.assertRaises(ValueError): K.mysql_contracts(['t_child'], [fk, fk], [], 'audit')
        with self.assertRaises(ValueError): K.mysql_contracts(['t_child'], [], [index, index], 'audit')

    def test_missing_old_artifact_data_is_not_a_match(self):
        self.assertEqual(K.compare(None, self.physical())['status'], 'NOT_COLLECTED')
        self.assertEqual(K.compare({}, {})['status'], 'NOT_COLLECTED')

    def test_boolean_contract_version_does_not_claim_evidence(self):
        value = self.physical()
        value['version'] = True
        self.assertEqual(K.compare(value, self.physical())['status'], 'NOT_COLLECTED')

    def test_missing_cascade_action_is_not_invented_as_restrict(self):
        value = self.physical()
        del value['foreignKeys'][0]['onDelete']
        with self.assertRaises(ValueError): K.signatures(value)

    def test_malformed_key_parts_fail_closed(self):
        for kind in ('target', 'column', 'prefix', 'primary', 'direction'):
            value = self.physical()
            if kind == 'target': value['foreignKeys'][0]['targets'][0]['table'] = ''
            if kind == 'column': value['foreignKeys'][0]['columns'][0] = None
            if kind == 'prefix': value['uniqueKeys'][0]['parts'][0]['prefixLength'] = True
            if kind == 'primary': value['primaryKey'] = ['id', 'id']
            if kind == 'direction': value['uniqueKeys'][0]['parts'][0]['direction'] = 'UNKNOWN'
            with self.subTest(kind=kind), self.assertRaises(ValueError): K.signatures(value)

    def test_expression_index_requires_review_even_when_text_matches(self):
        value = self.physical()
        value['unsupported'] = ['EXPRESSION_INDEX_REQUIRES_REVIEW']
        self.assertEqual(K.compare(value, value)['status'], 'REVIEW_REQUIRED')

    def test_invalid_paired_keys_are_rejected(self):
        value = self.physical()
        value['foreignKeys'][0]['targets'].pop()
        with self.assertRaises(ValueError): K.signatures(value)

    def test_missing_key_contract_blocks_reconcile_agreement(self):
        source = {'models': [{'table': 't_child', 'inheritedFieldNames': ['id']}], 'staticMigrationHeads': ['head']}
        rt = {'tables': {'t_child': {'columns': {'id': {'nullable': False, 'primaryKey': True}}, 'foreignKeys': []}}}
        db = {**copy.deepcopy(rt), 'readOnly': True, 'schemaHeads': ['head']}
        result = R.reconcile(source, rt, db)
        self.assertEqual(result['runtimeMysqlKeyContracts'][0]['status'], 'NOT_COLLECTED')
        self.assertEqual(result['coverageStatus'], 'REVIEW_REQUIRED')
        self.assertFalse(result['m0Complete'])


if __name__ == '__main__':
    unittest.main()
