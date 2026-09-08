"""Offline image-audit policy tests; report fixtures are NOT vulnerability scans.

Runs with stdlib unittest in its own workflow and under the full pytest suite.
No Docker daemon, network access, database or application import is required.
"""
from __future__ import annotations

import contextlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('image_audit_policy', ROOT / 'scripts/check/check-security-image-audit.py')
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)
NOW = datetime(2026, 9, 8, 0, 0, tzinfo=timezone.utc)
SOURCE, HEAD = 'a' * 40, 'b' * 40


def receipt():
    return {'sourceSha': SOURCE, 'headSha': HEAD, 'imageId': 'sha256:' + 'c' * 64,
            'imageRef': 'pr265-image-audit:' + SOURCE,
            'pythonBaseDigest': 'python@sha256:' + 'd' * 64,
            'runtimeBaseDigest': 'registry.access.redhat.com/ubi9/ubi-micro@sha256:' + 'e' * 64}


def report():
    return {'SchemaVersion': 2, 'Trivy': {'Version': POLICY.SCANNER_VERSION},
            'CreatedAt': NOW.isoformat(), 'ArtifactType': 'container_image',
            'ArtifactName': receipt()['imageRef'], 'Metadata': {'ImageID': receipt()['imageId'],
            'OS': {'Family': 'debian', 'Name': '13'}},
            'Results': [
                {'Target': 'image (debian 13)', 'Class': 'os-pkgs', 'Type': 'debian',
                 'Packages': [{'Name': 'libc6', 'Version': 'test-version'}]},
                {'Target': 'Python', 'Class': 'lang-pkgs', 'Type': 'python-pkg',
                 'Packages': [{'Name': 'fastapi', 'Version': 'test-version'}]},
            ]}


def vulnerability(severity='HIGH', fixed=True):
    result = {'VulnerabilityID': 'CVE-2099-0001', 'PkgName': 'fixture-only',
              'InstalledVersion': '1', 'Severity': severity}
    if fixed:
        result['FixedVersion'] = '2'
    return result


def evaluate(r=None, build=None):
    return POLICY.evaluate(report() if r is None else r, receipt() if build is None else build,
                           source_sha=SOURCE, head_sha=HEAD, now=NOW)


