"""Expand-only storage adapter for the existing organization-adjustment authority.

No second request table or writer. Legacy columns retain their original types.
N-1 must not execute an expanded source scope it cannot read completely.
"""
from __future__ import annotations

import hashlib
import json

from app.core.exceptions import AppException

PREFIX = "V2_"


def scope_json(row) -> str:
    expanded = getattr(row, "from_class_ids_expanded", None)
    if expanded is not None:
        return expanded
    if str(row.status or "").startswith(PREFIX):
        raise AppException("DATA_CONFLICT", "扩展调整范围缺失，请联系管理员核对原申请", http_status=409)
    return row.from_class_ids or "[]"


def public_status(row) -> str:
    return str(row.status or "").removeprefix(PREFIX)


def set_status(row, value: str) -> None:
    row.status = (PREFIX if getattr(row, "from_class_ids_expanded", None) is not None else "") + value


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def store_check(row, payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) <= 2000:
        legacy = raw
    else:
        # N-1 may display this receipt but may not mistake an abbreviated receipt for approval.
        legacy = json.dumps({"blocked": True, "reason": "EXPANDED_RECEIPT_REQUIRES_CURRENT_VERSION",
                             "message": "完整核对回执请使用当前教务版本查看并办理"}, ensure_ascii=False)
    row.check_result_json = legacy
    row.check_result_expanded = json.dumps(
        {"schemaVersion": 1, "legacyHash": _digest(legacy), "payload": payload}, ensure_ascii=False)


def read_check(row) -> dict | None:
    legacy = row.check_result_json or ""
    expanded = getattr(row, "check_result_expanded", None)
    try:
        if expanded:
            envelope = json.loads(expanded)
            if not isinstance(envelope, dict) or envelope.get("schemaVersion") != 1:
                raise ValueError("invalid expanded envelope")
            if envelope.get("legacyHash") == _digest(legacy):
                payload = envelope.get("payload")
                if not isinstance(payload, dict):
                    raise ValueError("invalid expanded receipt")
                return payload
        if not legacy:
            return None
        result = json.loads(legacy)
        if not isinstance(result, dict):
            raise ValueError("invalid legacy receipt")
        return result
    except (TypeError, ValueError) as exc:
        raise AppException("DATA_CONFLICT", "核对回执不完整，请重新核对后办理", http_status=409) from exc
