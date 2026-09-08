from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/security-image-vulnerability.yml'
DOCKERFILE = ROOT / 'backend/Dockerfile.security'

EXPECTED_RUNTIME_SCRIPTS = {
    'check_crypto_compatibility.py',
    'check_production_file_scan.py',
    'check_production_redis.py',
    'cleanup_shared_import_batches.py',
    'run_scheduled_jobs.py',
    'security_profile_probe.py',
}


class SecurityProductionImageSurfaceContracts(unittest.TestCase):
    def test_production_scan_is_explicit_trixie_after_bookworm_comparison(self):
        text = WORKFLOW.read_text()
        self.assertIn('export PYTHON_BASE_TAG="python:3.12-slim-trixie"', text)
        self.assertNotIn('python:3.12-slim-bookworm', text)
        self.assertNotIn('python:3.12-alpine', text)

    def test_base_is_resolved_to_digest_before_build(self):
        text = WORKFLOW.read_text()
        pull = text.index('docker pull "$PYTHON_BASE_TAG"')
        inspect = text.index('export PYTHON_BASE_DIGEST=')
        build = text.index('docker build -f backend/Dockerfile.security')
        self.assertLess(pull, inspect)
        self.assertLess(inspect, build)
        self.assertIn('--build-arg "PYTHON_BASE_IMAGE=$PYTHON_BASE_DIGEST"', text)
        self.assertIn("'pythonBaseTag': os.environ['PYTHON_BASE_TAG']", text)
        self.assertIn("'pythonBaseDigest': os.environ['PYTHON_BASE_DIGEST']", text)

    def test_runtime_does_not_copy_entire_backend_scripts_tree(self):
        text = DOCKERFILE.read_text()
        self.assertNotIn('COPY backend/scripts ./scripts', text)
        copy_block = text[text.index('RUN mkdir -p ./scripts'):text.index('COPY shared /app/shared')]
        copied = set(re.findall(r'backend/scripts/([A-Za-z0-9_.-]+\.py)', copy_block))
        self.assertEqual(copied, EXPECTED_RUNTIME_SCRIPTS)
        self.assertNotIn('seed_demo_data.py', copy_block)
        self.assertNotIn('bootstrap_', copy_block)

    def test_scheduler_dependency_is_in_runtime_allowlist(self):
        scheduler = (ROOT / 'backend/scripts/run_scheduled_jobs.py').read_text()
        self.assertIn('from scripts.cleanup_shared_import_batches import run', scheduler)
        self.assertIn('cleanup_shared_import_batches.py', EXPECTED_RUNTIME_SCRIPTS)

    def test_setuid_and_setgid_bits_are_stripped_before_nonroot_user(self):
        text = DOCKERFILE.read_text()
        find = 'find /usr/bin /usr/sbin /bin /sbin -xdev -type f'
        self.assertIn(find, text)
        self.assertIn('-perm -4000 -o -perm -2000', text)
        self.assertIn('-exec chmod a-s {} +', text)
        self.assertLess(text.index(find), text.index('USER 10001:10001'))

    def test_native_runtime_surface_check_is_mandatory_before_scan(self):
        text = WORKFLOW.read_text()
        surface = text.index('- name: Verify reduced runtime script and privilege-escalation surface')
        scan = text.index('- name: Scan OS and language packages')
        self.assertLess(surface, scan)
        block = text[surface:scan]
        self.assertIn('find /usr/bin /usr/sbin /bin /sbin', block)
        for name in EXPECTED_RUNTIME_SCRIPTS:
            self.assertIn(name, block)
        self.assertNotIn('continue-on-error', block)
        self.assertNotIn('|| true', block)

    def test_vulnerability_policy_is_not_relaxed_to_make_unfixed_findings_green(self):
        text = WORKFLOW.read_text()
        self.assertIn('--severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --ignore-unfixed=false', text)
        self.assertIn('--ignorefile /dev/null', text)
        self.assertIn("--ignore-policy ''", text)
        self.assertIn("--vex ''", text)
        self.assertIn('Require fresh matching image evidence and zero blocking findings', text)


if __name__ == '__main__':
    unittest.main()
