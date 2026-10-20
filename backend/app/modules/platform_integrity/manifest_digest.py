"""Pinned canonical digest for new platform frozen manifests.

Only persisted immutable manifest/item fields participate. Operational state,
package pointers, update timestamps, operators and retry counters are excluded.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Iterable

PLATFORM_BUSINESS_SNAPSHOT = "PLATFORM_BUSINESS_SNAPSHOT"
PLATFORM_MANIFEST_DIGEST_V1 = "PLATFORM_MANIFEST_DIGEST_V1"


def _text(value) -> str:
    return "" if value is None else str(value)


def _time(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        # The authoritative manifest timestamp columns are MySQL DATETIME(0).
        # MySQL rounds fractional seconds (rather than merely truncating), so
        # mirror that persistence rule before hashing.
        rounded = value + timedelta(seconds=1) if value.microsecond >= 500_000 else value
        return rounded.replace(microsecond=0).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def ordered_items(items: Iterable[object]) -> list[object]:
    return sorted(
        items,
        key=lambda item: (
            int(getattr(item, "sort_no", 0) or 0),
            _text(getattr(item, "material_code", "")),
            int(getattr(item, "version_id", 0) or 0),
            int(getattr(item, "id", 0) or 0),
        ),
    )


def is_platform_frozen_manifest(items: Iterable[object]) -> bool:
    return any(
        _text(getattr(item, "material_code", "")).upper() == PLATFORM_BUSINESS_SNAPSHOT
        for item in items
    )


def canonical_manifest_payload(manifest: object, items: Iterable[object]) -> dict:
    pinned_items = []
    for item in ordered_items(items):
        pinned_items.append({
            "itemId": int(getattr(item, "id", 0) or 0),
            "materialCode": _text(getattr(item, "material_code", "")),
            "assetId": int(getattr(item, "asset_id", 0) or 0),
            "versionId": int(getattr(item, "version_id", 0) or 0),
            "fileObjectId": int(getattr(item, "file_object_id", 0) or 0),
            "fileNameSnapshot": _text(getattr(item, "file_name_snapshot", "")),
            "sizeSnapshot": int(getattr(item, "size_snapshot", 0) or 0),
            "sha256Snapshot": _text(getattr(item, "sha256_snapshot", "")).lower(),
            "reviewStatus": _text(getattr(item, "review_status", "")),
            "scanResult": _text(getattr(item, "scan_result", "")),
            "uploaderSnapshot": _text(getattr(item, "uploader_snapshot", "")),
            "submittedAtSnapshot": _time(getattr(item, "submitted_at_snapshot", None)),
            "sortNo": int(getattr(item, "sort_no", 0) or 0),
        })
    return {
        "digestSchemaVersion": PLATFORM_MANIFEST_DIGEST_V1,
        "manifestId": int(getattr(manifest, "id", 0) or 0),
        "tenantId": int(getattr(manifest, "tenant_id", 0) or 0),
        "moduleCode": _text(getattr(manifest, "module_code", "")),
        "archiveType": _text(getattr(manifest, "archive_type", "")),
        "targetType": _text(getattr(manifest, "target_type", "")),
        "targetId": _text(getattr(manifest, "target_id", "")),
        "revision": int(getattr(manifest, "revision", 1) or 1),
        "ruleVersion": _text(getattr(manifest, "rule_version", "")),
        "items": pinned_items,
    }


def canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def platform_manifest_digest(manifest: object, items: Iterable[object]) -> str:
    return hashlib.sha256(canonical_json_bytes(canonical_manifest_payload(manifest, items))).hexdigest()


__all__ = [
    "PLATFORM_BUSINESS_SNAPSHOT",
    "PLATFORM_MANIFEST_DIGEST_V1",
    "canonical_json_bytes",
    "canonical_manifest_payload",
    "is_platform_frozen_manifest",
    "ordered_items",
    "platform_manifest_digest",
]
