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

    def test_three_independent_http_processes_cover_shared_and_failed_redis_reads(self):
        text = WORKFLOW.read_text()
        for port in (8000, 8001, 8002):
            self.assertIn(f"--port {port}", text)
        self.assertIn("REDIS_URL=redis://127.0.0.1:9/14", text)
        self.assertIn("auth_two_process_revocation.py", text)
        script = REVOCATION.read_text()
        for name in ("E2E_AUTH_A", "E2E_AUTH_B", "E2E_AUTH_C"):
            self.assertIn(name, script)
        self.assertIn('"clientType": "STUDENT_PC"', script)
        self.assertIn('after_shared.status_code == 401', script)
        self.assertIn('after_no_redis.status_code == 401', script)
        self.assertIn('workerCDurableMysqlFallback', script)
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

    def test_auth_route_and_fixture_changes_retrigger_this_gate(self):
        text = WORKFLOW.read_text()
        for path in (
            'backend/app/api/v1/auth.py', 'backend/app/core/security_legacy.py',
            'backend/scripts/_seed_login_accounts_only.py', 'backend/scripts/_seed_fixture_roles.py',
        ):
            self.assertIn(path, text)


if __name__ == "__main__":
    unittest.main()
