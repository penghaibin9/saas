#!/usr/bin/env python3
"""Read-only Docker runtime exposure audit for production hosts.

Docker-published ports can bypass UFW's INPUT/OUTPUT filtering. This auditor reads
Docker's actual running container/network state and fails closed on unexpected
public bindings. It does not mutate Docker, firewall rules, containers, networks,
or production data.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
import subprocess

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SENSITIVE_PORTS = {2375, 2376, 3306, 3310, 6379, 8000}
DEFAULT_PUBLIC_PORTS = {80, 443}
WILDCARDS = {"", "0.0.0.0", "::", "[::]", "*"}


@dataclass(frozen=True)
class Finding:
    check: str
    status: str
    message: str
    evidence: str = ""


def _run(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, check=False, text=True, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return proc.returncode, (proc.stdout or proc.stderr or "").strip()


def _is_loopback(host: str) -> bool:
    normalized = (host or "").strip("[]")
    return normalized == "::1" or normalized == "localhost" or normalized.startswith("127.")


def evaluate_daemon(config: dict) -> list[Finding]:
    findings: list[Finding] = []
    for key in ("iptables", "ip6tables"):
        disabled = config.get(key) is False
        findings.append(Finding(
            f"docker.firewall.{key}",
            FAIL if disabled else PASS,
            f"Docker {key} integration must not be disabled without an independently reviewed replacement policy",
            "false" if disabled else "default-or-enabled",
        ))
    direct = config.get("allow-direct-routing") is True
    findings.append(Finding(
        "docker.allow_direct_routing",
        WARN if direct else PASS,
        "allow-direct-routing broadens direct access to published container ports; require explicit network review",
        "enabled" if direct else "disabled-or-default",
    ))
    return findings


def evaluate_containers(containers: list[dict], allowed_public_ports: set[int]) -> list[Finding]:
    findings: list[Finding] = []
    if not containers:
        return [Finding("docker.runtime.containers", FAIL,
                        "no running containers were returned; production runtime exposure is not proven")]

    for item in containers:
        cid = str(item.get("Id", "unknown"))[:12]
        host_config = item.get("HostConfig") if isinstance(item.get("HostConfig"), dict) else {}
        network_settings = item.get("NetworkSettings") if isinstance(item.get("NetworkSettings"), dict) else {}

        privileged = host_config.get("Privileged") is True
        findings.append(Finding(
            "docker.runtime.privileged",
            FAIL if privileged else PASS,
            "production containers must not run privileged",
            f"container={cid}",
        ))

        network_mode = str(host_config.get("NetworkMode", ""))
        host_network = network_mode == "host"
        findings.append(Finding(
            "docker.runtime.host_network",
            FAIL if host_network else PASS,
            "host network mode bypasses normal published-port boundaries",
            f"container={cid},mode={network_mode or 'default'}",
        ))

        publish_all = host_config.get("PublishAllPorts") is True
        findings.append(Finding(
            "docker.runtime.publish_all",
            FAIL if publish_all else PASS,
            "--publish-all/-P is not allowed in production",
            f"container={cid}",
        ))

        binds = host_config.get("Binds") if isinstance(host_config.get("Binds"), list) else []
        socket_bind = any("/var/run/docker.sock" in str(bind) for bind in binds)
        findings.append(Finding(
            "docker.runtime.socket_bind",
            FAIL if socket_bind else PASS,
            "production containers must not mount the Docker daemon socket",
            f"container={cid}",
        ))

        ports = network_settings.get("Ports") if isinstance(network_settings.get("Ports"), dict) else {}
        saw_binding = False
        for container_port, bindings in ports.items():
            target_text = str(container_port).split("/", 1)[0]
            try:
                target_port = int(target_text)
            except ValueError:
                findings.append(Finding("docker.runtime.port_binding", FAIL,
                                        "Docker target port identity is invalid",
                                        f"container={cid},target=invalid"))
                continue
            if not bindings:
                continue
            if not isinstance(bindings, list):
                findings.append(Finding("docker.runtime.port_binding", FAIL,
                                        "Docker port binding structure is unexpected",
                                        f"container={cid},target={container_port}"))
                continue
            for binding in bindings:
                if not isinstance(binding, dict):
                    findings.append(Finding("docker.runtime.port_binding", FAIL,
                                            "Docker port binding structure is unexpected",
                                            f"container={cid},target={container_port}"))
                    continue
                saw_binding = True
                host_ip = str(binding.get("HostIp") or "")
                host_port_text = str(binding.get("HostPort") or "")
                try:
                    host_port = int(host_port_text)
                except ValueError:
                    findings.append(Finding("docker.runtime.port_binding", FAIL,
                                            "Docker published host port is invalid",
                                            f"container={cid},host={host_ip or '*'},port=invalid"))
                    continue

                public_binding = host_ip in WILDCARDS or not _is_loopback(host_ip)
                sensitive = host_port in SENSITIVE_PORTS or target_port in SENSITIVE_PORTS
                unexpected_public = public_binding and host_port not in allowed_public_ports
                blocked = (sensitive and public_binding) or unexpected_public
                findings.append(Finding(
                    "docker.runtime.port_binding",
                    FAIL if blocked else PASS,
                    "only approved web ports may bind non-loopback interfaces; sensitive host or target ports remain blocked",
                    f"container={cid},host={host_ip or '*'},port={host_port},target={target_port}",
                ))
        if not saw_binding:
            findings.append(Finding("docker.runtime.port_binding", PASS,
                                    "container has no host-published ports",
                                    f"container={cid}"))
    return findings


def evaluate_networks(networks: list[dict]) -> list[Finding]:
    findings: list[Finding] = []
    for item in networks:
        if not isinstance(item, dict) or item.get("Driver") != "bridge":
            continue
        network_id = str(item.get("Id", "unknown"))[:12]
        options = item.get("Options") if isinstance(item.get("Options"), dict) else {}
        for family in ("ipv4", "ipv6"):
            key = f"com.docker.network.bridge.gateway_mode_{family}"
            value = str(options.get(key, "nat"))
            findings.append(Finding(
                f"docker.network.gateway_mode_{family}",
                FAIL if value == "nat-unprotected" else PASS,
                "nat-unprotected permits direct access without normal port filtering",
                f"network={network_id},mode={value}",
            ))
        trusted = str(options.get("com.docker.network.bridge.trusted_host_interfaces", "")).strip()
        if trusted:
            findings.append(Finding(
                "docker.network.trusted_host_interfaces",
                WARN,
                "trusted host interfaces enable direct routed access; require explicit architecture review",
                f"network={network_id},configured=yes",
            ))
    if not findings:
        findings.append(Finding("docker.network.bridge_policy", PASS,
                                "no unsafe bridge gateway mode found"))
    return findings


def _load_json(text: str, description: str) -> list | dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(description + " returned invalid JSON") from exc
    if not isinstance(value, (list, dict)):
        raise ValueError(description + " returned unexpected JSON")
    return value


def collect_runtime() -> tuple[list[dict], list[dict], list[Finding]]:
    findings: list[Finding] = []
    if not shutil.which("docker"):
        return [], [], [Finding("docker.runtime.cli", FAIL, "Docker CLI is required on the production host")]

    code, ids_text = _run(["docker", "ps", "-q"])
    if code != 0:
        return [], [], [Finding("docker.runtime.inspect", FAIL,
                                "running containers could not be enumerated; run audit with Docker read access")]
    ids = [item for item in ids_text.splitlines() if item.strip()]
    containers: list[dict] = []
    if ids:
        code, inspect_text = _run(["docker", "inspect", *ids])
        if code != 0:
            findings.append(Finding("docker.runtime.inspect", FAIL,
                                    "running containers could not be inspected"))
        else:
            try:
                value = _load_json(inspect_text, "docker inspect")
            except ValueError:
                findings.append(Finding("docker.runtime.inspect", FAIL,
                                        "docker inspect returned invalid or unexpected JSON"))
            else:
                if not isinstance(value, list):
                    findings.append(Finding("docker.runtime.inspect", FAIL,
                                            "docker inspect did not return a list"))
                else:
                    containers = [item for item in value if isinstance(item, dict)]
                    if len(containers) != len(ids):
                        findings.append(Finding("docker.runtime.inspect", FAIL,
                                                "not every running container produced a valid inspect record"))

    code, network_ids_text = _run(["docker", "network", "ls", "-q"])
    networks: list[dict] = []
    if code != 0:
        findings.append(Finding("docker.network.inspect", FAIL, "Docker networks could not be enumerated"))
    else:
        network_ids = [item for item in network_ids_text.splitlines() if item.strip()]
        if network_ids:
            code, network_text = _run(["docker", "network", "inspect", *network_ids])
            if code != 0:
                findings.append(Finding("docker.network.inspect", FAIL, "Docker networks could not be inspected"))
            else:
                try:
                    value = _load_json(network_text, "docker network inspect")
                except ValueError:
                    findings.append(Finding("docker.network.inspect", FAIL,
                                            "docker network inspect returned invalid or unexpected JSON"))
                else:
                    if isinstance(value, list):
                        networks = [item for item in value if isinstance(item, dict)]
                        if len(networks) != len(network_ids):
                            findings.append(Finding("docker.network.inspect", FAIL,
                                                    "not every Docker network produced a valid inspect record"))
                    else:
                        findings.append(Finding("docker.network.inspect", FAIL,
                                                "docker network inspect did not return a list"))
    return containers, networks, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-port", type=int, action="append", default=[])
    parser.add_argument("--docker-daemon-json", default="/etc/docker/daemon.json")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    allowed_public_ports = DEFAULT_PUBLIC_PORTS | set(args.allow_public_port)
    if any(port < 1 or port > 65535 for port in allowed_public_ports):
        parser.error("public ports must be 1..65535")

    findings: list[Finding] = []
    daemon_path = Path(args.docker_daemon_json)
    if daemon_path.is_file():
        try:
            daemon = json.loads(daemon_path.read_text())
            if not isinstance(daemon, dict):
                raise ValueError
            findings.extend(evaluate_daemon(daemon))
        except (OSError, json.JSONDecodeError, ValueError):
            findings.append(Finding("docker.daemon_json", FAIL,
                                    "Docker daemon.json is unreadable or invalid"))
    else:
        findings.append(Finding("docker.daemon_json", FAIL,
                                "Docker daemon.json is required for runtime exposure audit"))

    containers, networks, collection_findings = collect_runtime()
    findings.extend(collection_findings)
    findings.extend(evaluate_containers(containers, allowed_public_ports))
    findings.extend(evaluate_networks(networks))

    failures = [item for item in findings if item.status == FAIL]
    warnings = [item for item in findings if item.status == WARN]
    receipt = {
        "schemaVersion": 1,
        "passed": not failures,
        "failureCount": len(failures),
        "warningCount": len(warnings),
        "allowedPublicPorts": sorted(allowed_public_ports),
        "mutatedHost": False,
        "productionDataAccessed": False,
        "findings": [asdict(item) for item in findings],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
