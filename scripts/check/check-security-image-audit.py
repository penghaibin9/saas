#!/usr/bin/env python3
"""Fail-closed policy for an actual Trivy image report, not a source-only audit."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

SCANNER_VERSION = "0.70.0"
SEVERITIES = ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")
BLOCKING = frozenset({"UNKNOWN", "HIGH", "CRITICAL"})
SHA = re.compile(r"[a-f0-9]{40}\Z")
IMAGE_ID = re.compile(r"sha256:[a-f0-9]{64}\Z")
# The workflow owns the reviewed tag choice. The receipt must contain an immutable
# digest from either the historical Docker Hub Python base or the reviewed UBI9
# Python 3.12 minimal base; mutable tags can never satisfy this identity check.
BASE_DIGEST = re.compile(
    r"(?:(?:docker\.io/library/)?python|registry\.access\.redhat\.com/ubi9/python-312-minimal)"
    r"@sha256:[a-f0-9]{64}\Z"
)
MAX_REPORT_BYTES = 64 * 1024 * 1024


class InvalidEvidence(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise InvalidEvidence(reason)


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value) -> datetime:
    require(isinstance(value, str), "SCAN_TIMESTAMP_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidEvidence("SCAN_TIMESTAMP_INVALID") from exc
    require(result.tzinfo is not None, "SCAN_TIMESTAMP_INVALID")
    return result.astimezone(timezone.utc)


def evaluate(report, receipt, *, source_sha: str, head_sha: str, now=None) -> dict:
    require(bool(SHA.fullmatch(source_sha)) and bool(SHA.fullmatch(head_sha)), "EXPECTED_COMMIT_INVALID")
    require(isinstance(receipt, dict), "BUILD_RECEIPT_REQUIRED")
    require(receipt.get("sourceSha") == source_sha and receipt.get("headSha") == head_sha,
            "BUILD_COMMIT_MISMATCH")
    image_id = receipt.get("imageId")
    require(isinstance(image_id, str) and bool(IMAGE_ID.fullmatch(image_id)), "BUILD_IMAGE_ID_INVALID")
    require(receipt.get("imageRef") == "pr265-image-audit:" + source_sha, "BUILD_IMAGE_REF_INVALID")
    require(isinstance(receipt.get("pythonBaseDigest"), str)
            and bool(BASE_DIGEST.fullmatch(receipt["pythonBaseDigest"])), "BUILD_BASE_DIGEST_REQUIRED")
    require(isinstance(report, dict), "SCAN_REPORT_REQUIRED")
    require(type(report.get("SchemaVersion")) is int and report["SchemaVersion"] == 2,
            "SCAN_SCHEMA_UNSUPPORTED")
    require(report.get("ArtifactType") == "container_image", "NOT_CONTAINER_IMAGE_SCAN")
    require(report.get("ArtifactName") == receipt["imageRef"], "SCANNED_IMAGE_REF_MISMATCH")
    require(isinstance(report.get("Trivy"), dict)
            and report["Trivy"].get("Version") == SCANNER_VERSION, "SCANNER_VERSION_MISMATCH")
    stamp = _timestamp(report.get("CreatedAt"))
    current = now or datetime.now(timezone.utc)
    require(current - timedelta(hours=6) <= stamp <= current + timedelta(minutes=5), "STALE_OR_FUTURE_SCAN")
    metadata = report.get("Metadata")
    require(isinstance(metadata, dict) and metadata.get("ImageID") == image_id,
            "SCANNED_IMAGE_ID_MISMATCH")
    os_info = metadata.get("OS")
    require(isinstance(os_info, dict) and _text(os_info.get("Family")) and _text(os_info.get("Name")),
            "OS_IDENTIFICATION_REQUIRED")
    require(os_info.get("EOSL", False) is False, "OS_EOL_OR_UNKNOWN_LIFECYCLE")
    results = report.get("Results")
    require(isinstance(results, list) and bool(results), "PACKAGE_RESULTS_REQUIRED")
    totals = dict.fromkeys(SEVERITIES, 0)
    inventory = {"os": 0, "python": 0}
    unfixed_blocking = 0
    for result in results:
        require(isinstance(result, dict), "RESULT_STRUCTURE_INVALID")
        require(not result.get("ExperimentalModifiedFindings"), "SUPPRESSED_FINDINGS_NOT_ALLOWED")
        cls, kind = result.get("Class"), result.get("Type")
        require(cls in {"os-pkgs", "lang-pkgs"} and _text(kind), "RESULT_CLASS_UNEXPECTED")
        packages = result.get("Packages")
        require(isinstance(packages, list) and bool(packages), "PACKAGE_INVENTORY_MISSING")
        for package in packages:
            require(isinstance(package, dict) and _text(package.get("Name")) and _text(package.get("Version")),
                    "PACKAGE_IDENTITY_INVALID")
        if cls == "os-pkgs":
            inventory["os"] += len(packages)
        if cls == "lang-pkgs" and kind == "python-pkg":
            inventory["python"] += len(packages)
        findings = result.get("Vulnerabilities", [])
        require(isinstance(findings, list), "FINDING_LIST_INVALID")
        for finding in findings:
            require(isinstance(finding, dict), "FINDING_STRUCTURE_INVALID")
            severity = finding.get("Severity")
            require(isinstance(severity, str) and severity in SEVERITIES, "FINDING_SEVERITY_INVALID")
            require(all(_text(finding.get(field)) for field in
                        ("VulnerabilityID", "PkgName", "InstalledVersion")), "FINDING_IDENTITY_INVALID")
            totals[severity] += 1
            if severity in BLOCKING and not _text(finding.get("FixedVersion")):
                unfixed_blocking += 1
    require(inventory["os"] > 0 and inventory["python"] > 0, "OS_AND_PYTHON_COVERAGE_REQUIRED")
    blockers = sum(totals[level] for level in BLOCKING)
    return {
        "scanEvidenceValid": True, "imageAuditPassed": blockers == 0,
        "releaseApproved": False, "sourceSha": source_sha, "headSha": head_sha,
        "imageId": image_id, "scannerVersion": SCANNER_VERSION,
        "scannedAt": stamp.isoformat(), "packageCounts": inventory,
        "findingCounts": totals, "blockingFindings": blockers,
        "unfixedBlockingFindings": unfixed_blocking,
        "errors": ["VULNERABILITY_REMEDIATION_REQUIRED"] if blockers else [],
        "productionDeployment": "NOT_PERFORMED", "businessSecurityAcceptance": "SEPARATE_GATE",
    }


def read_json(path: Path, *, limit: int):
    require(not path.is_symlink() and path.is_file(), "EVIDENCE_FILE_MISSING_OR_UNSAFE")
    require(0 < path.stat().st_size <= limit, "EVIDENCE_SIZE_INVALID")
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = evaluate(read_json(args.report, limit=MAX_REPORT_BYTES),
                           read_json(args.build_receipt, limit=16384),
                           source_sha=args.expected_source_sha, head_sha=args.expected_head_sha)
    except (InvalidEvidence, OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
        summary = {"scanEvidenceValid": False, "imageAuditPassed": False, "releaseApproved": False,
                   "errors": [str(exc) if isinstance(exc, InvalidEvidence) else "EVIDENCE_NOT_VALIDATED"]}
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2)
            stream.write("\n")
    except OSError:
        summary["imageAuditPassed"] = False
        summary["errors"] = sorted(set(summary["errors"] + ["RECEIPT_NOT_WRITTEN"]))
    print(json.dumps(summary, indent=2))
    return 0 if summary["imageAuditPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
