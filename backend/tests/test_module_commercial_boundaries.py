"""M0 boundary source assertions and rejection paths; synthetic schema is not MySQL."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'docs/07-部署运维交付与商业化/module-commerce/M0-resource-boundaries.json'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts/check'/(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


B = load('module-commercial-boundaries')
I = load('module-commercial-inventory')


class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_base = {**I.inventory(ROOT), 'sourceSha': 'a'*40}
        cls.contract_base = B.unique_json(CONTRACT.read_text(encoding='utf-8'))
        # Fake metadata/physical structures exercise validation only. The workflow
        # independently executes the same command against migrated MySQL evidence.
        tables = {row['table']: {'columns': {name: {} for name in row['inheritedFieldNames']}}
                  for row in cls.source_base['models']}
        runtime, physical = copy.deepcopy(tables), copy.deepcopy(tables)
        for row in cls.contract_base['exceptionalTables']:
            for target, key in ((runtime,'metadata'), (physical,'mysql')):
                if row['presence'][key]:
                    target.setdefault(row['table'], {'columns': {'id': {}, 'tenant_id': {}}})
                else: target.pop(row['table'], None)
        for row in cls.contract_base['noTenantResources']:
            if row['table'] not in tables:
                physical[row['table']] = {'columns': {name: {} for name in row['requiredFields']}}
        cls.schema_base = {'sourceSha':'a'*40, 'sourceManifestHash':cls.source_base['sourceManifestHash'],
            'comparison':{'runtimeMysqlKeyContracts':[copy.deepcopy(row['observation']) for row in cls.contract_base['keyDispositions']]},'collectionStatus':'PASS','metadata':{'tables': runtime},
            'mysql':{'tables': physical, 'readOnly':True,'readerSelectOnly':True,'businessRowsRead':False}}

    def setUp(self):
        self.source = copy.deepcopy(self.source_base)
        self.schema = copy.deepcopy(self.schema_base)
        self.contract = copy.deepcopy(self.contract_base)

    def run_assess(self):
        return B.assess(ROOT, self.source, self.schema, self.contract)

    def test_current_source_assertions_do_not_approve_stage_or_deletion(self):
        result = self.run_assess()
        self.assertEqual(result['status'], 'STRUCTURAL_BOUNDARY_ASSERTIONS_VERIFIED')
        for name in ('m0Complete','m1EntryApproved','deletionAuthorized'): self.assertIs(result[name], False)
        self.assertEqual(result['counts']['noTenantBoundaries'], len(self.contract['noTenantResources']))
        self.assertTrue(result['remaining'])

    def test_missing_no_tenant_entry_is_not_implicitly_ignored(self):
        self.contract['noTenantResources'].pop()
        with self.assertRaisesRegex(ValueError,'COVERAGE_CHANGED'): self.run_assess()

    def test_new_no_tenant_table_requires_review(self):
        self.schema['mysql']['tables']['t_new_no_tenant'] = {'columns': {'id':{}}}
        with self.assertRaisesRegex(ValueError,'COVERAGE_CHANGED'): self.run_assess()

    def test_new_sql_only_tenant_table_requires_exception_disposition(self):
        self.schema['mysql']['tables']['t_new_sql_only'] = {'columns': {'id':{},'tenant_id':{}}}
        with self.assertRaisesRegex(ValueError,'EXCEPTIONAL_RESOURCE_COVERAGE_CHANGED'): self.run_assess()

    def test_later_todo_integration_invalidates_unregistered_disposition(self):
        self.schema['mysql']['tables']['t_todo_work_assignment'] = copy.deepcopy(self.schema_base['mysql']['tables']['t_tenant'])
        with self.assertRaises(ValueError): self.run_assess()

    def test_presence_cannot_be_integer_truthiness(self):
        self.contract['exceptionalTables'][0]['presence']['ast'] = 1
        with self.assertRaises(ValueError): self.run_assess()

    def test_duplicate_boundary_table_is_rejected(self):
        self.contract['noTenantResources'].append(copy.deepcopy(self.contract['noTenantResources'][0]))
        with self.assertRaisesRegex(ValueError,'DUPLICATE'): self.run_assess()

    def test_unknown_parent_and_missing_scope_field_are_rejected(self):
        for field,value in [('relatedTables',['t_unknown_parent']),('requiredFields',['invented_scope_id'])]:
            self.contract = copy.deepcopy(self.contract_base)
            self.contract['noTenantResources'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'RELATION_CHANGED'): self.run_assess()

    def test_scope_review_cannot_claim_implemented_selector(self):
        self.contract['noTenantResources'][0]['selectorImplemented'] = True
        with self.assertRaisesRegex(ValueError,'SCOPE_CONTRACT'): self.run_assess()

    def test_missing_or_wrong_review_evidence_is_rejected(self):
        self.contract['noTenantResources'][0]['evidence'] = ['absent']
        with self.assertRaises(ValueError): self.run_assess()

    def test_unrelated_valid_anchor_cannot_prove_a_table(self):
        self.contract['noTenantResources'][0]['evidence'] = self.contract['sharedFoundation'][0]['evidence']
        with self.assertRaisesRegex(ValueError,'NOT_IN_SOURCE_ANCHOR'): self.run_assess()

    def test_wrong_source_manifest_or_sha_is_rejected(self):
        for key in ('sourceSha','sourceManifestHash'):
            self.schema = copy.deepcopy(self.schema_base); self.schema[key] = 'wrong'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'IDENTITY_MISMATCH'): self.run_assess()

    def test_drifted_source_hash_is_rejected(self):
        next(iter(self.contract['evidence'].values()))['sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError,'ANCHOR_CHANGED'): self.run_assess()

    def test_invalid_range_and_wrong_symbol_are_rejected(self):
        for field,value in [('startLine',True),('endLine',10000000),('symbol','InventedSymbol')]:
            self.contract = copy.deepcopy(self.contract_base)
            next(iter(self.contract['evidence'].values()))[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_assess()

    def test_unsafe_source_path_is_rejected(self):
        next(iter(self.contract['evidence'].values()))['path'] = '../outside.py'
        with self.assertRaisesRegex(ValueError,'UNSAFE'): self.run_assess()

    def test_untested_consumer_cannot_be_promoted_to_runtime_pass(self):
        self.contract['consumerCheckpoints'][0]['runtimeRetirementTest'] = 'PASS'
        with self.assertRaisesRegex(ValueError,'CONSUMER'): self.run_assess()

    def test_stage_and_access_flags_are_strict_false(self):
        for field in ('implicitEmployment','implicitApiAccess','consumerClosureComplete','m0Complete','m1EntryApproved','deletionAuthorized'):
            for value in (True,0,'false',None):
                self.contract = copy.deepcopy(self.contract_base);self.contract[field]=value
                with self.subTest(field=field,value=value), self.assertRaises(ValueError): self.run_assess()

    def test_row_cannot_authorize_purge(self):
        self.contract['noTenantResources'][0]['purgeAuthorized'] = True
        with self.assertRaises(ValueError): self.run_assess()

    def test_shared_master_cannot_be_removed_or_deleted(self):
        self.contract['sharedFoundation'].pop()
        with self.assertRaisesRegex(ValueError,'COVERAGE_CHANGED'): self.run_assess()
        self.contract = copy.deepcopy(self.contract_base)
        self.contract['sharedFoundation'][0]['onModuleExit'] = 'DELETE'
        with self.assertRaisesRegex(ValueError,'PRESERVED'): self.run_assess()

    def test_module_alias_cannot_create_another_paid_module(self):
        self.contract['canonicalFeatures']['graduation'] = 'graduation'
        with self.assertRaisesRegex(ValueError,'MAPPING_CHANGED'): self.run_assess()

    def test_writable_or_business_row_evidence_is_rejected(self):
        for field,value in [('readOnly',False),('readerSelectOnly',False),('businessRowsRead',True)]:
            self.schema = copy.deepcopy(self.schema_base);self.schema['mysql'][field]=value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'READ_ONLY'): self.run_assess()

    def test_key_disposition_does_not_hide_missing_unique_index(self):
        self.schema['comparison']['runtimeMysqlKeyContracts'][0]['differences']['uniqueKeys']['mysql'] = []
        with self.assertRaisesRegex(ValueError,'KEY_OBSERVATION_CHANGED'): self.run_assess()

    def test_new_key_difference_requires_explicit_review(self):
        self.schema['comparison']['runtimeMysqlKeyContracts'].append({'table':'t_user','status':'REVIEW_REQUIRED','differences':{}})
        with self.assertRaisesRegex(ValueError,'KEY_DISPOSITION_COVERAGE_CHANGED'): self.run_assess()

    def test_disposition_is_not_schema_remediation(self):
        self.contract['keyDispositions'][0]['remediationComplete'] = True
        with self.assertRaisesRegex(ValueError,'KEY_OBSERVATION_CHANGED'): self.run_assess()

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ValueError): B.unique_json('{"m0Complete":false,"m0Complete":true}')


if __name__ == '__main__':
    unittest.main()
