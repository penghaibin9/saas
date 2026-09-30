"""Offline contracts for effective Docker container-isolation auditing."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/check-docker-port-exposure.py"
SPEC = importlib.util.spec_from_file_location("docker_runtime_isolation", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def base_container() -> dict:
    return {
        "Id": "c" * 64,
        "HostConfig": {
            "Privileged": False,
            "NetworkMode": "default",
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "",
            "UsernsMode": "",
            "PublishAllPorts": False,
            "CapAdd": None,
            "Devices": [],
            "DeviceRequests": [],
            "SecurityOpt": ["no-new-privileges:true"],
            "Binds": [],
        },
        "Mounts": [],
        "NetworkSettings": {"Ports": {}},
    }


def status(findings: list, check: str) -> str:
    matches = [item.status for item in findings if item.check == check]
    if not matches:
        raise AssertionError(f"missing finding: {check}")
    return matches[-1]


class DockerRuntimeIsolationTests(unittest.TestCase):
    def test_reviewed_default_isolation_passes(self):
        findings = AUDIT.evaluate_container_isolation(base_container())
        self.assertNotIn(AUDIT.FAIL, [item.status for item in findings])

    def test_host_namespaces_are_blocking(self):
        cases = (
            ("NetworkMode", "docker.runtime.host_network"),
            ("PidMode", "docker.runtime.host_pid"),
            ("IpcMode", "docker.runtime.host_ipc"),
            ("UTSMode", "docker.runtime.host_uts"),
            ("UsernsMode", "docker.runtime.host_userns"),
        )
        for field, check in cases:
            with self.subTest(field=field):
                item = base_container()
                item["HostConfig"][field] = "host"
                self.assertEqual(status(AUDIT.evaluate_container_isolation(item), check), AUDIT.FAIL)

    def test_added_capability_is_blocking(self):
        item = base_container()
        item["HostConfig"]["CapAdd"] = ["SYS_ADMIN"]
        self.assertEqual(
            status(AUDIT.evaluate_container_isolation(item), "docker.runtime.cap_add"),
            AUDIT.FAIL,
        )

    def test_host_device_or_device_request_is_blocking(self):
        item = base_container()
        item["HostConfig"]["Devices"] = [{"PathOnHost": "/dev/sda"}]
        self.assertEqual(
            status(AUDIT.evaluate_container_isolation(item), "docker.runtime.devices"),
            AUDIT.FAIL,
        )
        item = base_container()
        item["HostConfig"]["DeviceRequests"] = [{"Driver": "nvidia"}]
        self.assertEqual(
            status(AUDIT.evaluate_container_isolation(item), "docker.runtime.devices"),
            AUDIT.FAIL,
        )

    def test_unconfined_security_options_are_blocking(self):
        for option in (
            "seccomp=unconfined",
            "apparmor=unconfined",
            "systempaths=unconfined",
            "label=disable",
        ):
            with self.subTest(option=option):
                item = base_container()
                item["HostConfig"]["SecurityOpt"] = [option]
                self.assertEqual(
                    status(AUDIT.evaluate_container_isolation(item), "docker.runtime.security_opt"),
                    AUDIT.FAIL,
                )

    def test_docker_socket_is_detected_from_mounts_not_only_binds(self):
        item = base_container()
        item["Mounts"] = [{
            "Type": "bind",
            "Source": "/var/run/docker.sock",
            "Destination": "/run/docker.sock",
        }]
        self.assertEqual(
            status(AUDIT.evaluate_container_isolation(item), "docker.runtime.socket_bind"),
            AUDIT.FAIL,
        )

    def test_docker_socket_destination_alias_is_also_blocking(self):
        item = base_container()
        item["Mounts"] = [{
            "Type": "bind",
            "Source": "/tmp/daemon.sock",
            "Destination": "/var/run/docker.sock",
        }]
        self.assertEqual(
            status(AUDIT.evaluate_container_isolation(item), "docker.runtime.socket_bind"),
            AUDIT.FAIL,
        )


if __name__ == "__main__":
    unittest.main()
