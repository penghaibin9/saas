from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import stat
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/check-host-security.py"
spec = spec_from_file_location("host_security_audit", SCRIPT)
host_security = module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = host_security
spec.loader.exec_module(host_security)


def statuses(items):
    return {item.check: item.status for item in items}


SECURE_SSH = """
permitrootlogin no
passwordauthentication no
kbdinteractiveauthentication no
pubkeyauthentication yes
x11forwarding no
allowagentforwarding no
allowtcpforwarding no
maxauthtries 4
logingracetime 30
clientaliveinterval 300
clientalivecountmax 2
port 22
"""


class HostAuditFocusedContracts(unittest.TestCase):
    def test_secure_sshd_contract_passes(self):
        result = statuses(host_security.evaluate_sshd(SECURE_SSH, 22))
        self.assertTrue(all(value == host_security.PASS for value in result.values()))

    def test_password_or_root_ssh_fails_closed(self):
        text = SECURE_SSH.replace("permitrootlogin no", "permitrootlogin yes")
        text = text.replace("passwordauthentication no", "passwordauthentication yes")
        result = statuses(host_security.evaluate_sshd(text, 22))
        self.assertEqual(result["ssh.permitrootlogin"], host_security.FAIL)
        self.assertEqual(result["ssh.passwordauthentication"], host_security.FAIL)

    def test_sensitive_public_listener_is_rejected(self):
        findings = host_security.evaluate_listeners(
            [("0.0.0.0", 443), ("0.0.0.0", 3306), ("127.0.0.1", 6379)], 22, set()
        )
        result = statuses(findings)
        self.assertEqual(result["listener.sensitive.3306"], host_security.FAIL)
        self.assertEqual(result["listener.public.3306"], host_security.FAIL)
        self.assertEqual(result["listener.sensitive.6379"], host_security.PASS)

    def test_ufw_requires_source_restricted_ssh_and_no_sensitive_allows(self):
        secure = """
Status: active
Default: deny (incoming), allow (outgoing), disabled (routed)
22/tcp ALLOW IN 203.0.113.10
80/tcp ALLOW IN Anywhere
443/tcp ALLOW IN Anywhere
"""
        result = statuses(host_security.evaluate_ufw(secure, 22))
        self.assertEqual(result["firewall.ufw_active"], host_security.PASS)
        self.assertEqual(result["firewall.default_deny"], host_security.PASS)
        self.assertEqual(result["firewall.ssh_rule"], host_security.PASS)
        for port in host_security.SENSITIVE_PORTS:
            self.assertEqual(result[f"firewall.sensitive.{port}"], host_security.PASS)

    def test_ufw_rejects_world_open_ssh(self):
        text = """
Status: active
Default: deny (incoming), allow (outgoing), disabled (routed)
22/tcp ALLOW IN Anywhere
"""
        result = statuses(host_security.evaluate_ufw(text, 22))
        self.assertEqual(result["firewall.ssh_rule"], host_security.FAIL)

    def test_nginx_contract_requires_tls12_tls13_and_security_includes(self):
        text = """
http {
  server_tokens off;
  include /etc/nginx/snippets/security-http.conf;
  server {
    listen 443 ssl http2;
    ssl_protocols TLSv1.2 TLSv1.3;
    include /etc/nginx/snippets/security-server.conf;
  }
}
"""
        result = statuses(host_security.evaluate_nginx(text))
        self.assertTrue(all(value == host_security.PASS for value in result.values()))

    def test_docker_daemon_rejects_tcp_socket_and_unbounded_logs(self):
        bad = {
            "live-restore": False,
            "no-new-privileges": False,
            "hosts": ["tcp://0.0.0.0:2375"],
            "insecure-registries": ["registry.invalid:5000"],
            "log-driver": "json-file",
        }
        result = statuses(host_security.evaluate_docker_daemon(bad))
        self.assertEqual(result["docker.live_restore"], host_security.FAIL)
        self.assertEqual(result["docker.no_new_privileges"], host_security.FAIL)
        self.assertEqual(result["docker.tcp_socket"], host_security.FAIL)
        self.assertEqual(result["docker.insecure_registries"], host_security.FAIL)
        self.assertEqual(result["docker.log_rotation"], host_security.FAIL)

    def test_secret_permissions_fail_when_other_readable(self):
        findings = host_security.evaluate_secret_mode(stat.S_IFREG | 0o644, 0, 0)
        self.assertEqual(findings[0].status, host_security.FAIL)


if __name__ == "__main__":
    unittest.main()
