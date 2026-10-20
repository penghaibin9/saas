#!/usr/bin/env python3
"""Read-only audit of the actual dockerd process launch arguments.

This closes the gap where /etc/docker/daemon.json looks safe but systemd ExecStart
(or another supervisor) passes unsafe daemon flags. The auditor only reads /proc
and emits JSON; it never signals, restarts, or reconfigures Docker.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@dataclass(frozen=True)
class Finding:
    check: str
    status: str
    message: str
    evidence: str = ""


def _bool_option(argv: list[str], name: str) -> bool | None:
    """Return explicit boolean for --name[=value], else None when not specified."""
    prefix = f"--{name}="
    for index, arg in enumerate(argv):
        if arg == f"--{name}":
            if index + 1 < len(argv) and argv[index + 1].lower() in {"true", "false"}:
                return argv[index + 1].lower() == "true"
            return True
        if arg.startswith(prefix):
            value = arg[len(prefix):].lower()
            if value in {"true", "false"}:
                return value == "true"
    return None


def _host_values(argv: list[str]) -> list[str]:
    values: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-H", "--host"}:
            if index + 1 < len(argv):
                values.append(argv[index + 1])
                index += 2
                continue
        elif arg.startswith("--host="):
            values.append(arg.split("=", 1)[1])
        elif arg.startswith("-H="):
            values.append(arg.split("=", 1)[1])
        elif arg.startswith("-H") and len(arg) > 2:
            values.append(arg[2:])
        index += 1
    return values


def evaluate_argv(argv: list[str]) -> list[Finding]:
    findings: list[Finding] = []

    for name in ("iptables", "ip6tables"):
        value = _bool_option(argv, name)
        findings.append(Finding(
            f"dockerd.launch.{name}",
            FAIL if value is False else PASS,
            f"dockerd must not disable {name} integration through launch flags",
            "explicit=false" if value is False else ("explicit=true" if value is True else "not-overridden"),
        ))

    hosts = _host_values(argv)
    tcp_hosts = [value for value in hosts if value.lower().startswith("tcp://")]
    findings.append(Finding(
        "dockerd.launch.tcp_host",
        FAIL if tcp_hosts else PASS,
        "dockerd launch flags must not expose a TCP management socket",
        ",".join(tcp_hosts) if tcp_hosts else "none",
    ))

    direct = _bool_option(argv, "allow-direct-routing")
    findings.append(Finding(
        "dockerd.launch.allow_direct_routing",
        WARN if direct is True else PASS,
        "allow-direct-routing requires an explicit Docker network architecture review",
        "explicit=true" if direct is True else ("explicit=false" if direct is False else "not-overridden"),
    ))

    tlsverify = _bool_option(argv, "tlsverify")
    if tcp_hosts:
        findings.append(Finding(
            "dockerd.launch.tlsverify",
            FAIL,
            "TCP Docker management sockets are forbidden even when TLS verification is configured",
            "tcp-management-forbidden",
        ))
    elif tlsverify is False:
        findings.append(Finding(
            "dockerd.launch.tlsverify",
            WARN,
            "tlsverify=false is unnecessary without a TCP management socket and should be removed",
            "explicit=false",
        ))
    else:
        findings.append(Finding("dockerd.launch.tlsverify", PASS,
                                "no unsafe Docker TCP/TLS launch override found"))
    return findings


def collect_dockerd_argv(proc_root: Path = Path("/proc")) -> tuple[list[str], Finding]:
    try:
        proc = subprocess.run(["pgrep", "-xo", "dockerd"], check=False, text=True,
                              capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return [], Finding("dockerd.process", FAIL, "could not locate dockerd process")
    if proc.returncode != 0 or not proc.stdout.strip().isdigit():
        return [], Finding("dockerd.process", FAIL,
                           "dockerd process is not running or cannot be identified")
    pid = proc.stdout.strip()
    cmdline = proc_root / pid / "cmdline"
    try:
        raw = cmdline.read_bytes()
    except OSError:
        return [], Finding("dockerd.process", FAIL,
                           "dockerd command line is unreadable; run audit with sufficient read privileges")
    argv = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
    if not argv:
        return [], Finding("dockerd.process", FAIL, "dockerd command line is empty")
    return argv, Finding("dockerd.process", PASS, "actual dockerd process arguments collected",
                         f"pid={pid},argc={len(argv)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    dockerd_argv, process_finding = collect_dockerd_argv()
    findings = [process_finding]
    if dockerd_argv:
        findings.extend(evaluate_argv(dockerd_argv))

    failures = [item for item in findings if item.status == FAIL]
    warnings = [item for item in findings if item.status == WARN]
    receipt = {
        "schemaVersion": 1,
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
