"""Pure read-only M0 scanner tests; no application imports or database fixtures."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/check/module-commercial-inventory.py'
spec = importlib.util.spec_from_file_location('commerce_inventory', SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ('backend/app/models', 'backend/alembic/versions', 'shared/contracts'):
            (self.root / directory).mkdir(parents=True)
        self.write('backend/app/models/test.py', '''
raise RuntimeError("must never execute business code")
class TenantMixin:
    tenant_id: int = mapped_column(BigInteger)
class Indirect(TenantMixin):
    pass
class Student(Indirect, Base):
    __tablename__ = "t_student"
    id: int = mapped_column(BigInteger)
class Child(Base):
    __tablename__ = "t_child"
    parent_id = Column(BigInteger, ForeignKey("t_student.id"))
''')
        self.write('backend/alembic/versions/one.py', 'revision = "r1"\ndown_revision = None\n')
        self.manifest = {'modules': [
            {'moduleKey': key, 'featureKey': feature, 'aliases': ['graduation'] if key == 'graduationDesign' else []}
            for key, feature in scanner.MODULE_FEATURES.items()
        ] + [{'moduleKey': 'employment', 'featureKey': 'employment'}]}
        self.write_manifest()

    def write(self, name, content):
        (self.root / name).write_text(content, encoding='utf-8')

    def write_manifest(self):
        self.write('shared/contracts/module-manifest.json', json.dumps(self.manifest))

    def test_scan_does_not_import_or_execute_application(self):
        result = scanner.inventory(self.root)
        self.assertEqual(result['summary']['uniqueTables'], 2)
        self.assertEqual(result['gates']['staticScan'], 'PASS')
        self.assertFalse(result['gates']['m0Complete'])
        self.assertEqual(result['gates']['mysqlSchema'], 'NOT_RUN')

    def test_inherited_tenant_and_indirect_child_are_distinguished(self):
        models = {row['table']: row for row in scanner.inventory(self.root)['models']}
        self.assertTrue(models['t_student']['tenantScopedSyntactic'])
        self.assertFalse(models['t_child']['tenantScopedSyntactic'])
        self.assertEqual(models['t_child']['fields']['parent_id']['foreignKeys'], ['t_student.id'])
        self.assertIn('parent_id', models['t_child']['logicalIdFieldsToReview'])

    def test_every_candidate_stays_unknown_and_non_destructive(self):
        result = scanner.inventory(self.root)
        for row in result['models']:
            self.assertFalse(row['purgeAuthorized'])
            self.assertEqual(row['ownershipClass'], 'UNKNOWN')
        self.assertFalse(result['gates']['deletionAuthorized'])
        self.assertFalse(result['gates']['runtimeEntitlementChanged'])

    def test_fingerprint_is_stable_and_changes_with_content(self):
        first = scanner.inventory(self.root)['sourceManifestHash']
        self.assertEqual(first, scanner.inventory(self.root)['sourceManifestHash'])
        self.write('backend/app/models/test.py', 'class Empty: pass\n')
        self.assertNotEqual(first, scanner.inventory(self.root)['sourceManifestHash'])

    def test_missing_parent_and_multiple_heads_are_not_silently_accepted(self):
        self.write('backend/alembic/versions/two.py', 'revision = "r2"\ndown_revision = "missing"\n')
        result = scanner.inventory(self.root)
        self.assertEqual(result['gates']['staticScan'], 'FAIL')
        self.assertTrue(any(i['code'] == 'MIGRATION_GRAPH_REQUIRES_REVIEW' for i in result['summary']['issues']))

    def test_duplicate_revisions_and_tables_are_reported(self):
        self.write('backend/alembic/versions/two.py', 'revision = "r1"\ndown_revision = None\n')
        self.write('backend/app/models/duplicate.py', 'class Duplicate(Base):\n __tablename__ = "t_student"\n')
        codes = {i['code'] for i in scanner.inventory(self.root)['summary']['issues']}
        self.assertIn('DUPLICATE_TABLE_DECLARATIONS', codes)
        self.assertIn('MIGRATION_GRAPH_REQUIRES_REVIEW', codes)

    def test_dynamic_and_invalid_sources_are_blocked(self):
        self.write('backend/app/models/dynamic.py', 'class Dynamic(Base):\n __tablename__ = pick_table()\n')
        self.write('backend/app/models/broken.py', 'bad = (\n')
        codes = {i['code'] for i in scanner.inventory(self.root)['summary']['issues']}
        self.assertIn('DYNAMIC_TABLE_REQUIRES_REVIEW', codes)
        self.assertIn('SOURCE_PARSE_ERROR', codes)

    def test_alias_and_employment_drift_rejected(self):
        self.manifest['modules'][-1]['featureKey'] = 'internship'
        self.write_manifest()
        self.assertIsNone(scanner.inventory(self.root)['moduleMapping'])
        with self.assertRaises(ValueError):
            scanner.module_mapping(self.manifest)

    def test_navigation_owner_never_assigns_deletion_owner(self):
        self.manifest['modules'][0]['dataOwner'] = 'studentAffairs'
        self.write_manifest()
        result = scanner.inventory(self.root)
        self.assertTrue(all(m['ownershipClass'] == 'UNKNOWN' for m in result['models']))

    def test_symlink_is_not_read(self):
        target = self.root / 'outside.py'
        target.write_text('secret content must not be parsed', encoding='utf-8')
        link = self.root / 'backend/app/models/link.py'
        link.symlink_to(target)
        result = scanner.inventory(self.root)
        self.assertTrue(any(i['code'] == 'SYMLINK_NOT_SCANNED' for i in result['summary']['issues']))
        self.assertNotIn('backend/app/models/link.py', result['sourceFiles'])

    def test_table_calls_are_explicit_review_gaps(self):
        self.write('backend/app/models/table.py', 'thing = Table("t_raw", metadata)\n')
        result = scanner.inventory(self.root)
        self.assertEqual(result['additionalTableSites'][0]['kind'], 'TABLE_CALL_REVIEW')
        self.assertFalse(result['gates']['m0Complete'])

    def test_disconnected_cycle_is_detected_even_with_one_head(self):
        self.write('backend/alembic/versions/two.py', 'revision = "r2"\ndown_revision = "r3"\n')
        self.write('backend/alembic/versions/three.py', 'revision = "r3"\ndown_revision = "r2"\n')
        result = scanner.inventory(self.root)
        self.assertEqual(result['staticMigrationHeads'], ['r1'])
        self.assertTrue(any(i['code'] == 'UNRESOLVED_MIGRATION_CHAIN' for i in result['summary']['issues']))

    def test_no_revision_is_invented_for_dynamic_migrations(self):
        self.write('backend/alembic/versions/two.py', 'revision = compute_revision()\ndown_revision = "r1"\n')
        codes = {i['code'] for i in scanner.inventory(self.root)['summary']['issues']}
        self.assertIn('DYNAMIC_MIGRATION_REQUIRES_REVIEW', codes)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=True).stdout.strip()

    def committed_fixture(self):
        self.git('init', '-q')
        self.git('add', 'backend/app/models/test.py', 'backend/alembic/versions/one.py', 'shared/contracts/module-manifest.json')
        self.git('-c', 'user.name=Inventory Test', '-c', 'user.email=inventory@example.invalid', 'commit', '-qm', 'isolated scanner fixture')
        return self.git('rev-parse', 'HEAD')

    def run_cli(self, head, output):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--repo', str(self.root),
                               '--expected-head', head, '--output', str(output)], capture_output=True, text=True, timeout=20)

    def test_cli_binds_evidence_to_exact_clean_head(self):
        head = self.committed_fixture()
        with tempfile.TemporaryDirectory() as output_dir:
            output = Path(output_dir) / 'inventory.json'
            result = self.run_cli(head, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads(output.read_text())
            self.assertEqual(evidence['sourceSha'], head)
            self.assertFalse(evidence['gates']['m0Complete'])
            self.assertEqual(self.git('status', '--porcelain'), '')

    def test_cli_rejects_wrong_head_and_does_not_write_evidence(self):
        self.committed_fixture()
        with tempfile.TemporaryDirectory() as output_dir:
            output = Path(output_dir) / 'inventory.json'
            self.assertEqual(self.run_cli('0'*40, output).returncode, 2)
            self.assertFalse(output.exists())

    def test_cli_rejects_dirty_or_untracked_source(self):
        head = self.committed_fixture()
        self.write('backend/app/models/new.py', 'class New: pass\n')
        with tempfile.TemporaryDirectory() as output_dir:
            output = Path(output_dir) / 'inventory.json'
            self.assertEqual(self.run_cli(head, output).returncode, 2)
            self.assertFalse(output.exists())
            self.assertTrue((self.root / 'backend/app/models/new.py').exists())

    def test_cli_never_overwrites_existing_report(self):
        head = self.committed_fixture()
        with tempfile.TemporaryDirectory() as output_dir:
            output = Path(output_dir) / 'inventory.json'
            output.write_text('previous evidence')
            self.assertEqual(self.run_cli(head, output).returncode, 2)
            self.assertEqual(output.read_text(), 'previous evidence')

    def test_cli_cannot_write_inside_repo(self):
        head = self.committed_fixture()
        output = self.root / 'audit.json'
        self.assertEqual(self.run_cli(head, output).returncode, 2)
        self.assertFalse(output.exists())

    def test_missing_source_roots_fail_instead_of_empty_pass(self):
        self.assertEqual(scanner.inventory(self.root / 'shared')['gates']['staticScan'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