class ImageEvidenceTests(unittest.TestCase):
    def test_complete_clean_inventory_passes_only_this_gate(self):
        value = evaluate()
        self.assertTrue(value['imageAuditPassed'])
        self.assertTrue(value['scanEvidenceValid'])
        self.assertFalse(value['releaseApproved'])
        self.assertEqual(value['packageCounts'], {'os': 1, 'python': 1})

    def test_each_blocking_severity_blocks_fixed_and_unfixed(self):
        for severity in ('UNKNOWN', 'HIGH', 'CRITICAL'):
            for fixed in (False, True):
                with self.subTest(severity=severity, fixed=fixed):
                    r = report(); r['Results'][1]['Vulnerabilities'] = [vulnerability(severity, fixed)]
                    result = evaluate(r)
                    self.assertFalse(result['imageAuditPassed'])
                    self.assertEqual(result['blockingFindings'], 1)
                    self.assertEqual(result['unfixedBlockingFindings'], int(not fixed))

    def test_lower_severities_are_counted_not_hidden(self):
        r = report(); r['Results'][0]['Vulnerabilities'] = [vulnerability('MEDIUM'), vulnerability('LOW')]
        result = evaluate(r)
        self.assertTrue(result['imageAuditPassed'])
        self.assertEqual(result['findingCounts']['MEDIUM'], 1)
        self.assertEqual(result['findingCounts']['LOW'], 1)

    def test_every_result_is_scanned_not_just_first(self):
        r = report(); r['Results'].append(deepcopy(r['Results'][1]))
        r['Results'][-1]['Vulnerabilities'] = [vulnerability()]
        self.assertEqual(evaluate(r)['blockingFindings'], 1)

    def test_build_receipt_must_match_both_commit_identities(self):
        for field in ('sourceSha', 'headSha'):
            with self.subTest(field=field):
                build = receipt(); build[field] = 'e' * 40
                with self.assertRaisesRegex(POLICY.InvalidEvidence, 'BUILD_COMMIT_MISMATCH'):
                    evaluate(build=build)

    def test_expected_commit_must_not_be_a_branch_or_shell_text(self):
        for value in ('main', 'bad; command', ''):
            with self.subTest(value=value):
                with self.assertRaises(POLICY.InvalidEvidence):
                    POLICY.evaluate(report(), receipt(), source_sha=value, head_sha=HEAD, now=NOW)

    def test_receipt_requires_concrete_image_and_base_identities(self):
        for field, value in [
            ('imageId', 'tag'), ('imageRef', 'latest'),
            ('pythonBaseDigest', 'python:3.12-slim'),
            ('runtimeBaseDigest', 'registry.access.redhat.com/ubi9/ubi-micro:9.8'),
            ('runtimeBaseDigest', 'registry.access.redhat.com/ubi9/python-312-minimal@sha256:' + 'f' * 64),
        ]:
            with self.subTest(field=field, value=value):
                build = receipt(); build[field] = value
                with self.assertRaises(POLICY.InvalidEvidence):
                    evaluate(build=build)
        build = receipt(); del build['runtimeBaseDigest']
        with self.assertRaisesRegex(POLICY.InvalidEvidence, 'BUILD_RUNTIME_BASE_DIGEST_REQUIRED'):
            evaluate(build=build)

    def test_wrong_scanned_image_ref_is_rejected(self):
        r = report(); r['ArtifactName'] = 'other-image:latest'
        with self.assertRaisesRegex(POLICY.InvalidEvidence, 'SCANNED_IMAGE_REF_MISMATCH'):
            evaluate(r)

    def test_wrong_scanned_image_id_is_rejected(self):
        r = report(); r['Metadata']['ImageID'] = 'sha256:' + 'e' * 64
        with self.assertRaisesRegex(POLICY.InvalidEvidence, 'SCANNED_IMAGE_ID_MISMATCH'):
            evaluate(r)

    def test_source_scan_cannot_pass_as_image_scan(self):
        r = report(); r['ArtifactType'] = 'filesystem'
        with self.assertRaisesRegex(POLICY.InvalidEvidence, 'NOT_CONTAINER_IMAGE_SCAN'):
            evaluate(r)

    def test_unknown_schema_and_missing_scanner_evidence_rejected(self):
        for field, value in [('SchemaVersion', 1), ('SchemaVersion', True), ('Trivy', {}),
                             ('Trivy', {'Version': '0.69.4'})]:
            with self.subTest(field=field, value=value):
                r = report(); r[field] = value
                with self.assertRaises(POLICY.InvalidEvidence):
                    evaluate(r)

    def test_stale_and_future_report_rejected(self):
        for delta in (timedelta(hours=-7), timedelta(minutes=6)):
            with self.subTest(delta=delta):
                r = report(); r['CreatedAt'] = (NOW + delta).isoformat()
                with self.assertRaisesRegex(POLICY.InvalidEvidence, 'STALE_OR_FUTURE_SCAN'):
                    evaluate(r)

    def test_naive_invalid_missing_scan_timestamp_rejected(self):
        for value in ('2026-09-08T00:00:00', 'not-time', None):
            with self.subTest(value=value):
                r = report(); r['CreatedAt'] = value
                with self.assertRaisesRegex(POLICY.InvalidEvidence, 'SCAN_TIMESTAMP_INVALID'):
                    evaluate(r)

    def test_utc_nanosecond_timestamp_supported(self):
        r = report(); r['CreatedAt'] = '2026-09-08T00:00:00.123456789Z'
        self.assertTrue(evaluate(r)['imageAuditPassed'])

    def test_unsupported_or_eol_os_never_looks_clean(self):
        for value in (None, {}, {'Family': 'debian', 'Name': ''},
                      {'Family': 'debian', 'Name': '13', 'EOSL': True},
                      {'Family': 'debian', 'Name': '13', 'EOSL': 'false'}):
            with self.subTest(value=value):
                r = report(); r['Metadata']['OS'] = value
                with self.assertRaises(POLICY.InvalidEvidence):
                    evaluate(r)

    def test_missing_results_is_not_zero_vulnerabilities(self):
        for value in ([], None, {}, [None]):
            with self.subTest(value=value):
                r = report(); r['Results'] = value
                with self.assertRaises(POLICY.InvalidEvidence):
                    evaluate(r)

    def test_os_and_python_coverage_both_required(self):
        for index in (0, 1):
            with self.subTest(index=index):
                r = report(); del r['Results'][index]
                with self.assertRaisesRegex(POLICY.InvalidEvidence, 'OS_AND_PYTHON_COVERAGE_REQUIRED'):
                    evaluate(r)

    def test_no_package_inventory_is_incomplete_scan(self):
        for value in (None, [], [{}], [{'Name': 'name-only'}]):
            with self.subTest(value=value):
                r = report(); r['Results'][1]['Packages'] = value
                with self.assertRaisesRegex(POLICY.InvalidEvidence, 'PACKAGE_INVENTORY_MISSING'):
                    evaluate(r)

    def test_suppression_or_adjusted_severity_is_not_allowed(self):
        r = report(); r['Results'][1]['ExperimentalModifiedFindings'] = [{'ignored': True}]
        with self.assertRaisesRegex(POLICY.InvalidEvidence, 'SUPPRESSED_FINDINGS_NOT_ALLOWED'):
            evaluate(r)

    def test_malformed_findings_cannot_disappear(self):
        for value in (None, {}, [None], [{}], [dict(vulnerability(), Severity='unknown')]):
            with self.subTest(value=value):
                r = report(); r['Results'][1]['Vulnerabilities'] = value
                with self.assertRaises(POLICY.InvalidEvidence):
                    evaluate(r)

    def test_missing_finding_identity_rejected(self):
        for field in ('VulnerabilityID', 'PkgName', 'InstalledVersion'):
            with self.subTest(field=field):
                item = vulnerability(); del item[field]
                r = report(); r['Results'][1]['Vulnerabilities'] = [item]
                with self.assertRaisesRegex(POLICY.InvalidEvidence, 'FINDING_IDENTITY_INVALID'):
                    evaluate(r)

    def test_foreign_secrets_and_raw_paths_not_copied_to_summary(self):
        r = report(); r['Metadata']['ImageConfig'] = {'Env': ['SECRET=private-fixture']}
        r['Results'][1]['Target'] = 'private-path'; item = vulnerability()
        item['Description'] = 'private-text'; r['Results'][1]['Vulnerabilities'] = [item]
        output = json.dumps(evaluate(r))
        for private in ('private-fixture', 'private-path', 'private-text'):
            self.assertNotIn(private, output)


