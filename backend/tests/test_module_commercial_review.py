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

    def test_reanchor_receipt_only_relocates_stale_evidence_after_reviewed_window(self):
        old = b'changed\nanchor\n'
        old_sha = hashlib.sha256(old).hexdigest()
        self.path.write_text('changed-a\nchanged-b\nanchor\n')
        current_sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        review = {
            'evidence': {
                'E1': {'path': 'model.py', 'sha256': old_sha, 'startLine': 2, 'endLine': 2},
            },
        }
        receipt = {
            'schemaVersion': 1,
            'artifactType': 'M0_SCHEMA_EVIDENCE_REANCHORS_NOT_APPROVAL',
            'deletionAuthorized': False,
            'purgeAuthorized': False,
            'entries': [{
                'path': 'model.py',
                'fromSha256': old_sha,
                'toSha256': current_sha,
                'sourceChangeCommit': 'b' * 40,
                'lineOffset': 1,
                'changeWindow': {'oldStart': 1, 'oldEnd': 1, 'newStart': 1, 'newEnd': 2},
                'evidenceIds': ['E1'],
                'reason': 'one reviewed line inserted before unchanged evidence',
            }],
        }
        resolved = D.validate_review_evidence(self.root, {'model.py': current_sha}, review, receipt)
        self.assertEqual(resolved['E1']['startLine'], 3)
        self.assertEqual(resolved['E1']['endLine'], 3)
        self.assertTrue(resolved['E1']['reanchored'])

        for field in ('deletionAuthorized', 'purgeAuthorized'):
            bad = copy.deepcopy(receipt)
            bad[field] = True
            with self.assertRaises(ValueError):
                D.validate_review_evidence(self.root, {'model.py': current_sha}, review, bad)

        overlap = copy.deepcopy(receipt)
        overlap['entries'][0]['changeWindow']['oldEnd'] = 2
        overlap['entries'][0]['changeWindow']['newEnd'] = 3
        with self.assertRaisesRegex(ValueError, 'OVERLAPS'):
            D.validate_review_evidence(self.root, {'model.py': current_sha}, review, overlap)

        incomplete = copy.deepcopy(receipt)
        incomplete['entries'][0]['evidenceIds'] = ['OTHER']
        with self.assertRaises(ValueError):
            D.validate_review_evidence(self.root, {'model.py': current_sha}, review, incomplete)

    def test_reanchor_can_partition_unchanged_evidence_before_and_after_change_window(self):
        old = b'before\nchanged\nafter\n'
        old_sha = hashlib.sha256(old).hexdigest()
        self.path.write_text('before\nchanged-a\nchanged-b\nafter\n')
        current_sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        review = {
            'evidence': {
                'E0': {'path': 'model.py', 'sha256': old_sha, 'startLine': 1, 'endLine': 1},
                'E1': {'path': 'model.py', 'sha256': old_sha, 'startLine': 3, 'endLine': 3},
            },
        }
        base = {
            'path': 'model.py',
            'fromSha256': old_sha,
            'toSha256': current_sha,
            'sourceChangeCommit': 'c' * 40,
            'changeWindow': {'oldStart': 2, 'oldEnd': 2, 'newStart': 2, 'newEnd': 3},
        }
        receipt = {
            'schemaVersion': 1,
            'artifactType': 'M0_SCHEMA_EVIDENCE_REANCHORS_NOT_APPROVAL',
            'deletionAuthorized': False,
            'purgeAuthorized': False,
            'entries': [
                {**base, 'lineOffset': 0, 'evidenceIds': ['E0'], 'reason': 'unchanged evidence before the reviewed source window'},
                {**base, 'lineOffset': 1, 'evidenceIds': ['E1'], 'reason': 'unchanged evidence after the reviewed source window'},
            ],
        }
        resolved = D.validate_review_evidence(self.root, {'model.py': current_sha}, review, receipt)
        self.assertEqual(resolved['E0']['startLine'], 1)
        self.assertEqual(resolved['E1']['startLine'], 4)
        self.assertEqual(set(resolved), {'E0', 'E1'})

        bad = copy.deepcopy(receipt)
        bad['entries'][0]['lineOffset'] = 1
        with self.assertRaisesRegex(ValueError, 'OFFSET_MISMATCH'):
            D.validate_review_evidence(self.root, {'model.py': current_sha}, review, bad)

    def multi_window_fixture(self):
        old = b'old-head\nanchor\nold-tail\n'
        self.path.write_text('new-head-a\nnew-head-b\nanchor\nnew-tail-a\nnew-tail-b\n')
        current_sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        review = {'evidence': {'E1': {
            'path': 'model.py', 'sha256': hashlib.sha256(old).hexdigest(),
            'startLine': 2, 'endLine': 2,
        }}}
        receipt = {
            'schemaVersion': 1, 'artifactType': 'M0_SCHEMA_EVIDENCE_REANCHORS_NOT_APPROVAL',
            'deletionAuthorized': False, 'purgeAuthorized': False,
            'entries': [{
                'path': 'model.py', 'fromSha256': hashlib.sha256(old).hexdigest(),
                'toSha256': current_sha, 'sourceChangeCommit': 'b' * 40,
                'lineOffset': 1, 'evidenceIds': ['E1'],
                'evidenceRangeSha256': {'E1': hashlib.sha256(b'anchor\n').hexdigest()},
                'changeWindows': [
                    {'oldStart': 1, 'oldEnd': 1, 'newStart': 1, 'newEnd': 2},
                    {'oldStart': 3, 'oldEnd': 3, 'newStart': 4, 'newEnd': 5},
                ],
                'reason': 'reviewed edits before and after byte-identical evidence',
            }],
        }
        return current_sha, review, receipt

    def test_reanchor_between_disjoint_edits_preserves_bytes_and_approval_boundary(self):
        sha, review, receipt = self.multi_window_fixture()
        resolved = D.validate_review_evidence(self.root, {'model.py': sha}, review, receipt)
        self.assertEqual(resolved['E1']['startLine'], 3)
        self.assertEqual(resolved['E1']['endLine'], 3)
        for flag in ('deletionAuthorized', 'purgeAuthorized'):
            bad = copy.deepcopy(receipt)
            bad[flag] = True
            with self.assertRaisesRegex(ValueError, 'NOT_REVIEW_ONLY'):
                D.validate_review_evidence(self.root, {'model.py': sha}, review, bad)

    def test_multi_window_reanchor_cannot_hide_changed_evidence(self):
        sha, review, receipt = self.multi_window_fixture()
        self.path.write_text(self.path.read_text().replace('anchor', 'edited'))
        sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        receipt['entries'][0]['toSha256'] = sha
        with self.assertRaisesRegex(ValueError, 'EVIDENCE_CONTENT_CHANGED'):
            D.validate_review_evidence(self.root, {'model.py': sha}, review, receipt)

    def test_multi_window_reanchor_rejects_missing_hash_overlap_and_inconsistent_windows(self):
        sha, review, receipt = self.multi_window_fixture()
        mutations = [
            lambda r: r.pop('evidenceRangeSha256'),
            lambda r: r.update(changeWindow=r['changeWindows'][0]),
            lambda r: r.update(changeWindows=[]),
            lambda r: r.update(changeWindows=list(reversed(r['changeWindows']))),
            lambda r: r['changeWindows'][1].update(newStart=3),
            lambda r: r['changeWindows'][1].update(oldStart=2, newStart=3),
            lambda r: r['changeWindows'][1].update(oldStart=True),
            lambda r: r.update(lineOffset=3),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(receipt)
                mutation(bad['entries'][0])
                with self.assertRaises(ValueError):
                    D.validate_review_evidence(self.root, {'model.py': sha}, review, bad)

    def test_committed_recruitment_reanchor_requires_complete_stale_coverage(self):
        review = D.unique_json((ROOT / 'docs/07-部署运维交付与商业化/module-commerce/M0-schema-dispositions.json').read_text())
        receipts = D.unique_json((ROOT / 'docs/07-部署运维交付与商业化/module-commerce/M0-schema-evidence-reanchors.json').read_text())
        files = {v['path']: hashlib.sha256((ROOT / v['path']).read_bytes()).hexdigest()
                 for v in review['evidence'].values()}
        resolved = D.validate_review_evidence(ROOT, files, review, receipts)
        self.assertEqual((resolved['S158']['startLine'], resolved['S158']['endLine']), (175, 191))
        receipts['entries'] = [r for r in receipts['entries'] if 'S158' not in r['evidenceIds']]
        with self.assertRaisesRegex(ValueError, 'STALE_EVIDENCE_COVERAGE_MISMATCH'):
            D.validate_review_evidence(ROOT, files, review, receipts)

    def test_committed_review_has_unique_cases_and_valid_anchored_source(self):
        review = D.unique_json((ROOT / 'docs/07-部署运维交付与商业化/module-commerce/M0-schema-dispositions.json').read_text(encoding='utf-8'))
        reanchors = D.unique_json((ROOT / 'docs/07-部署运维交付与商业化/module-commerce/M0-schema-evidence-reanchors.json').read_text(encoding='utf-8'))
        self.assertEqual(len(review['cases']), len({c['table'] for c in review['cases']}))
        for row in review['cases']:
            self.assertFalse(row['purgeAuthorized'])
            self.assertFalse(row['remediationComplete'])
            self.assertTrue(row['evidence'])
            self.assertIn(row['code'], review['decisions'])
        source_files = {}
        for anchor in review['evidence'].values():
            path = ROOT / anchor['path']
            source_files[anchor['path']] = hashlib.sha256(path.read_bytes()).hexdigest()
        resolved = D.validate_review_evidence(ROOT, source_files, review, reanchors)
        self.assertEqual(set(resolved), set(review['evidence']))
        self.assertEqual(sum(1 for item in resolved.values() if item['reanchored']), 17)
        self.assertFalse(reanchors['deletionAuthorized'])
        self.assertFalse(reanchors['purgeAuthorized'])
        for anchor in resolved.values():
            content = (ROOT / anchor['path']).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), anchor['sha256'])
            self.assertTrue(1 <= anchor['startLine'] <= anchor['endLine'] <= len(content.decode('utf-8-sig').splitlines()))


if __name__ == '__main__':
    unittest.main()
