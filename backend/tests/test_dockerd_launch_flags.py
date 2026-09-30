"""Offline contracts for effective dockerd launch-argument auditing."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/check-dockerd-launch-flags.py"
SPEC = importlib.util.spec_from_file_location("dockerd_launch_flags", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def statuses(findings):
    return {item.check: item.status for item in findings}


class DockerdLaunchFlagTests(unittest.TestCase):
    def test_normal_unix_fd_launch_passes(self):
        result = statuses(AUDIT.evaluate_argv(["/usr/bin/dockerd", "-H", "fd://"]))
        self.assertEqual(result["dockerd.launch.iptables"], AUDIT.PASS)
        self.assertEqual(result["dockerd.launch.ip6tables"], AUDIT.PASS)
        self.assertEqual(result["dockerd.launch.tcp_host"], AUDIT.PASS)

    def test_iptables_false_is_blocking(self):
        for argv in (
            ["dockerd", "--iptables=false"],
            ["dockerd", "--iptables", "false"],
            ["dockerd", "--ip6tables=false"],
        ):
            with self.subTest(argv=argv):
                result = statuses(AUDIT.evaluate_argv(argv))
                self.assertIn(AUDIT.FAIL, result.values())

    def test_tcp_management_socket_is_blocking_for_all_common_forms(self):
        cases = (
            ["dockerd", "-H", "tcp://0.0.0.0:2375"],
            ["dockerd", "-H=tcp://127.0.0.1:2375"],
            ["dockerd", "--host=tcp://0.0.0.0:2376"],
            ["dockerd", "-Htcp://0.0.0.0:2375"],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                result = statuses(AUDIT.evaluate_argv(argv))
                self.assertEqual(result["dockerd.launch.tcp_host"], AUDIT.FAIL)

    def test_direct_routing_is_visible(self):
        result = statuses(AUDIT.evaluate_argv(["dockerd", "--allow-direct-routing=true"]))
        self.assertEqual(result["dockerd.launch.allow_direct_routing"], AUDIT.WARN)

    def test_process_cmdline_collection_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "321").mkdir()
            (root / "321" / "cmdline").write_bytes(b"/usr/bin/dockerd\0-H\0fd://\0")
            completed = mock.Mock(returncode=0, stdout="321\n", stderr="")
            with mock.patch.object(AUDIT.subprocess, "run", return_value=completed):
                argv, finding = AUDIT.collect_dockerd_argv(root)
            self.assertEqual(argv, ["/usr/bin/dockerd", "-H", "fd://"])
            self.assertEqual(finding.status, AUDIT.PASS)

    def test_auditor_has_no_daemon_mutation_commands(self):
        source = SCRIPT.read_text()
        for token in (
            "systemctl restart docker", "systemctl reload docker", "kill ",
            "docker stop", "docker restart", "iptables -", "nft add", "ufw ",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)
        self.assertIn('"mutatedHost": False', source)
        self.assertIn('"productionDataAccessed": False', source)


if __name__ == "__main__":
    unittest.main()