class ImageCliTests(unittest.TestCase):
    def invoke(self, folder, *, r=None, build=None):
        report_path, receipt_path, output = (folder / name for name in ('scan.json', 'build.json', 'summary.json'))
        if r is not None:
            report_path.write_text(json.dumps(r))
        if build is not None:
            receipt_path.write_text(json.dumps(build))
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            status = POLICY.main(['--report', str(report_path), '--build-receipt', str(receipt_path),
                                  '--expected-source-sha', SOURCE, '--expected-head-sha', HEAD,
                                  '--output', str(output)])
        return status, json.loads(stream.getvalue())

    def fresh(self):
        r = report(); r['CreatedAt'] = datetime.now(timezone.utc).isoformat()
        return r

    def test_missing_report_blocks_and_leaves_failure_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            status, summary = self.invoke(Path(directory), build=receipt())
            self.assertEqual(status, 1)
            self.assertFalse(summary['scanEvidenceValid'])
            self.assertTrue((Path(directory) / 'summary.json').is_file())

    def test_broken_json_error_does_not_leak_report_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); (folder / 'scan.json').write_text('private-fixture-invalid-json')
            status, summary = self.invoke(folder, build=receipt())
            self.assertEqual(status, 1); self.assertNotIn('private-fixture', json.dumps(summary))

    def test_cli_returns_success_only_for_complete_clean_actual_format(self):
        with tempfile.TemporaryDirectory() as directory:
            status, summary = self.invoke(Path(directory), r=self.fresh(), build=receipt())
            self.assertEqual(status, 0); self.assertFalse(summary['releaseApproved'])

    def test_high_without_fix_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            r = self.fresh(); r['Results'][1]['Vulnerabilities'] = [vulnerability(fixed=False)]
            status, summary = self.invoke(Path(directory), r=r, build=receipt())
            self.assertEqual(status, 1); self.assertEqual(summary['unfixedBlockingFindings'], 1)

    def test_existing_receipt_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); path = folder / 'summary.json'; path.write_text('previous-evidence')
            status, summary = self.invoke(folder, r=self.fresh(), build=receipt())
            self.assertEqual(status, 1); self.assertEqual(path.read_text(), 'previous-evidence')
            self.assertIn('RECEIPT_NOT_WRITTEN', summary['errors'])

    def test_symlinked_report_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); raw = folder / 'raw.json'; raw.write_text(json.dumps(self.fresh()))
            (folder / 'scan.json').symlink_to(raw)
            status, summary = self.invoke(folder, build=receipt())
            self.assertEqual(status, 1); self.assertFalse(summary['scanEvidenceValid'])

    def test_oversized_evidence_refused_without_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'; path.write_text('{}')
            with self.assertRaisesRegex(POLICY.InvalidEvidence, 'EVIDENCE_SIZE_INVALID'):
                POLICY.read_json(path, limit=1)


class WorkflowContractTests(unittest.TestCase):
    def test_scanner_is_pinned_not_mutable(self):
        source = (ROOT / '.github/workflows/security-image-vulnerability.yml').read_text()
        self.assertIn('aquasecurity/setup-trivy@3fb12ec12f41e471780db15c232d5dd185dcb514', source)
        self.assertIn('version: v' + POLICY.SCANNER_VERSION, source)
        self.assertNotIn('continue-on-error', source)
        self.assertNotIn('pull_request_target', source)
        self.assertNotIn('docker push', source)

    def test_scan_completeness_and_policy_gate_are_mandatory(self):
        source = (ROOT / '.github/workflows/security-image-vulnerability.yml').read_text()
        for flag in ('--image-src docker', '--scanners vuln', '--pkg-types os,library',
                     '--list-all-pkgs=true', '--ignore-unfixed=false', '--ignorefile /dev/null',
                     '--show-suppressed=true', '--skip-db-update=false',
                     '--severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL', 'if: always()',
                     'python scripts/check/check-security-image-audit.py',
                     'contents: read', 'persist-credentials: false', 'retention-days: 7'):
            with self.subTest(flag=flag):
                self.assertIn(flag, source)
        self.assertIn('docker build -f backend/Dockerfile.security', source)
        self.assertIn("{{.Id}}", source)
        self.assertIn("'runtimeBaseDigest': os.environ['RUNTIME_BASE_DIGEST']", source)


if __name__ == '__main__':
    unittest.main()
