"""Contracts separating empty-host preflight from final Docker runtime evidence."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/check-docker-port-exposure.py"
SPEC = importlib.util.spec_from_file_location("docker_preflight_contract", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class DockerPreflightContractTests(unittest.TestCase):
    def test_empty_runtime_is_blocking_for_final_acceptance(self):
        finding = AUDIT.evaluate_containers([], {80, 443})[0]
        self.assertEqual(finding.status, AUDIT.FAIL)
        self.assertIn("final", finding.message.lower())

    def test_empty_runtime_is_only_warning_in_explicit_preflight(self):
        finding = AUDIT.evaluate_containers([], {80, 443}, allow_empty=True)[0]
        self.assertEqual(finding.status, AUDIT.WARN)
        self.assertIn("preflight", finding.evidence)

    def test_source_marks_runtime_evidence_completeness(self):
        source = SCRIPT.read_text()
        self.assertIn('"runtimeEvidenceComplete": bool(containers)', source)
        self.assertIn('"preflightEmptyAllowed": args.preflight_empty_ok', source)
        self.assertIn('action="store_true"', source)

    def test_preflight_flag_does_not_relax_real_port_exposure(self):
        container = {
            "Id": "a" * 64,
            "HostConfig": {
                "Privileged": False,
                "NetworkMode": "default",
                "PublishAllPorts": False,
                "Binds": [],
            },
            "NetworkSettings": {
                "Ports": {"3306/tcp": [{"HostIp": "0.0.0.0", "HostPort": "3306"}]}
            },
        }
        findings = AUDIT.evaluate_containers([container], {80, 443}, allow_empty=True)
        self.assertIn(AUDIT.FAIL, [item.status for item in findings])


if __name__ == "__main__":
    unittest.main()
