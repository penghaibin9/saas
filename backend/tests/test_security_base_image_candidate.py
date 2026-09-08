from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/security-image-vulnerability.yml'


class SecurityBaseImageCandidateContracts(unittest.TestCase):
    def test_candidate_is_supported_python_312_bookworm(self):
        text = WORKFLOW.read_text()
        self.assertIn('export PYTHON_BASE_TAG="python:3.12-slim-bookworm"', text)
        self.assertNotIn('export PYTHON_BASE_TAG="python:3.12-slim"', text)
        self.assertNotIn('python:3.12-slim-trixie', text)
        self.assertNotIn('python:3.12-alpine', text)

    def test_candidate_is_resolved_to_digest_before_build(self):
        text = WORKFLOW.read_text()
        pull = text.index('docker pull "$PYTHON_BASE_TAG"')
        inspect = text.index('export PYTHON_BASE_DIGEST=')
        build = text.index('docker build -f backend/Dockerfile.security')
        self.assertLess(pull, inspect)
        self.assertLess(inspect, build)
        self.assertIn('--build-arg "PYTHON_BASE_IMAGE=$PYTHON_BASE_DIGEST"', text)

    def test_receipt_records_tag_and_digest_without_relaxing_scan(self):
        text = WORKFLOW.read_text()
        self.assertIn("'pythonBaseTag': os.environ['PYTHON_BASE_TAG']", text)
        self.assertIn("'pythonBaseDigest': os.environ['PYTHON_BASE_DIGEST']", text)
        self.assertIn('--severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --ignore-unfixed=false', text)
        self.assertIn('--ignorefile /dev/null', text)
        self.assertIn('Require fresh matching image evidence and zero blocking findings', text)
        self.assertNotIn('continue-on-error', text)

    def test_crypto_compatibility_still_runs_before_scan(self):
        text = WORKFLOW.read_text()
        smoke = text.index('- name: Verify upgraded crypto and old ciphertext')
        scan = text.index('- name: Scan OS and language packages')
        self.assertLess(smoke, scan)
        self.assertIn('--network none --read-only --cap-drop=ALL', text)
        self.assertIn('--security-opt=no-new-privileges', text)


if __name__ == '__main__':
    unittest.main()
