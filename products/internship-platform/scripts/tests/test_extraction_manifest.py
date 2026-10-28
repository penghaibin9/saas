"""The selected student pages must bring their actual recruitment presentation dependencies."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class ExtractionManifestTest(unittest.TestCase):
    def test_existing_recruitment_components_are_included_without_other_student_modules(self):
        root = Path(__file__).resolve().parents[4]
        product = root / 'products/internship-platform'
        subprocess.run([sys.executable, str(product / 'scripts/build_extraction_manifest.py')],
                       cwd=root, check=True, capture_output=True)
        manifest = json.loads((product / 'artifacts/extraction-manifest.json').read_text(encoding='utf-8'))
        sources = manifest['surfaces']['studentPc']
        for component in (root / 'student-portal/src/components/recruitment').glob('*.vue'):
            self.assertIn(component.relative_to(root).as_posix(), sources)
        self.assertFalse(any('/academic/' in path or '/student-affairs/' in path for path in sources))
        self.assertFalse(manifest['policy']['historicalMigrationsInstallableInStandalone'])
