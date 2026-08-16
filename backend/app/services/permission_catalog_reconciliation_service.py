"""Global Permission Catalog -> t_permission reconciliation Authority.

Tenant runtime is intentionally read-only for global Permission definitions.
This service is the Control Plane writer that materializes missing ACTIVE
catalog entries into ``t_permission`` while preserving stable Permission ids
and all metadata on rows that already exist.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

from sqlalchemy import select

from app.core.permission_catalog import load_permission_catalog
from app.db.session import get_sessionmaker
from app.models import Permission


def _active_entries() -> list[dict]:
    entries = []
    for raw in load_permission_catalog().get("entries") or []:
        if str(raw.get("lifecycle") or "").upper() != "ACTIVE":
            continue
        code = str(raw.get("permissionCode") or "").strip()
        if not code:
            raise RuntimeError("ACTIVE permission catalog entry has empty permissionCode")
        entries.append(dict(raw))
    entries.sort(key=lambda item: str(item["permissionCode"]))
    return entries


def _row_metadata(entry: dict) -> dict[str, str | None]:
    code = str(entry["permissionCode"]).strip()
    label = str(entry.get("label") or code).strip() or code
    module_code = str(entry.get("moduleKey") or code.split(".", 1)[0]).strip()
    action = code.rsplit(".", 1)[-1] if "." in code else None
    if len(code) > 200:
        raise RuntimeError(f"permissionCode exceeds t_permission.permission_code: {code}")
    if len(label) > 200:
        raise RuntimeError(f"permission label exceeds t_permission.permission_name: {code}")
    if module_code and len(module_code) > 50:
        raise RuntimeError(f"permission moduleKey exceeds t_permission.module_code: {code}")
    if action and len(action) > 50:
        raise RuntimeError(f"permission action exceeds t_permission.action: {code}")
    return {
        "permission_code": code,
        "permission_name": label,
        "module_code": module_code or None,
        "action": action or None,
    }


def active_catalog_permission_codes() -> tuple[str, ...]:
    return tuple(str(item["permissionCode"]) for item in _active_entries())


def permission_catalog_digest(codes: Iterable[str] | None = None) -> str:
    values = list(codes if codes is not None else active_catalog_permission_codes())
    payload = json.dumps(sorted(set(values)), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reconcile_permission_catalog(*, source: str = "CONTROL_PLANE") -> dict:
    """Append missing ACTIVE Catalog definitions to global ``t_permission``.

    Existing rows are deliberately byte-semantics-preserving: their ids and
    metadata are not rewritten by reconciliation. Inactive/retired Catalog
    entries are never deleted because historical RolePermission rows may still
    reference their stable ids.
    """
    entries = _active_entries()
    desired = {str(item["permissionCode"]): _row_metadata(item) for item in entries}

    db = get_sessionmaker()()
    try:
        existing = set(db.scalars(
            select(Permission.permission_code).where(
                Permission.permission_code.in_(sorted(desired))
            )
        ).all()) if desired else set()
        missing_before = sorted(set(desired) - existing)

        for code in missing_before:
            db.add(Permission(**desired[code]))
        db.commit()

        materialized = set(db.scalars(
            select(Permission.permission_code).where(
                Permission.permission_code.in_(sorted(desired))
            )
        ).all()) if desired else set()
        missing_after = sorted(set(desired) - materialized)
        if missing_after:
            raise RuntimeError(
                "permission catalog reconciliation incomplete: "
                + ", ".join(missing_after[:20])
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "source": source,
        "activeCatalogCount": len(desired),
        "created": len(missing_before),
        "existing": len(desired) - len(missing_before),
        "missingAfterReconcile": 0,
        "permissionDigest": permission_catalog_digest(desired),
    }
