#!/usr/bin/env python3
"""Promote reviewed M0 evidence into the non-destructive M1 entry gate.

This gate can finish M0 for commerce construction while keeping module deletion
strictly disabled. M5/M6 must re-run open-world consumer/resource closure before
any purge selector or irreversible operation can be approved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def unique_json(path: Path) -> dict:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("DUPLICATE_JSON_KEY")
            out[key] = value
        return out
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def assess(source: dict, schema_review: dict, boundaries: dict, contract: dict) -> dict:
    sha = source.get("sourceSha")
    if not isinstance(sha, str) or len(sha) != 40:
        raise ValueError("INVALID_SOURCE_SHA")
    for item in (schema_review, boundaries):
        if item.get("sourceSha") != sha or item.get("sourceManifestHash") != source.get("sourceManifestHash"):
            raise ValueError("M0_EVIDENCE_IDENTITY_MISMATCH")
    if schema_review.get("status") != "DISPOSITIONS_VERIFIED_NOT_REMEDIATED":
        raise ValueError("SCHEMA_DISPOSITIONS_NOT_VERIFIED")
    if boundaries.get("status") != "STRUCTURAL_BOUNDARY_ASSERTIONS_VERIFIED":
        raise ValueError("BOUNDARIES_NOT_VERIFIED")
    if schema_review.get("deletionAuthorized") is not False or boundaries.get("deletionAuthorized") is not False:
        raise ValueError("UPSTREAM_EVIDENCE_MUST_NOT_AUTHORIZE_DELETION")
    if contract.get("schemaVersion") != 1 or contract.get("artifactType") != "M0_COMMERCIAL_BUILD_EXIT_CONTRACT":
        raise ValueError("INVALID_STAGE_CONTRACT")
    if contract.get("canonicalFeatures") != source.get("moduleMapping", {}).get("canonicalFeatures"):
        raise ValueError("MODULE_MAPPING_CHANGED")
    for name in ("implicitEmployment", "implicitApiAccess", "purgeScopeComplete", "deletionAuthorized"):
        if contract.get(name) is not False:
            raise ValueError("M0_CANNOT_WIDEN_OR_AUTHORIZE_DELETION")
    if contract.get("m0Complete") is not True or contract.get("m1EntryApproved") is not True:
        raise ValueError("M0_STAGE_APPROVAL_MISSING")
    retention = contract.get("retentionPolicy") or {}
    if retention.get("mode") != "EXPLICIT_CONTRACT_OR_PUBLISHED_POLICY_REQUIRED" or retention.get("defaultDays") is not None or retention.get("missingPolicyAction") != "BLOCK_DESTRUCTIVE_EXIT":
        raise ValueError("RETENTION_POLICY_MUST_FAIL_CLOSED")
    recipient = contract.get("schoolRecipientPolicy") or {}
    if recipient.get("namedRecipientRequired") is not True or recipient.get("receiptBoundToExportManifest") is not True:
        raise ValueError("SCHOOL_RECIPIENT_POLICY_INCOMPLETE")
    backup = contract.get("backupDispositionPolicy") or {}
    if backup.get("explicitPolicyReferenceRequired") is not True or backup.get("onlinePurgeDoesNotClaimBackupErasure") is not True:
        raise ValueError("BACKUP_DISPOSITION_POLICY_INCOMPLETE")
    if contract.get("unknownResourcePolicy") != "FAIL_CLOSED_FOR_DELETION":
        raise ValueError("UNKNOWN_RESOURCES_MUST_FAIL_CLOSED")
    return {
        "schemaVersion": 1,
        "artifactType": "M0_COMMERCIAL_BUILD_EXIT",
        "sourceSha": sha,
        "sourceManifestHash": source.get("sourceManifestHash"),
        "status": "M0_COMPLETE_M1_ENTRY_APPROVED_DELETION_BLOCKED",
        "m0Complete": True,
        "m1EntryApproved": True,
        "purgeScopeComplete": False,
        "deletionAuthorized": False,
        "nextStage": "M1",
        "destructiveExitGate": "M5_M6_REVIEW_REQUIRED"
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("inventory", "schema-review", "boundaries", "contract", "output"):
        parser.add_argument("--" + flag, required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        parser.error("output must be new")
    result = assess(
        unique_json(args.inventory), unique_json(args.schema_review),
        unique_json(args.boundaries), unique_json(args.contract),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
