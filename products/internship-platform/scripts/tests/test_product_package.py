import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import product
from check_schema_revision_contract import check_contract, CURRENT_PRODUCT_FILES, PRODUCT


class ProductPackageTest(unittest.TestCase):
    def test_web_prefix_accepts_local_paths_and_rejects_external_or_traversal_paths(self):
        self.assertEqual(product.web_base_path('/'), '')
        self.assertEqual(product.web_base_path('/internship/'), '/internship')
        for invalid in ['https://other.example', '//other.example', '/internship/../api', '/a?b', '/a#b']:
            with self.assertRaises(ValueError):
                product.web_base_path(invalid)

    def fixture(self, root):
        (root / 'README.md').write_text('独立产品', encoding='utf-8')
        for output in product.OUTPUTS:
            (root / output).mkdir(parents=True)
            (root / output / 'index.html').write_text('<html>实际构建</html>', encoding='utf-8')
        (root / 'backend/app').mkdir(parents=True)
        (root / 'backend/app/main.py').write_text('value = 1', encoding='utf-8')
        (root / 'backend/alembic/data').mkdir(parents=True)
        (root / 'backend/alembic/data/permissions.json').write_text('{"permissions": []}')
        (root / '.product-audits').mkdir()
        audits=[]
        for surface in product.SURFACES:
            audit=root / '.product-audits' / (surface+'.json');audit.write_text('{}');audits.append(audit)
        receipt = {'product': 'internship-standalone',
            'sourceFiles': product.hashes(root, product.source_files(root)),
            'buildFiles': product.hashes(root, product.built_files(root)),
            'auditFiles': product.hashes(root, audits)}
        (root / product.RECEIPT).write_text(json.dumps(receipt), encoding='utf-8')

    def test_export_excludes_environment_private_material_and_runtime_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'product'; root.mkdir(); self.fixture(root)
            for name in ['.env.production', 'accounts.private.json', 'key.pem', 'runtime.db']:
                (root / 'backend' / name).write_text('must-not-ship')
            for folder in ['.venv', 'node_modules', 'data', 'test-results-example']:
                (root / 'backend' / folder).mkdir()
                (root / 'backend' / folder / 'private.txt').write_text('must-not-ship')
            output = Path(directory) / 'delivery.zip'
            product.package(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertIn('backend/app/main.py', archive.namelist())
                self.assertIn('mobile/dist/build/h5/index.html', archive.namelist())
                self.assertIn('backend/alembic/data/permissions.json', archive.namelist())
                self.assertFalse(any(b'must-not-ship' in archive.read(name) for name in archive.namelist()))
            self.assertTrue(output.with_suffix('.zip.sha256').is_file())
            with self.assertRaisesRegex(ValueError, '已存在'):
                product.package(root, output)

    def test_source_or_build_change_invalidates_receipt(self):
        for relative in ['backend/app/main.py', 'student-web/dist/index.html']:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'product'; root.mkdir(); self.fixture(root)
                (root / relative).write_text('changed', encoding='utf-8')
                output = Path(directory) / 'delivery.zip'
                with self.assertRaisesRegex(ValueError, '已变化'):
                    product.package(root, output)
                self.assertFalse(output.exists())

    def test_server_script_rejects_windows_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            (root / 'scripts').mkdir()
            (root / 'scripts/start.sh').write_bytes(b'#!/bin/sh\r\nexit 0\r\n')
            with self.assertRaisesRegex(ValueError, '换行格式'):
                product.source_files(root)

    def test_portable_schema_contract_needs_no_parent_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migrations = root / 'backend/alembic/versions'; migrations.mkdir(parents=True)
            (migrations / '0001.py').write_text("revision='ix0001'\ndown_revision=None\n")
            for relative in CURRENT_PRODUCT_FILES:
                target = root / relative.relative_to(PRODUCT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('EXPECTED_ALEMBIC_REVISION=ix0001\n')
            head, paths, errors = check_contract(root)
            self.assertEqual(head, 'ix0001')
            self.assertEqual(len(paths), len(CURRENT_PRODUCT_FILES))
            self.assertEqual(errors, [])
            (root / 'deploy/env.production.example').write_text('EXPECTED_ALEMBIC_REVISION=ix0000\n')
            self.assertEqual(len(check_contract(root)[2]), 1)


if __name__ == '__main__':
    unittest.main()
