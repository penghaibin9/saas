#!/usr/bin/env python3
"""Fail-closed aggregator for final production-host technical evidence.

This tool only validates sanitized receipts generated on the target host. It does
not contact Tencent Cloud, mutate the host, or claim that manual control-plane,
identity-source, or recovery drills have happened. Those remain separate release
requirements in deploy/host/TENCENT_CLOUD_CONTROL_PLANE.md and README.md.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"


@dataclass(frozen=True)
class Finding:
    check: str
    status: str
    message: str
    evidence: str = ""


def _load_receipt(path: Path, label: str) -> tuple[dict | None, Finding | None]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, Finding(f"evidence.{label}.read", FAIL, f"{label} receipt is missing or invalid JSON")
    if not isinstance(value, dict):
        return None, Finding(f"evidence.{label}.shape", FAIL, f"{label} receipt must be a JSON object")
    return value, None


def _truth(value: dict, key: str) -> bool:
    return value.get(key) is True


def evaluate_host(receipt: dict) -> list[Finding]:
    return [
        Finding(
            "evidence.host.passed", PASS if _truth(receipt, "passed") else FAIL,
            "host security receipt must pass",
        ),
        Finding(
            "evidence.host.non_mutating",
            PASS if receipt.get("mutatedHost") is False else FAIL,
            "host security receipt must prove the auditor did not mutate the host",
        ),
        Finding(
            "evidence.host.no_production_data",
            PASS if receipt.get("productionDataAccessed") is False else FAIL,
            "host security audit must not access production application data",
        ),
    ]


def evaluate_docker(receipt: dict) -> list[Finding]:
    return [
        Finding(
            "evidence.docker.passed", PASS if _truth(receipt, "passed") else FAIL,
            "Docker runtime exposure receipt must pass",
        ),
        Finding(
            "evidence.docker.final_mode",
            PASS if receipt.get("preflightEmptyAllowed") is False else FAIL,
            "final release evidence must not come from --preflight-empty-ok mode",
        ),
        Finding(
            "evidence.docker.runtime_complete",
            PASS if _truth(receipt, "runtimeEvidenceComplete") else FAIL,
            "final Docker evidence requires actual running-container inspection",
        ),
        Finding(
            "evidence.docker.non_mutating",
            PASS if receipt.get("mutatedHost") is False else FAIL,
            "Docker runtime auditor must be non-mutating",
        ),
        Finding(
            "evidence.docker.no_production_data",
            PASS if receipt.get("productionDataAccessed") is False else FAIL,
            "Docker runtime audit must not access production application data",
        ),
    ]


def evaluate_dockerd(receipt: dict) -> list[Finding]:
    return [
        Finding(
            "evidence.dockerd.passed", PASS if _truth(receipt, "passed") else FAIL,
            "dockerd launch-flag receipt must pass",
        ),
        Finding(
            "evidence.dockerd.non_mutating",
            PASS if receipt.get("mutatedHost") is False else FAIL,
            "dockerd launch auditor must be non-mutating",
        ),
        Finding(
            "evidence.dockerd.no_production_data",
            PASS if receipt.get("productionDataAccessed") is False else FAIL,
            "dockerd launch audit must not access production application data",
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-report", type=Path, required=True)
    parser.add_argument("--docker-report", type=Path, required=True)
    parser.add_argument("--dockerd-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    loaded: dict[str, dict] = {}
    for label, path in (
        ("host", args.host_report),
        ("docker", args.docker_report),
        ("dockerd", args.dockerd_report),
    ):
        receipt, error = _load_receipt(path, label)
        if error:
            findings.append(error)
        else:
            assert receipt is not None
            loaded[label] = receipt

    if "host" in loaded:
        findings.extend(evaluate_host(loaded["host"]))
    if "docker" in loaded:
        findings.extend(evaluate_docker(loaded["docker"]))
    if "dockerd" in loaded:
        findings.extend(evaluate_dockerd(loaded["dockerd"]))

    failures = [item for item in findings if item.status == FAIL]
    result = {
        "schemaVersion": 1,
        "passed": not failures and len(loaded) == 3,
        "failureCount": len(failures),
        "technicalEvidenceComplete": len(loaded) == 3 and not failures,
        "cloudControlPlaneVerified": False,
        "identitySourcesVerified": False,
        "restoreDrillVerifiedByThisTool": False,
        "mutatedHost": False,
        "productionDataAccessed": False,
        "findings": [asdict(item) for item in findings],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
