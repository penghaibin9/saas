"""Upgrade contracts and failure receipts; no dependency/runtime is mocked as fixed.

The workflow executes the separate compatibility command INSIDE the built image.
These stdlib tests protect pin consistency and its mandatory execution/failure path.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'backend/scripts/check_crypto_compatibility.py'
SPEC = importlib.util.spec_from_file_location('crypto_upgrade_smoke', SCRIPT)
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


def requirements(name):
    return [line.strip() for line in (ROOT / 'backend' / name).read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


class DependencyUpgradeContracts(unittest.TestCase):
    def test_exact_freezes_match_including_platform_markers(self):
        self.assertEqual(requirements('requirements.txt'), requirements('requirements.lock'))
        self.assertIn('uvloop==0.22.1; sys_platform != "win32"', requirements('requirements.lock'))

    def test_reviewed_crypto_pin_is_unique_and_matches_smoke(self):
        for name in ('requirements.txt', 'requirements.lock'):
            with self.subTest(name=name):
                pins = [p for p in requirements(name) if p.lower().startswith('cryptography')]
                self.assertEqual(pins, ['cryptography==' + SMOKE.EXPECTED_VERSION])
        self.assertEqual(SMOKE.EXPECTED_VERSION, '50.0.1')

    def test_direct_policy_cannot_resolve_back_to_vulnerable_major(self):
        pins = [p for p in requirements('requirements.in') if p.lower().startswith('cryptography')]
        self.assertEqual(pins, ['cryptography>=50.0.1,<51.0'])

    def test_sdk_freeze_supports_crypto_upgrade_without_forcing_install(self):
        for name in ('requirements.txt', 'requirements.lock'):
            with self.subTest(name=name):
                pins = [p for p in requirements(name) if p.lower().startswith('alibabacloud-tea-openapi')]
                self.assertEqual(pins, ['alibabacloud-tea-openapi==0.4.6'])
        self.assertIn('alibabacloud-tea-openapi>=0.4.6,<0.5', requirements('requirements.in'))
        text = (ROOT / 'backend/Dockerfile.security').read_text()
        appenv = text.split('FROM ${SECURITY_PYTHON_BASE_IMAGE} AS appenv\n', 1)[1].split(
            'FROM ${RUNTIME_BASE_IMAGE} AS micro-root', 1)[0]
        self.assertIn('/opt/secure-venv/bin/pip install --no-cache-dir --no-index --find-links /tmp/wheels -r /tmp/requirements.txt', appenv)
        self.assertNotIn('pip install --no-deps', appenv)
        self.assertIn('&& /opt/secure-venv/bin/pip check', appenv)

    def test_runtime_root_receives_reviewed_distribution_packages(self):
        text = (ROOT / 'backend/Dockerfile.security').read_text()
        rootfs = text.split('FROM ${SECURITY_PYTHON_BASE_IMAGE} AS rootfs\n', 1)[1].split('FROM scratch', 1)[0]
        self.assertIn('--installroot="$INSTALL_ROOT"', rootfs)
        self.assertIn('--releasever=9', rootfs)
        self.assertIn('install python3.12 ca-certificates tzdata', rootfs)
        self.assertIn('rpm --root "$INSTALL_ROOT" -q python3.12 ca-certificates tzdata', rootfs)
        self.assertNotIn('|| true', rootfs)
        self.assertNotIn('--allow-unauthenticated', rootfs)
        self.assertNotIn('rpm -e --nodeps', rootfs)

    def test_image_preserves_package_inventory_and_nonroot_readiness(self):
        text = (ROOT / 'backend/Dockerfile.security').read_text()
        self.assertNotIn('rm -rf /var/lib/dpkg', text)
        self.assertNotIn('rm -rf /usr/lib/sysimage/rpm', text)
        self.assertIn('(test -d "$INSTALL_ROOT/usr/lib/sysimage/rpm" || test -d "$INSTALL_ROOT/var/lib/rpm")', text)
        self.assertIn('USER 10001:10001', text)
        self.assertIn('scripts/security_profile_probe.py', text)
        self.assertIn('/opt/secure-venv/bin/pip check', text)

    def test_native_smoke_is_mandatory_in_same_scanned_image(self):
        text = (ROOT / '.github/workflows/security-image-vulnerability.yml').read_text()
        start = text.index('- name: Verify upgraded crypto')
        end = text.index('# Pinned reviewed installer', start)
        command = text[start:end]
        self.assertIn('"pr265-image-audit:$GITHUB_SHA" python scripts/check_crypto_compatibility.py', command)
        self.assertIn('--network none --read-only --cap-drop=ALL', command)
        self.assertIn('--security-opt=no-new-privileges', command)
        self.assertIn('set -euo pipefail', command)
        self.assertNotIn('continue-on-error', text)
        self.assertNotIn('|| true', command)
        self.assertNotIn('if:', command)

    def test_scan_severities_and_unfixed_policy_are_not_relaxed(self):
        text = (ROOT / '.github/workflows/security-image-vulnerability.yml').read_text()
        self.assertIn('--severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --ignore-unfixed=false', text)
        self.assertIn('--ignorefile /dev/null', text)
        self.assertIn('Require fresh matching image evidence and zero blocking findings', text)

    def test_smoke_cannot_be_skipped_via_command_line(self):
        text = SCRIPT.read_text()
        self.assertNotIn('argparse', text)
        self.assertNotIn('getenv(', text)
        self.assertNotIn('os.environ', text)
        self.assertIn('check_version()', text)


class SmokeReceiptContracts(unittest.TestCase):
    def test_old_installed_version_is_rejected(self):
        with patch.object(SMOKE, 'version', return_value='46.0.7'):
            with self.assertRaisesRegex(RuntimeError, 'CRYPTOGRAPHY_FREEZE_MISMATCH'):
                SMOKE.check_version()

    def test_unreviewed_future_version_is_not_silently_accepted(self):
        with patch.object(SMOKE, 'version', return_value='51.0.0'):
            with self.assertRaises(RuntimeError):
                SMOKE.check_version()

    def test_approved_metadata_satisfies_only_version_contract(self):
        with patch.object(SMOKE, 'version', return_value='50.0.1'):
            SMOKE.check_version()

    def test_missing_distribution_fails_before_crypto_or_customer_access(self):
        output = io.StringIO()
        with patch.object(SMOKE, 'version', side_effect=RuntimeError('private failure value')), \
                patch.object(SMOKE, 'check_fernet', side_effect=AssertionError('must not run')), \
                contextlib.redirect_stdout(output):
            self.assertEqual(SMOKE.main(), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result['failedStage'], 'installed-version')
        self.assertEqual(result['completedChecks'], [])
        self.assertNotIn('private failure value', output.getvalue())
        self.assertFalse(result['releaseApproved'])

    def test_each_failed_stage_blocks_receipt_without_raw_error(self):
        names = ('check_version', 'check_fernet', 'check_application_fields', 'check_mysql_rsa')
        stages = ('installed-version', 'legacy-fernet-and-tamper',
                  'application-field-envelopes', 'pymysql-rsa-auth')
        for index, name in enumerate(names):
            with self.subTest(stage=name), contextlib.ExitStack() as stack:
                calls = []
                for method in names:
                    def operation(method=method):
                        calls.append(method)
                        if method == name:
                            raise RuntimeError('synthetic-secret-not-in-receipt')
                    stack.enter_context(patch.object(SMOKE, method, side_effect=operation))
                output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                self.assertEqual(SMOKE.main(), 1)
                result = json.loads(output.getvalue())
                self.assertFalse(result['cryptoCompatibilityPassed'])
                self.assertFalse(result['releaseApproved'])
                self.assertEqual(calls, list(names[:index+1]))
                self.assertEqual(result['failedStage'], stages[index])
                self.assertNotIn('synthetic-secret-not-in-receipt', output.getvalue())

    def test_success_receipt_means_smoke_only_not_release_approval(self):
        with contextlib.ExitStack() as stack:
            for name in ('check_version', 'check_fernet', 'check_application_fields', 'check_mysql_rsa'):
                stack.enter_context(patch.object(SMOKE, name))
            output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(SMOKE.main(), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result['cryptoCompatibilityPassed'])
        self.assertFalse(result['customerDataAccessed'])
        self.assertFalse(result['releaseApproved'])
        self.assertEqual(len(result['checks']), 4)
        self.assertNotIn(SMOKE.PUBLIC_TEST_KEY, output.getvalue())
        self.assertNotIn(SMOKE.LEGACY_VECTOR, output.getvalue())


if __name__ == '__main__':
    unittest.main()
