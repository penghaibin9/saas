from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/security-runtime-acceptance.yml"
REVOCATION = ROOT / "scripts/e2e/auth_two_process_revocation.py"
RECOVERY = ROOT / "backend/tests/file_scan_recovery_acceptance.py"


class SecurityRuntimeAcceptanceContractTests(unittest.TestCase):
    def test_workflow_is_isolated_and_uses_real_mysql_redis_clamav(self):
        text = WORKFLOW.read_text()
        for image in ("mysql:8.0", "redis:7-alpine", "clamav/clamav:stable"):
            self.assertIn(image, text)
        self.assertIn("APP_ENV: test", text)
        self.assertIn("DEPLOYMENT_MODE: local", text)
        self.assertNotIn("APP_ENV: production", text)
        self.assertNotIn("workflow_run:", text)
        self.assertIn("persist-credentials: false", text)

    def test_two_independent_http_processes_and_cross_process_script_are_mandatory(self):
        text = WORKFLOW.read_text()
        self.assertIn("--port 8000", text)
        self.assertIn("--port 8001", text)
        self.assertIn("auth_two_process_revocation.py", text)
        script = REVOCATION.read_text()
        self.assertIn('E2E_AUTH_A', script)
        self.assertIn('E2E_AUTH_B', script)
        self.assertIn('"clientType": "STUDENT_PC"', script)
        self.assertIn('after.status_code == 401', script)
        self.assertIn('tokenInvalidated', script)

    def test_clamav_acceptance_covers_infected_outage_and_recovery(self):
        text = WORKFLOW.read_text()
        self.assertIn("file_scan_mysql_acceptance.py", text)
        self.assertIn("file_scan_recovery_acceptance.py", text)
        base = (ROOT / "backend/tests/file_scan_mysql_acceptance.py").read_text()
        self.assertIn("EICAR", base)
        self.assertIn('assert_scan_result(result, "INFECTED")', base)
        self.assertIn('infected_row.scan_status == "INFECTED"', base)
        recovery = RECOVERY.read_text()
        self.assertIn('port=9', recovery)
        self.assertIn('recoveredScanStatus', recovery)
        self.assertIn('assert_file_ready_for_business', recovery)

    def test_receipts_are_fixture_only_and_do_not_store_tokens(self):
        revocation = REVOCATION.read_text()
        self.assertIn('"fixtureOnly": True', revocation)
        self.assertNotIn('"accessToken": token', revocation)
        recovery = RECOVERY.read_text()
        self.assertIn('"fixtureOnly": True', recovery)
        workflow = WORKFLOW.read_text()
        self.assertIn('${{ github.workspace }}/artifacts/security-runtime', workflow)


if __name__ == "__main__":
    unittest.main()
