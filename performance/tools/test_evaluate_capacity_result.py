#!/usr/bin/env python3
"""Behavior contract for capacity verdict semantics using only the Python standard library."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALUATOR = ROOT / "performance" / "tools" / "evaluate_capacity_result.py"


def _summary(*, p95: float, p99: float, failed_rate: float = 0.0, check_rate: float = 1.0) -> dict:
    return {
        "metrics": {
            "http_req_duration": {"values": {"p(95)": p95, "p(99)": p99}},
            "http_req_failed": {"values": {"rate": failed_rate}},
            "checks": {"values": {"rate": check_rate}},
            "http_reqs": {"values": {"count": 10000}},
        }
    }


def _probe(target_mode: str) -> dict:
    return {
        "ok": True,
        "targetMode": target_mode,
        "health": {"statusCode": 200, "status": "UP"},
        "readiness": {
            "statusCode": 200,
            "status": "READY",
            "checks": {"database": True, "redis": True},
        },
        "metrics": {
            "missingKeys": [],
            "latest": {"statuses": {"2xx": 10000}},
        },
    }


def _run(*, target_mode: str, p95: float, p99: float, failed_rate: float = 0.0):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        summary = root / "summary.json"
        before = root / "before.json"
        after = root / "after.json"
        output = root / "verdict.json"
        summary.write_text(
            json.dumps(_summary(p95=p95, p99=p99, failed_rate=failed_rate)), encoding="utf-8"
        )
        before.write_text(json.dumps(_probe(target_mode)), encoding="utf-8")
        after.write_text(json.dumps(_probe(target_mode)), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(EVALUATOR),
                "--profile",
                "p300",
                "--summary",
                str(summary),
                "--before",
                str(before),
                "--after",
                str(after),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        verdict = json.loads(output.read_text(encoding="utf-8"))
        return proc, verdict


class CapacityVerdictSemanticsTest(unittest.TestCase):
    def test_local_high_load_can_finish_diagnostic_without_claiming_capacity_green(self):
        proc, verdict = _run(target_mode="local", p95=4021.772, p99=4699.935)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(verdict["functionalPassed"])
        self.assertTrue(verdict["executionPassed"])
        self.assertFalse(verdict["passed"])
        self.assertFalse(verdict["releaseCapacityPassed"])
        self.assertFalse(verdict["releaseEligible"])
        self.assertTrue(verdict["diagnosticOnly"])
        self.assertFalse(verdict["latencyGateEnforced"])
        self.assertEqual(verdict["status"], "DIAGNOSTIC_FUNCTIONAL_PASS")

    def test_remote_high_load_with_slow_latency_is_capacity_fail(self):
        proc, verdict = _run(target_mode="remote", p95=4021.772, p99=4699.935)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(verdict["functionalPassed"])
        self.assertFalse(verdict["executionPassed"])
        self.assertFalse(verdict["passed"])
        self.assertFalse(verdict["releaseCapacityPassed"])
        self.assertTrue(verdict["releaseEligible"])
        self.assertTrue(verdict["latencyGateEnforced"])
        self.assertEqual(verdict["status"], "CAPACITY_FAIL")

    def test_remote_high_load_with_good_latency_is_capacity_pass(self):
        proc, verdict = _run(target_mode="remote", p95=700, p99=1200)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(verdict["functionalPassed"])
        self.assertTrue(verdict["executionPassed"])
        self.assertTrue(verdict["passed"])
        self.assertTrue(verdict["releaseCapacityPassed"])
        self.assertEqual(verdict["status"], "CAPACITY_PASS")

    def test_local_diagnostic_still_fails_real_functional_errors(self):
        proc, verdict = _run(target_mode="local", p95=700, p99=1200, failed_rate=0.01)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(verdict["functionalPassed"])
        self.assertFalse(verdict["executionPassed"])
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["status"], "DIAGNOSTIC_FUNCTIONAL_FAIL")


if __name__ == "__main__":
    unittest.main()
