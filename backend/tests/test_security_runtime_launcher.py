from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = ROOT / "backend/scripts/security_runtime_launcher.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("security_runtime_launcher_test", LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LAUNCHER = load_launcher()


class RuntimeLauncherTests(unittest.TestCase):
    def invoke(self, role):
        calls = []
        def filesystem(): calls.append("filesystem")
        def redis(): calls.append("redis"); return 0
        def scan(): calls.append("scan"); return 0
        def execute(executable, argv):
            calls.append((executable, tuple(argv)))
            raise RuntimeError("EXEC_CAPTURED")
        with self.assertRaisesRegex(RuntimeError, "EXEC_CAPTURED"):
            LAUNCHER.launch(role, filesystem_fn=filesystem, redis_fn=redis,
                            scan_fn=scan, exec_fn=execute)
        return calls

    def test_backend_preflights_then_execs_static_uvicorn_module(self):
        calls = self.invoke("backend")
        self.assertEqual(calls[:3], ["filesystem", "redis", "scan"])
        executable, argv = calls[3]
        self.assertEqual(executable, sys.executable)
        self.assertEqual(argv[:4], (sys.executable, "-m", "uvicorn", "app.main:app"))
        self.assertIn("--no-proxy-headers", argv)
        self.assertNotIn("sh", argv)

    def test_scheduler_has_no_scanner_preflight_and_no_shell(self):
        calls = self.invoke("scheduler")
        self.assertEqual(calls[:2], ["filesystem", "redis"])
        self.assertEqual(calls[2][1], (sys.executable, "-m", "scripts.run_scheduled_jobs"))

    def test_file_scan_has_scanner_preflight_and_no_redis_gate(self):
        calls = self.invoke("file-scan")
        self.assertEqual(calls[:2], ["filesystem", "scan"])
        self.assertEqual(calls[2][1], (sys.executable, "-m", "app.workers.file_scan_worker"))

    def test_failed_preflight_never_execs_target(self):
        def execute(*_):
            self.fail("target must not execute after failed preflight")
        with self.assertRaisesRegex(RuntimeError, "REDIS_PREFLIGHT_FAILED"):
            LAUNCHER.launch("backend", filesystem_fn=lambda: None, redis_fn=lambda: 1,
                            scan_fn=lambda: 0, exec_fn=execute)
        with self.assertRaisesRegex(RuntimeError, "FILE_SCAN_PREFLIGHT_FAILED"):
            LAUNCHER.launch("file-scan", filesystem_fn=lambda: None, redis_fn=lambda: 0,
                            scan_fn=lambda: 1, exec_fn=execute)

    def test_unknown_role_is_rejected_before_any_execution(self):
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_RUNTIME_ROLE"):
            LAUNCHER.target_argv("operator-input")

    def test_all_targets_are_static_python_commands(self):
        self.assertEqual(set(LAUNCHER.ROLE_TARGETS), {"backend", "scheduler", "file-scan"})
        for argv in LAUNCHER.ROLE_TARGETS.values():
            self.assertEqual(argv[0], sys.executable)
            self.assertEqual(argv[1], "-m")
            self.assertFalse(any(token in {"sh", "bash", "dash", "-c"} for token in argv))


if __name__ == "__main__":
    unittest.main()
