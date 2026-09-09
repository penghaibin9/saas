"""Offline contracts for Docker published-port exposure auditing."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/check-docker-port-exposure.py"
SPEC = importlib.util.spec_from_file_location("docker_port_exposure", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def container(*, host_ip="0.0.0.0", host_port="443", target="443/tcp",
              privileged=False, network_mode="default", publish_all=False,
              binds=None):
    return {
        "Id": "a" * 64,
        "HostConfig": {
            "Privileged": privileged,
            "NetworkMode": network_mode,
            "PublishAllPorts": publish_all,
            "Binds": [] if binds is None else binds,
        },
        "NetworkSettings": {
            "Ports": {target: [{"HostIp": host_ip, "HostPort": host_port}]}
        },
    }


def statuses(findings, check):
    return [item.status for item in findings if item.check == check]


class DockerRuntimeExposureTests(unittest.TestCase):
    def test_only_web_ports_may_bind_public_interfaces(self):
        findings = AUDIT.evaluate_containers([container(host_port="443")], {80, 443})
        self.assertNotIn(AUDIT.FAIL, statuses(findings, "docker.runtime.port_binding"))

    def test_database_public_binding_is_blocking(self):
        findings = AUDIT.evaluate_containers(
            [container(host_port="3306", target="3306/tcp")], {80, 443}
        )
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.runtime.port_binding"))

    def test_backend_public_binding_is_blocking(self):
        findings = AUDIT.evaluate_containers(
            [container(host_ip="::", host_port="8000", target="8000/tcp")], {80, 443}
        )
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.runtime.port_binding"))

    def test_loopback_only_internal_binding_is_allowed(self):
        findings = AUDIT.evaluate_containers(
            [container(host_ip="127.0.0.1", host_port="3306", target="3306/tcp")], {80, 443}
        )
        self.assertNotIn(AUDIT.FAIL, statuses(findings, "docker.runtime.port_binding"))

    def test_arbitrary_public_port_is_blocking(self):
        findings = AUDIT.evaluate_containers(
            [container(host_port="9000", target="9000/tcp")], {80, 443}
        )
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.runtime.port_binding"))

    def test_explicit_public_exception_is_narrow(self):
        findings = AUDIT.evaluate_containers(
            [container(host_port="9000", target="9000/tcp")], {80, 443, 9000}
        )
        self.assertNotIn(AUDIT.FAIL, statuses(findings, "docker.runtime.port_binding"))

    def test_publish_all_is_blocking(self):
        findings = AUDIT.evaluate_containers([container(publish_all=True)], {80, 443})
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.runtime.publish_all"))

    def test_privileged_is_blocking(self):
        findings = AUDIT.evaluate_containers([container(privileged=True)], {80, 443})
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.runtime.privileged"))

    def test_host_network_is_blocking(self):
        findings = AUDIT.evaluate_containers([container(network_mode="host")], {80, 443})
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.runtime.host_network"))

    def test_docker_socket_bind_is_blocking(self):
        findings = AUDIT.evaluate_containers(
            [container(binds=["/var/run/docker.sock:/var/run/docker.sock"])], {80, 443}
        )
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.runtime.socket_bind"))

    def test_unpublished_container_port_is_not_mistaken_for_public(self):
        item = container()
        item["NetworkSettings"]["Ports"] = {"3306/tcp": None}
        findings = AUDIT.evaluate_containers([item], {80, 443})
        self.assertNotIn(AUDIT.FAIL, statuses(findings, "docker.runtime.port_binding"))

    def test_no_running_container_is_visible_not_green(self):
        findings = AUDIT.evaluate_containers([], {80, 443})
        self.assertEqual(findings[0].status, AUDIT.WARN)


class DockerFirewallPolicyTests(unittest.TestCase):
    def test_default_docker_firewall_integration_passes(self):
        findings = AUDIT.evaluate_daemon({})
        self.assertNotIn(AUDIT.FAIL, [item.status for item in findings])

    def test_disabling_iptables_is_blocking(self):
        findings = AUDIT.evaluate_daemon({"iptables": False})
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.firewall.iptables"))

    def test_disabling_ip6tables_is_blocking(self):
        findings = AUDIT.evaluate_daemon({"ip6tables": False})
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.firewall.ip6tables"))

    def test_direct_routing_is_visible_as_warning(self):
        findings = AUDIT.evaluate_daemon({"allow-direct-routing": True})
        self.assertIn(AUDIT.WARN, statuses(findings, "docker.allow_direct_routing"))

    def test_nat_unprotected_bridge_mode_is_blocking(self):
        networks = [{
            "Id": "b" * 64,
            "Driver": "bridge",
            "Options": {"com.docker.network.bridge.gateway_mode_ipv4": "nat-unprotected"},
        }]
        findings = AUDIT.evaluate_networks(networks)
        self.assertIn(AUDIT.FAIL, statuses(findings, "docker.network.gateway_mode_ipv4"))

    def test_normal_nat_bridge_mode_passes(self):
        networks = [{"Id": "b" * 64, "Driver": "bridge", "Options": {}}]
        findings = AUDIT.evaluate_networks(networks)
        self.assertNotIn(AUDIT.FAIL, [item.status for item in findings])

    def test_trusted_host_interfaces_are_visible(self):
        networks = [{
            "Id": "b" * 64,
            "Driver": "bridge",
            "Options": {"com.docker.network.bridge.trusted_host_interfaces": "eth0"},
        }]
        findings = AUDIT.evaluate_networks(networks)
        self.assertIn(AUDIT.WARN, statuses(findings, "docker.network.trusted_host_interfaces"))


class DockerExposureArtifactTests(unittest.TestCase):
    def test_auditor_is_read_only(self):
        source = SCRIPT.read_text()
        forbidden = (
            "docker stop", "docker rm", "docker network rm", "docker restart",
            "iptables -A", "iptables -D", "nft add", "ufw enable", "ufw delete",
            "systemctl restart", "systemctl reload",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)
        self.assertIn('"mutatedHost": False', source)
        self.assertIn('"productionDataAccessed": False', source)
        self.assertIn('["docker", "inspect", *ids]', source)
        self.assertIn('["docker", "network", "inspect", *network_ids]', source)


if __name__ == "__main__":
    unittest.main()
