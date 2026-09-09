"""Offline contracts for the read-only production host security baseline."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/check-host-security.py"
SPEC = importlib.util.spec_from_file_location("host_security", SCRIPT)
HOST = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(HOST)


def statuses(findings):
    return {item.check: item.status for item in findings}


SAFE_SSH = """
port 22
permitrootlogin no
passwordauthentication no
kbdinteractiveauthentication no
pubkeyauthentication yes
x11forwarding no
allowagentforwarding no
allowtcpforwarding no
maxauthtries 4
logingracetime 60
clientaliveinterval 300
clientalivecountmax 2
"""

SAFE_SYSCTL = {
    "kernel.dmesg_restrict": "1",
    "kernel.kptr_restrict": "2",
    "kernel.yama.ptrace_scope": "1",
    "fs.protected_hardlinks": "1",
    "fs.protected_symlinks": "1",
    "fs.suid_dumpable": "0",
    "net.ipv4.tcp_syncookies": "1",
    "net.ipv4.conf.all.accept_redirects": "0",
    "net.ipv4.conf.default.accept_redirects": "0",
    "net.ipv4.conf.all.send_redirects": "0",
    "net.ipv4.conf.default.send_redirects": "0",
    "net.ipv6.conf.all.accept_redirects": "0",
    "net.ipv6.conf.default.accept_redirects": "0",
}

SAFE_DOCKER = {
    "live-restore": True,
    "no-new-privileges": True,
    "log-driver": "local",
    "log-opts": {"max-size": "20m", "max-file": "5"},
}


class HostPolicyTests(unittest.TestCase):
    def test_safe_ssh_contract_passes(self):
        result = HOST.evaluate_sshd(SAFE_SSH, 22)
        self.assertTrue(result)
        self.assertTrue(all(item.status == HOST.PASS for item in result))

    def test_root_or_password_login_is_blocking(self):
        text = SAFE_SSH.replace("permitrootlogin no", "permitrootlogin yes")
        text = text.replace("passwordauthentication no", "passwordauthentication yes")
        result = statuses(HOST.evaluate_sshd(text, 22))
        self.assertEqual(result["ssh.permitrootlogin"], HOST.FAIL)
        self.assertEqual(result["ssh.passwordauthentication"], HOST.FAIL)

    def test_ssh_port_must_match_the_audited_port(self):
        result = statuses(HOST.evaluate_sshd(SAFE_SSH, 2222))
        self.assertEqual(result["ssh.port"], HOST.FAIL)

    def test_tcp_forwarding_is_at_least_visible(self):
        text = SAFE_SSH.replace("allowtcpforwarding no", "allowtcpforwarding yes")
        result = statuses(HOST.evaluate_sshd(text, 22))
        self.assertEqual(result["ssh.allowtcpforwarding"], HOST.WARN)

    def test_sensitive_listener_on_non_loopback_is_blocking(self):
        result = statuses(HOST.evaluate_listeners([("0.0.0.0", 3306)], 22, set()))
        self.assertEqual(result["listener.sensitive.3306"], HOST.FAIL)
        self.assertEqual(result["listener.public.3306"], HOST.FAIL)

    def test_sensitive_listener_on_loopback_is_allowed(self):
        result = statuses(HOST.evaluate_listeners([("127.0.0.1", 3306)], 22, set()))
        self.assertEqual(result["listener.sensitive.3306"], HOST.PASS)

    def test_only_expected_wildcard_ports_are_public(self):
        result = HOST.evaluate_listeners(
            [("0.0.0.0", 22), ("0.0.0.0", 80), ("::", 443), ("0.0.0.0", 9000)],
            22,
            set(),
        )
        failures = [item for item in result if item.status == HOST.FAIL]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].check, "listener.public.9000")

    def test_explicit_public_exception_is_narrow(self):
        result = HOST.evaluate_listeners([("0.0.0.0", 9000)], 22, {9000})
        self.assertFalse(any(item.status == HOST.FAIL for item in result))

    def test_safe_sysctl_contract_passes(self):
        result = HOST.evaluate_sysctl(SAFE_SYSCTL)
        self.assertTrue(all(item.status == HOST.PASS for item in result))

    def test_redirects_or_core_dump_relaxation_blocks(self):
        bad = dict(SAFE_SYSCTL)
        bad["fs.suid_dumpable"] = "1"
        bad["net.ipv4.conf.all.accept_redirects"] = "1"
        result = statuses(HOST.evaluate_sysctl(bad))
        self.assertEqual(result["sysctl.fs.suid_dumpable"], HOST.FAIL)
        self.assertEqual(result["sysctl.net.ipv4.conf.all.accept_redirects"], HOST.FAIL)

    def test_safe_docker_daemon_contract_passes(self):
        result = HOST.evaluate_docker_daemon(SAFE_DOCKER)
        self.assertTrue(all(item.status == HOST.PASS for item in result))

    def test_docker_tcp_or_insecure_registry_is_blocking(self):
        bad = dict(SAFE_DOCKER)
        bad["hosts"] = ["unix:///var/run/docker.sock", "tcp://0.0.0.0:2375"]
        bad["insecure-registries"] = ["registry.invalid:5000"]
        result = statuses(HOST.evaluate_docker_daemon(bad))
        self.assertEqual(result["docker.tcp_socket"], HOST.FAIL)
        self.assertEqual(result["docker.insecure_registries"], HOST.FAIL)

    def test_unbounded_json_file_logs_are_blocking(self):
        bad = {"live-restore": True, "log-driver": "json-file"}
        result = statuses(HOST.evaluate_docker_daemon(bad))
        self.assertEqual(result["docker.log_rotation"], HOST.FAIL)

    def test_secret_permissions_reject_world_readable_or_writable(self):
        self.assertEqual(HOST.evaluate_secret_mode(stat.S_IFREG | 0o600, 0, 1000)[0].status, HOST.PASS)
        self.assertEqual(HOST.evaluate_secret_mode(stat.S_IFREG | 0o644, 0, 1000)[0].status, HOST.FAIL)
        self.assertEqual(HOST.evaluate_secret_mode(stat.S_IFREG | 0o620, 0, 1000)[0].status, HOST.FAIL)


class HostArtifactContractTests(unittest.TestCase):
    def test_auditor_contains_no_host_mutation_commands(self):
        source = SCRIPT.read_text()
        forbidden = (
            "ufw enable", "ufw delete", "systemctl restart", "systemctl reload",
            "sysctl --system", "apt-get install", "apt install", "dnf install",
            "firewall-cmd --add", "iptables -A", "nft add rule", "passwd ",
            "useradd ", "rm /etc/ssh", "cp /etc/ssh", "mv /etc/ssh",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)
        self.assertIn('"mutatedHost": False', source)
        self.assertIn('"productionDataAccessed": False', source)

    def test_ssh_template_fails_closed(self):
        text = (ROOT / "deploy/host/sshd-hardening.conf.example").read_text().lower()
        for expected in (
            "permitrootlogin no", "passwordauthentication no",
            "kbdinteractiveauthentication no", "pubkeyauthentication yes",
            "x11forwarding no", "allowagentforwarding no", "allowtcpforwarding no",
        ):
            self.assertIn(expected, text)

    def test_sysctl_template_matches_the_auditor(self):
        text = (ROOT / "deploy/host/sysctl-hardening.conf.example").read_text()
        parsed = {}
        for raw in text.splitlines():
            if "=" in raw and not raw.lstrip().startswith("#"):
                key, value = raw.split("=", 1)
                parsed[key.strip()] = value.strip()
        result = HOST.evaluate_sysctl(parsed)
        self.assertTrue(result)
        self.assertTrue(all(item.status == HOST.PASS for item in result))

    def test_docker_template_matches_the_auditor(self):
        config = json.loads((ROOT / "deploy/host/docker-daemon.json.example").read_text())
        result = HOST.evaluate_docker_daemon(config)
        self.assertTrue(all(item.status == HOST.PASS for item in result))
        self.assertNotIn("hosts", config)
        self.assertNotIn("insecure-registries", config)

    def test_runbook_requires_rescue_path_and_second_session(self):
        text = (ROOT / "deploy/host/README.md").read_text()
        for phrase in ("VNC", "第二个终端", "快照", "只读审计", "隔离恢复演练"):
            self.assertIn(phrase, text)
        self.assertIn("3306", text)
        self.assertIn("6379", text)
        self.assertIn("2375", text)


if __name__ == "__main__":
    unittest.main()
