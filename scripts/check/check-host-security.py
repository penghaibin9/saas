#!/usr/bin/env python3
"""Read-only production host security audit for the school lifecycle SaaS.

This script is intentionally non-mutating. It never edits SSH, firewall, Docker,
Nginx, sysctl, users, packages, or application data. Run it on the target CVM,
review the JSON receipt, then apply remediations explicitly from deploy/host/README.md.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
from typing import Iterable

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"
SENSITIVE_PORTS = {2375, 2376, 3306, 3310, 6379, 8000}
PUBLIC_WILDCARDS = {"0.0.0.0", "::", "*", "[::]"}


@dataclass(frozen=True)
class Finding:
    check: str
    status: str
    message: str
    evidence: str = ""


def _run(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, check=False, text=True, capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    output = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode, output


def _parse_key_value_lines(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if " " in line:
            key, value = line.split(None, 1)
        elif "=" in line:
            key, value = line.split("=", 1)
        else:
            continue
        result[key.strip().lower()] = value.strip().lower()
    return result


def evaluate_sshd(text: str, ssh_port: int) -> list[Finding]:
    cfg = _parse_key_value_lines(text)
    required = {
        "permitrootlogin": "no",
        "passwordauthentication": "no",
        "kbdinteractiveauthentication": "no",
        "pubkeyauthentication": "yes",
        "x11forwarding": "no",
        "allowagentforwarding": "no",
    }
    findings: list[Finding] = []
    for key, expected in required.items():
        actual = cfg.get(key)
        findings.append(Finding(
            "ssh." + key,
            PASS if actual == expected else FAIL,
            f"{key} must be {expected}",
            actual or "missing",
        ))
    try:
        port = int(cfg.get("port", str(ssh_port)).split()[0])
    except ValueError:
        port = -1
    findings.append(Finding("ssh.port", PASS if port == ssh_port else FAIL,
                            "effective SSH port must match audited port", str(port)))
    numeric_limits = {"maxauthtries": (1, 4), "logingracetime": (1, 60),
                      "clientaliveinterval": (1, 300), "clientalivecountmax": (0, 2)}
    for key, (minimum, maximum) in numeric_limits.items():
        raw = cfg.get(key, "")
        try:
            value = int(re.match(r"\d+", raw).group(0)) if re.match(r"\d+", raw) else -1
        except ValueError:
            value = -1
        findings.append(Finding("ssh." + key,
                                PASS if minimum <= value <= maximum else FAIL,
                                f"{key} must be between {minimum} and {maximum}", raw or "missing"))
    if cfg.get("allowtcpforwarding", "yes") != "no":
        findings.append(Finding("ssh.allowtcpforwarding", WARN,
                                "TCP forwarding is enabled; disable unless an operational use-case is approved",
                                cfg.get("allowtcpforwarding", "default=yes")))
    else:
        findings.append(Finding("ssh.allowtcpforwarding", PASS, "TCP forwarding disabled", "no"))
    return findings


def parse_ss_listeners(text: str) -> list[tuple[str, int]]:
    listeners: list[tuple[str, int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[4]
        if local.startswith("[") and "]:" in local:
            host, port_text = local.rsplit(":", 1)
            host = host.strip("[]") or "::"
        elif ":" in local:
            host, port_text = local.rsplit(":", 1)
        else:
            continue
        if port_text == "*" or not port_text.isdigit():
            continue
        listeners.append((host or "0.0.0.0", int(port_text)))
    return listeners


def _is_loopback(host: str) -> bool:
    normalized = host.strip("[]")
    return normalized in {"127.0.0.1", "::1", "localhost"} or normalized.startswith("127.")


def evaluate_listeners(listeners: Iterable[tuple[str, int]], ssh_port: int,
                       extra_public_ports: set[int]) -> list[Finding]:
    allowed_public = {ssh_port, 80, 443} | extra_public_ports
    findings: list[Finding] = []
    seen_sensitive: set[int] = set()
    for host, port in listeners:
        if port in SENSITIVE_PORTS:
            seen_sensitive.add(port)
            ok = _is_loopback(host)
            findings.append(Finding(
                f"listener.sensitive.{port}", PASS if ok else FAIL,
                "sensitive service must not bind a non-loopback host interface",
                f"{host}:{port}",
            ))
        if host in PUBLIC_WILDCARDS and port not in allowed_public:
            findings.append(Finding(
                f"listener.public.{port}", FAIL,
                "unexpected wildcard listener; only SSH/80/443 and explicit exceptions may be public",
                f"{host}:{port}",
            ))
    if not findings:
        findings.append(Finding("listener.surface", PASS, "no unexpected public/sensitive listeners found"))
    for port in sorted(SENSITIVE_PORTS - seen_sensitive):
        findings.append(Finding(f"listener.sensitive.{port}", PASS,
                                "sensitive port is not listening on the host", "not-listening"))
    return findings


def evaluate_sysctl(values: dict[str, str]) -> list[Finding]:
    exact = {
        "kernel.dmesg_restrict": "1",
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
    findings = [Finding("sysctl." + key, PASS if values.get(key) == expected else FAIL,
                        f"{key} must be {expected}", values.get(key, "missing"))
                for key, expected in exact.items()]
    for key, minimum in {"kernel.kptr_restrict": 1, "kernel.yama.ptrace_scope": 1}.items():
        try:
            current = int(values.get(key, "-1"))
        except ValueError:
            current = -1
        findings.append(Finding("sysctl." + key, PASS if current >= minimum else FAIL,
                                f"{key} must be >= {minimum}", values.get(key, "missing")))
    return findings


def evaluate_docker_daemon(config: dict) -> list[Finding]:
    findings: list[Finding] = []
    findings.append(Finding("docker.live_restore", PASS if config.get("live-restore") is True else FAIL,
                            "Docker live-restore must be enabled", repr(config.get("live-restore"))))
    hosts = config.get("hosts", [])
    tcp_hosts = [item for item in hosts if isinstance(item, str) and item.startswith("tcp://")]
    findings.append(Finding("docker.tcp_socket", FAIL if tcp_hosts else PASS,
                            "Docker daemon must not expose a TCP management socket",
                            ",".join(tcp_hosts) or "none"))
    insecure = config.get("insecure-registries", [])
    findings.append(Finding("docker.insecure_registries", FAIL if insecure else PASS,
                            "insecure container registries are not allowed", repr(insecure)))
    driver = config.get("log-driver", "json-file")
    opts = config.get("log-opts", {}) if isinstance(config.get("log-opts", {}), dict) else {}
    rotated = driver == "local" or (driver == "json-file" and bool(opts.get("max-size")) and bool(opts.get("max-file")))
    findings.append(Finding("docker.log_rotation", PASS if rotated else FAIL,
                            "Docker logs must use local driver or bounded json-file rotation",
                            f"driver={driver},opts={opts}"))
    return findings


def evaluate_secret_mode(mode: int, owner_uid: int, current_uid: int) -> list[Finding]:
    writable_by_group_or_other = bool(mode & (stat.S_IWGRP | stat.S_IWOTH))
    readable_by_other = bool(mode & stat.S_IROTH)
    owner_ok = owner_uid in {0, current_uid}
    ok = not writable_by_group_or_other and not readable_by_other and owner_ok
    return [Finding("file.secret_permissions", PASS if ok else FAIL,
                    "secret files must be root/current-user owned, not other-readable, not group/other-writable",
                    f"mode={oct(mode & 0o777)},uid={owner_uid}")]


def _read_sysctl(key: str) -> str:
    path = Path("/proc/sys") / key.replace(".", "/")
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _collect_sshd() -> tuple[str, str]:
    if shutil.which("sshd"):
        code, output = _run(["sshd", "-T"])
        if code == 0 and output:
            return output, "sshd -T"
    path = Path("/etc/ssh/sshd_config")
    if path.is_file():
        try:
            return path.read_text(errors="replace"), str(path)
        except OSError:
            pass
    return "", "unavailable"


def _collect_findings(args: argparse.Namespace) -> list[Finding]:
    findings: list[Finding] = []
    sshd, source = _collect_sshd()
    if sshd:
        findings.extend(evaluate_sshd(sshd, args.ssh_port))
        findings.append(Finding("ssh.source", PASS if source == "sshd -T" else WARN,
                                "effective sshd -T is preferred over raw config", source))
    else:
        findings.append(Finding("ssh.available", FAIL, "SSH effective configuration could not be read"))

    if shutil.which("ss"):
        code, output = _run(["ss", "-H", "-lntup"])
        if code == 0:
            findings.extend(evaluate_listeners(parse_ss_listeners(output), args.ssh_port, set(args.allow_public_port)))
        else:
            findings.append(Finding("listener.collect", FAIL, "could not enumerate listening sockets"))
    else:
        findings.append(Finding("listener.collect", FAIL, "ss command is required for listener audit"))

    keys = [
        "kernel.dmesg_restrict", "kernel.kptr_restrict", "kernel.yama.ptrace_scope",
        "fs.protected_hardlinks", "fs.protected_symlinks", "fs.suid_dumpable",
        "net.ipv4.tcp_syncookies", "net.ipv4.conf.all.accept_redirects",
        "net.ipv4.conf.default.accept_redirects", "net.ipv4.conf.all.send_redirects",
        "net.ipv4.conf.default.send_redirects", "net.ipv6.conf.all.accept_redirects",
        "net.ipv6.conf.default.accept_redirects",
    ]
    findings.extend(evaluate_sysctl({key: _read_sysctl(key) for key in keys}))

    daemon_path = Path(args.docker_daemon_json)
    if daemon_path.is_file():
        try:
            daemon = json.loads(daemon_path.read_text())
            findings.extend(evaluate_docker_daemon(daemon))
        except (OSError, json.JSONDecodeError, TypeError):
            findings.append(Finding("docker.daemon_json", FAIL, "Docker daemon.json is unreadable or invalid JSON"))
    else:
        findings.append(Finding("docker.daemon_json", FAIL,
                                "checked Docker daemon.json is required on the production host", str(daemon_path)))

    docker_sock = Path("/var/run/docker.sock")
    if docker_sock.exists():
        try:
            st = docker_sock.stat()
            unsafe = bool(st.st_mode & (stat.S_IWOTH | stat.S_IROTH))
            findings.append(Finding("docker.socket_permissions", FAIL if unsafe else PASS,
                                    "Docker socket must not be world-readable/writable",
                                    f"mode={oct(st.st_mode & 0o777)},uid={st.st_uid},gid={st.st_gid}"))
        except OSError:
            findings.append(Finding("docker.socket_permissions", FAIL, "Docker socket permissions unreadable"))
    else:
        findings.append(Finding("docker.socket_permissions", WARN, "Docker socket not found on this host"))

    for raw in args.secret_path:
        path = Path(raw)
        try:
            st = path.stat()
            for finding in evaluate_secret_mode(st.st_mode, st.st_uid, os.geteuid()):
                findings.append(Finding(f"secret.{path}", finding.status, finding.message, finding.evidence))
        except OSError:
            findings.append(Finding(f"secret.{path}", FAIL, "configured secret path is missing or unreadable"))

    if shutil.which("systemctl"):
        for unit in ("docker.service", "nginx.service"):
            active, _ = _run(["systemctl", "is-active", "--quiet", unit])
            findings.append(Finding("service." + unit, PASS if active == 0 else FAIL,
                                    f"{unit} must be active"))
        ntp, value = _run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"])
        findings.append(Finding("time.ntp", PASS if ntp == 0 and value.lower() == "yes" else FAIL,
                                "host clock must be NTP synchronized", value or "unknown"))
        enabled, _ = _run(["systemctl", "is-enabled", "--quiet", "apt-daily-upgrade.timer"])
        findings.append(Finding("patching.timer", PASS if enabled == 0 else WARN,
                                "automatic security-update timer should be enabled on Ubuntu/Debian hosts"))
    else:
        findings.append(Finding("systemd.available", WARN, "systemd checks skipped"))

    apparmor = Path("/sys/module/apparmor/parameters/enabled")
    if apparmor.is_file():
        try:
            enabled = apparmor.read_text().strip().upper().startswith("Y")
        except OSError:
            enabled = False
        findings.append(Finding("lsm.apparmor", PASS if enabled else WARN,
                                "AppArmor should be enabled on Ubuntu production hosts"))

    journal = Path("/var/log/journal")
    findings.append(Finding("logging.persistent_journal", PASS if journal.is_dir() else WARN,
                            "persistent journald storage is recommended", str(journal)))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--allow-public-port", type=int, action="append", default=[])
    parser.add_argument("--secret-path", action="append", default=[])
    parser.add_argument("--docker-daemon-json", default="/etc/docker/daemon.json")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if not (1 <= args.ssh_port <= 65535):
        parser.error("--ssh-port must be 1..65535")
    if any(port < 1 or port > 65535 for port in args.allow_public_port):
        parser.error("--allow-public-port must be 1..65535")

    findings = _collect_findings(args)
    failures = [item for item in findings if item.status == FAIL]
    warnings = [item for item in findings if item.status == WARN]
    receipt = {
        "schemaVersion": 1,
        "hostname": socket.gethostname(),
        "passed": not failures,
        "failureCount": len(failures),
        "warningCount": len(warnings),
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
