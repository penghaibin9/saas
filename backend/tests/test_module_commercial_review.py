"""Schema review receipts cannot authorize runtime changes or hide source drift."""
import copy
import hashlib
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


D = load('module-commercial-review')
R = load('module-commercial-reconcile')
I = load('module-commercial-inventory')
SHA = 'a' * 40


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'model.py'
        self.path.write_text('pass\n')
        files = {'model.py': hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.source = {'sourceSha': SHA, 'sourceFiles': files, 'sourceManifestHash': I.digest(files),
            'models': [{'table': 't_child', 'inheritedFieldNames': ['id', 'created_at']}], 'staticMigrationHeads': ['head']}
        table = {'columns': {'id': {'type': 'BIGINT', 'nullable': False, 'primaryKey': True},
                            'created_at': {'type': 'DATETIME', 'nullable': False, 'primaryKey': False}}, 'foreignKeys': [],
                 'keyContract': {'version': 1, 'primaryKey': ['id'], 'foreignKeys': [], 'uniqueKeys': [], 'unsupported': []}}
        self.schema = {'sourceSha': SHA, 'sourceManifestHash': self.source['sourceManifestHash'], 'collectionStatus': 'PASS',
            'metadata': {'tables': {'t_child': table}}, 'mysql': {'tables': {'t_child': copy.deepcopy(table)},
                'readOnly': True, 'readerSelectOnly': True, 'businessRowsRead': False, 'schemaHeads': ['head']}}
        self.schema['mysql']['tables']['t_child']['columns']['created_at']['nullable'] = True
        self.compare()
        difference = self.schema['comparison']['runtimeMysqlColumns'][0]
        self.review = {'schemaVersion': 1, 'artifactType': 'M0_SCHEMA_DISPOSITIONS_NOT_APPROVAL',
            'reviewedApplicationSha': SHA, 'deletionAuthorized': False,
            'decisions': {'TIME': {'reason': 'nullable migration', 'handling': 'keep existing schema', 'nextCheck': 'check null origin before any retention decision'}},
            'cases': [{'table': 't_child', 'code': 'TIME', 'observationHash': D.digest(D.column_observation(self.schema, difference)),
                'evidence': ['E1'], 'remediationComplete': False, 'purgeAuthorized': False}],
            'evidence': {'E1': {'path': 'model.py', 'sha256': files['model.py'], 'startLine': 1, 'endLine': 1}}}

    def compare(self):
        self.schema['comparison'] = R.reconcile(self.source, self.schema['metadata'], self.schema['mysql'])

    def assess(self):
        return D.assess(self.root, self.source, self.schema, self.review)

    def test_valid_disposition_is_not_fix_stage_approval_or_deletion(self):
        result = self.assess()
        self.assertEqual(result['counts'], {'DISPOSITION_VERIFIED': 1})
        self.assertEqual(result['status'], 'DISPOSITIONS_VERIFIED_NOT_REMEDIATED')
        for key in ('m0Complete', 'm1EntryApproved', 'deletionAuthorized'):
            self.assertFalse(result[key])

    def test_changed_source_anchor_is_rejected(self):
        self.path.write_text('changed\n')
        with self.assertRaises(ValueError): self.assess()

    def test_wrong_source_sha_and_manifest_are_rejected(self):
        for field in ('sourceSha', 'sourceManifestHash'):
            original = self.schema[field]
            self.schema[field] = 'wrong'
            with self.assertRaises(ValueError): self.assess()
            self.schema[field] = original

    def test_copied_comparison_cannot_hide_a_real_difference(self):
        self.schema['comparison']['runtimeMysqlColumns'] = []
        with self.assertRaisesRegex(ValueError, 'TAMPERED'): self.assess()

    def test_changed_column_type_expires_the_old_disposition(self):
        self.schema['mysql']['tables']['t_child']['columns']['created_at']['type'] = 'TEXT'
        self.compare()
        self.assertEqual(self.assess()['counts'], {'SOURCE_OR_SCHEMA_CHANGED': 1})

    def test_new_column_difference_is_not_covered_by_old_case(self):
        self.schema['mysql']['tables']['t_child']['columns']['extra'] = {'type': 'INTEGER', 'nullable': True, 'primaryKey': False}
        self.compare()
        self.assertEqual(self.assess()['status'], 'REVIEW_REQUIRED')

    def test_missing_disposition_never_defaults_to_approved(self):
        self.review['cases'][0]['table'] = 't_elsewhere'
        result = self.assess()
        self.assertEqual(result['counts'], {'UNREVIEWED': 1})
        self.assertEqual(result['retiredOrChangedReviewCases'], ['t_elsewhere'])

    def test_resolved_column_difference_requires_review_record_update(self):
        self.schema['mysql']['tables']['t_child']['columns']['created_at']['nullable'] = False
        self.compare()
        result = self.assess()
        self.assertEqual(result['retiredOrChangedReviewCases'], ['t_child'])
        self.assertEqual(result['status'], 'REVIEW_REQUIRED')

    def test_duplicate_table_and_json_keys_are_rejected(self):
        self.review['cases'].append(copy.deepcopy(self.review['cases'][0]))
        with self.assertRaises(ValueError): self.assess()
        with self.assertRaises(ValueError): D.unique_json('{"a":1,"a":2}')

    def test_review_cannot_turn_into_purge_approval(self):
        for name in ('purgeAuthorized', 'remediationComplete'):
            self.review['cases'][0][name] = True
            with self.assertRaises(ValueError): self.assess()
            self.review['cases'][0][name] = False
        self.review['deletionAuthorized'] = True
        with self.assertRaises(ValueError): self.assess()

    def test_unsafe_table_or_evidence_path_is_rejected(self):
        self.review['cases'][0]['table'] = 't_x;DROP TABLE t_child'
        with self.assertRaises(ValueError): self.assess()
        self.review['cases'][0]['table'] = 't_child'
        self.review['evidence']['E1']['path'] = '../outside'
        with self.assertRaises(ValueError): self.assess()

    def test_missing_evidence_and_invalid_line_ranges_are_rejected(self):
        self.review['cases'][0]['evidence'] = ['nonexistent']
        with self.assertRaises(ValueError): self.assess()
        self.review['cases'][0]['evidence'] = ['E1']
        for start, end in [(0, 1), (1, 2), (2, 1), (True, 1)]:
            self.review['evidence']['E1'].update(startLine=start, endLine=end)
            with self.assertRaises(ValueError): self.assess()

    def test_uncollected_or_business_data_evidence_is_rejected(self):
        for key, value in [('readerSelectOnly', False), ('businessRowsRead', True)]:
            old = self.schema['mysql'][key]
            self.schema['mysql'][key] = value
            with self.assertRaises(ValueError): self.assess()
            self.schema['mysql'][key] = old

    def test_unique_drift_not_suppressed_by_reviewed_nullability(self):
        self.schema['mysql']['tables']['t_child']['keyContract']['uniqueKeys'] = [{
            'name': 'unique_created', 'parts': [{'column': 'created_at', 'prefixLength': None, 'expression': None, 'direction': 'ASC'}]}]
        self.compare()
        result = self.assess()
        self.assertEqual(result['counts']['DISPOSITION_VERIFIED'], 1)
        self.assertEqual(result['keyContractReviewRequired'], 1)
        self.assertFalse(result['m0Complete'])

    def test_committed_review_has_unique_cases_and_valid_anchored_source(self):
        review = D.unique_json((ROOT / 'docs/07-部署运维交付与商业化/module-commerce/M0-schema-dispositions.json').read_text(encoding='utf-8'))
        self.assertEqual(len(review['cases']), len({c['table'] for c in review['cases']}))
        for row in review['cases']:
            self.assertFalse(row['purgeAuthorized'])
            self.assertFalse(row['remediationComplete'])
            self.assertTrue(row['evidence'])
            self.assertIn(row['code'], review['decisions'])
        for anchor in review['evidence'].values():
            content = (ROOT / anchor['path']).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), anchor['sha256'])
            self.assertTrue(1 <= anchor['startLine'] <= anchor['endLine'] <= len(content.decode('utf-8-sig').splitlines()))


if __name__ == '__main__':
    unittest.main()
