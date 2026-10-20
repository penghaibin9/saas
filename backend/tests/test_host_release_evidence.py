"""Contracts for final host technical-evidence aggregation."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/check-host-release-evidence.py"
SPEC = importlib.util.spec_from_file_location("host_release_evidence", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class HostReleaseEvidenceTests(unittest.TestCase):
    def test_final_docker_receipt_passes(self):
        receipt = {
            "passed": True,
            "preflightEmptyAllowed": False,
            "runtimeEvidenceComplete": True,
            "mutatedHost": False,
            "productionDataAccessed": False,
        }
        self.assertNotIn(AUDIT.FAIL, [item.status for item in AUDIT.evaluate_docker(receipt)])

    def test_preflight_receipt_cannot_be_final_release_evidence(self):
        receipt = {
            "passed": True,
            "preflightEmptyAllowed": True,
            "runtimeEvidenceComplete": False,
            "mutatedHost": False,
            "productionDataAccessed": False,
        }
        findings = {item.check: item.status for item in AUDIT.evaluate_docker(receipt)}
        self.assertEqual(findings["evidence.docker.final_mode"], AUDIT.FAIL)
        self.assertEqual(findings["evidence.docker.runtime_complete"], AUDIT.FAIL)

    def test_missing_safety_markers_fail_closed(self):
        findings = AUDIT.evaluate_host({"passed": True})
        self.assertIn(AUDIT.FAIL, [item.status for item in findings])
        findings = AUDIT.evaluate_dockerd({"passed": True})
        self.assertIn(AUDIT.FAIL, [item.status for item in findings])

    def test_aggregator_never_claims_cloud_or_identity_verification(self):
        source = SCRIPT.read_text()
        self.assertIn('"cloudControlPlaneVerified": False', source)
        self.assertIn('"identitySourcesVerified": False', source)
        self.assertIn('"restoreDrillVerifiedByThisTool": False', source)
        self.assertIn('"mutatedHost": False', source)
        self.assertIn('"productionDataAccessed": False', source)


if __name__ == "__main__":
    unittest.main()
